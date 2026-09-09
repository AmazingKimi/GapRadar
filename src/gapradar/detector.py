from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import httpx

from .models import EventType, EvidenceTier, MarketEvent, SourceEvidence


TITLE_PATTERNS: dict[EventType, tuple[str, ...]] = {
    EventType.PRICE_SHOCK: (
        r"\bpricing (?:change|changes|update|updates)\b",
        r"\bprice (?:increase|increases|change|changes|update|updates)\b",
        r"\bnew pricing\b",
        r"\bfree (?:plan|tier).*(?:end|ending|remove|removed|retire|retired|discontinue|discontinued)\w*\b",
        r"\bbilling (?:change|changes|update|updates)\b",
    ),
    EventType.API_TERMS: (
        r"\b(?:API|APIs|SDK|endpoint|endpoints|REST|GraphQL|webhook|webhooks).*(?:deprecat|sunset|retir|remov|discontinu)\w*\b",
        r"\b(?:deprecat|sunset|retir|remov|discontinu)\w*.*(?:API|APIs|SDK|endpoint|endpoints|REST|GraphQL|webhook|webhooks)\b",
        r"\bterms of service.*(?:change|changes|update|updates)\b",
        r"\bpolicy (?:change|changes|update|updates)\b",
        r"\bbreaking change\b",
    ),
    EventType.SHUTDOWN: (
        r"\bshut(?:ting)? down\b",
        r"\bdecommission(?:ed|ing)?\b",
        r"\bend[- ]of[- ]life\b",
        r"\bEOL\b",
        r"\bretir(?:e|ed|ing)\b",
        r"\bdeprecated\b",
        r"\bdiscontinu(?:e|ed|ing)\b",
        r"\bno longer available\b",
    ),
}

# Body-only matching is deliberately much stricter. A changelog entry can
# mention a deprecated field while announcing a completely unrelated feature;
# that is not a market-change event. We only inspect the body when the title
# itself clearly frames the post as a migration/transition/removal notice.
BODY_FALLBACK_TITLE_GATE = (
    r"\bmigration\b",
    r"\btransition\b",
    r"\bremoval\b",
    r"\bend[- ]of[- ]support\b",
    r"\bsunset notice\b",
)

BODY_PATTERNS: dict[EventType, tuple[str, ...]] = {
    EventType.PRICE_SHOCK: (
        r"\bfree (?:plan|tier).{0,120}\b(?:will|is|has been).{0,40}\b(?:removed|retired|discontinued|ended)\b",
        r"\bprice.{0,80}\b(?:will|is).{0,30}\b(?:increase|increasing|changing)\b",
        r"\b(?:billing|pricing).{0,80}\b(?:will|is).{0,30}\b(?:change|changing)\b",
    ),
    EventType.API_TERMS: (
        r"\b(?:API|SDK|endpoint|REST|GraphQL|webhook).{0,180}\b(?:will|is|has been).{0,50}\b(?:deprecated|removed|retired|sunset|discontinued)\b",
        r"\b(?:deprecated|removed|retired|sunset|discontinued).{0,180}\b(?:API|SDK|endpoint|REST|GraphQL|webhook)\b",
        r"\bterms of service.{0,100}\b(?:will|have|has).{0,30}\b(?:change|changed|updated)\b",
    ),
    EventType.SHUTDOWN: (
        r"\b(?:product|service|app|application|platform|feature|model).{0,160}\b(?:will|is|has been).{0,50}\b(?:retired|shutdown|shut down|decommissioned|discontinued|deprecated)\b",
        r"\bwill no longer be available\b",
        r"\bfully retired\b",
        r"\bhas been decommissioned\b",
        r"\bis now retired\b",
    ),
}

CLASSIFICATION_ORDER = (
    EventType.PRICE_SHOCK,
    EventType.API_TERMS,
    EventType.SHUTDOWN,
)


@dataclass(frozen=True)
class OfficialSource:
    name: str
    vendor: str
    url: str
    allowed_domains: tuple[str, ...]
    lookback_days: int = 30
    max_entries: int = 120


@dataclass(frozen=True)
class SourceProbe:
    source: OfficialSource
    http_status: int
    entry_count: int
    official_link_count: int


def _match(patterns: tuple[str, ...], text: str) -> bool:
    normalized = " ".join(text.split())
    return any(re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def classify(text: str) -> EventType | None:
    for event_type in CLASSIFICATION_ORDER:
        if _match(TITLE_PATTERNS[event_type], text):
            return event_type
    return None


def classify_entry(title: str, summary: str) -> EventType | None:
    for event_type in CLASSIFICATION_ORDER:
        if _match(TITLE_PATTERNS[event_type], title):
            return event_type

    if not _match(BODY_FALLBACK_TITLE_GATE, title):
        return None

    for event_type in CLASSIFICATION_ORDER:
        if _match(BODY_PATTERNS[event_type], summary):
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


def _clean_html(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value).split())


def _infer_product(source: OfficialSource, title: str) -> str:
    subject = re.sub(r"^(?:upcoming\s+)?(?:deprecation(?: notice)? of\s+)", "", title, flags=re.IGNORECASE)
    subject = re.sub(
        r"\b(?:is|are|was|were|will be)?\s*(?:now\s+)?(?:deprecated|retired|retiring|discontinued|decommissioned)\b.*$",
        "",
        subject,
        flags=re.IGNORECASE,
    ).strip(" :-–—")
    if 2 <= len(subject) <= 90:
        return subject
    return source.name


def parse_feed(feed_text: str, source: OfficialSource, *, now: datetime | None = None) -> list[MarketEvent]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=source.lookback_days)
    feed = feedparser.parse(feed_text)
    events: list[MarketEvent] = []

    for entry in feed.entries[: source.max_entries]:
        title = str(entry.get("title", "")).strip()
        summary = str(entry.get("summary", entry.get("description", ""))).strip()
        link = str(entry.get("link", "")).strip()
        published_at = _published(entry)

        if not title or not link:
            continue
        if published_at and published_at < cutoff:
            continue
        if not is_allowed_official_url(link, source.allowed_domains):
            continue

        event_type = classify_entry(title, summary)
        if not event_type:
            continue

        clean_summary = _clean_html(summary)
        product = _infer_product(source, title)
        evidence = SourceEvidence(
            tier=EvidenceTier.TIER_1_OFFICIAL,
            title=title,
            url=link,
            publisher=source.vendor,
            published_at=published_at,
            excerpt=clean_summary[:700],
            is_official=True,
        )
        event = MarketEvent(
            id=make_event_id(source.vendor, product, title),
            product=product,
            vendor=source.vendor,
            event_type=event_type,
            headline=title,
            summary=evidence.excerpt or title,
            event_date=published_at,
            official_evidence=[evidence],
        )
        event.verify()
        events.append(event)

    return events


def _get(source: OfficialSource, timeout: float) -> httpx.Response:
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "GapRadar/0.2 (+https://github.com/AmazingKimi/GapRadar)"},
    ) as client:
        response = client.get(source.url)
        response.raise_for_status()
        return response


def scan_source(source: OfficialSource, *, timeout: float = 20.0) -> list[MarketEvent]:
    response = _get(source, timeout)
    return parse_feed(response.text, source)


def probe_source(source: OfficialSource, *, timeout: float = 20.0) -> SourceProbe:
    response = _get(source, timeout)
    feed = feedparser.parse(response.text)
    entries = list(feed.entries[: source.max_entries])
    official_links = sum(
        1
        for entry in entries
        if is_allowed_official_url(str(entry.get("link", "")), source.allowed_domains)
    )
    return SourceProbe(
        source=source,
        http_status=response.status_code,
        entry_count=len(entries),
        official_link_count=official_links,
    )
