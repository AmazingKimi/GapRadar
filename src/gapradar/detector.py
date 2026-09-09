from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import httpx

from .models import EventType, EvidenceTier, MarketEvent, SourceEvidence


PATTERNS: dict[EventType, tuple[str, ...]] = {
    EventType.SHUTDOWN: (
        r"\bshut(?:ting)? down\b",
        r"\bdiscontinu(?:e|ed|ing)\b",
        r"\bend[- ]of[- ]life\b",
        r"\bEOL\b",
        r"\bretir(?:e|ed|ing)\b",
        r"\bwill no longer be available\b",
    ),
    EventType.PRICE_SHOCK: (
        r"\bpricing (?:change|update)\b",
        r"\bprice (?:increase|change|update)\b",
        r"\bnew pricing\b",
        r"\bfree (?:plan|tier).*(?:end|remove|retire|discontinue)\w*\b",
    ),
    EventType.API_TERMS: (
        r"\bAPI.*(?:deprecat|sunset|retir|discontinu)\w*\b",
        r"\bdeprecat\w*.*API\b",
        r"\bterms of service.*(?:change|update)\b",
        r"\bpolicy (?:change|update)\b",
        r"\bbreaking change\b",
    ),
}

# Specific contexts must win over generic retirement language. For example,
# "free tier will be discontinued" is a pricing event, not a product shutdown.
CLASSIFICATION_ORDER = (
    EventType.API_TERMS,
    EventType.PRICE_SHOCK,
    EventType.SHUTDOWN,
)


@dataclass(frozen=True)
class OfficialSource:
    name: str
    vendor: str
    url: str
    allowed_domains: tuple[str, ...]


def classify(text: str) -> EventType | None:
    normalized = " ".join(text.split())
    for event_type in CLASSIFICATION_ORDER:
        for pattern in PATTERNS[event_type]:
            if re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL):
                return event_type
    return None


def is_allowed_official_url(url: str, allowed_domains: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)


def make_event_id(vendor: str, product: str, headline: str) -> str:
    raw = f"{vendor}|{product}|{headline}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _published(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def scan_source(source: OfficialSource, *, timeout: float = 20.0) -> list[MarketEvent]:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "GapRadar/0.1"}) as client:
        response = client.get(source.url)
        response.raise_for_status()

    feed = feedparser.loads(response.text)
    events: list[MarketEvent] = []

    for entry in feed.entries:
        title = str(entry.get("title", "")).strip()
        summary = str(entry.get("summary", "")).strip()
        link = str(entry.get("link", "")).strip()
        event_type = classify(f"{title}\n{summary}")
        if not event_type or not link:
            continue
        if not is_allowed_official_url(link, source.allowed_domains):
            continue

        evidence = SourceEvidence(
            tier=EvidenceTier.TIER_1_OFFICIAL,
            title=title,
            url=link,
            publisher=source.vendor,
            published_at=_published(entry),
            excerpt=re.sub(r"<[^>]+>", " ", summary)[:500],
            is_official=True,
        )
        event = MarketEvent(
            id=make_event_id(source.vendor, source.name, title),
            product=source.name,
            vendor=source.vendor,
            event_type=event_type,
            headline=title,
            summary=evidence.excerpt or title,
            event_date=evidence.published_at,
            official_evidence=[evidence],
        )
        event.verify()
        events.append(event)

    return events
