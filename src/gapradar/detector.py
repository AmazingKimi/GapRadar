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
        r"\b(?:cancel|canceling|cancelling|remove|removing).{0,40}\b(?:fee|pricing|charge)\b",
    ),
    EventType.API_TERMS: (
        r"\b(?:API|APIs|SDK|endpoint|endpoints|REST|GraphQL|webhook|webhooks).*(?:deprecat|sunset|retir|remov|discontinu)\w*\b",
        r"\b(?:deprecat|sunset|retir|remov|discontinu)\w*.*(?:API|APIs|SDK|endpoint|endpoints|REST|GraphQL|webhook|webhooks)\b",
        r"\bterms of service.*(?:change|changes|update|updates)\b",
        r"\blicens(?:e|ing).*(?:change|changes|update|updates|adopt)\b",
        r"\b(?:adopt|switch).{0,50}\b(?:license|licence)\b",
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
        r"\bsunset(?:ting)?\b",
        r"\bgoing away\b",
        r"\bwind(?:ing)? down\b",
    ),
}

BODY_FALLBACK_TITLE_GATE = (
    r"\bmigration\b",
    r"\btransition\b",
    r"\bremoval\b",
    r"\bend[- ]of[- ]support\b",
    r"\bsunset notice\b",
    r"\bnext chapter\b",
    r"\bmessage about\b",
    r"\bwhat(?:'s| is) changing\b",
    r"\bimportant changes\b",
    r"\bupdates? to\b",
    r"\bpricing updates?\b",
    r"\bhealthy ecosystem\b",
    r"\bnext phase\b",
    r"\binvesting in\b",
    r"\bsaying goodbye\b",
    r"\bend of\b",
)

BODY_PATTERNS: dict[EventType, tuple[str, ...]] = {
    EventType.PRICE_SHOCK: (
        r"\bfree (?:plan|tier).{0,180}\b(?:will|is|has been).{0,60}\b(?:removed|retired|discontinued|ended|limited|deactivated)\b",
        r"\bprice.{0,100}\b(?:will|is).{0,50}\b(?:increase|increasing|changing)\b",
        r"\b(?:billing|pricing).{0,100}\b(?:will|is).{0,50}\b(?:change|changing)\b",
        r"\b(?:free|existing).{0,120}\b(?:plan|tier|users?).{0,120}\b(?:paid|subscription|pro)\b",
        r"\b(?:fee|charge).{0,120}\b(?:introduc|cancel|remov)\w*\b",
        r"\b(?:sunset|end|retire|limit|deactivat)\w*.{0,120}\bfree.{0,80}\b(?:plans?|tier|users?)\b",
        r"\bfree.{0,100}\b(?:plans?|tier|users?).{0,140}\b(?:sunset|end|retire|limit|deactivat|paid|subscription|pro)\w*\b",
    ),
    EventType.API_TERMS: (
        r"\b(?:API|SDK|endpoint|REST|GraphQL|webhook).{0,220}\b(?:will|is|has been).{0,70}\b(?:deprecated|removed|retired|sunset|discontinued|changed)\b",
        r"\b(?:deprecated|removed|retired|sunset|discontinued).{0,220}\b(?:API|SDK|endpoint|REST|GraphQL|webhook)\b",
        r"\bterms of service.{0,140}\b(?:will|have|has).{0,50}\b(?:change|changed|updated)\b",
        r"\b(?:license|licensing).{0,160}\b(?:change|changed|adopt|adopted|switch|switched)\w*\b",
        r"\b(?:data )?API access.{0,180}\b(?:change|update|commercial|terms)\w*\b",
    ),
    EventType.SHUTDOWN: (
        r"\b(?:product|service|app|application|platform|feature|model|plans?|dynos?|devices?).{0,200}\b(?:will|is|has been).{0,70}\b(?:retired|shutdown|shut down|decommissioned|discontinued|deprecated|wound down|sunset)\b",
        r"\bwill no longer be available\b",
        r"\bwill no longer run\b",
        r"\bfully retired\b",
        r"\bhas been decommissioned\b",
        r"\bis now retired\b",
        r"\b(?:begin|beginning|start|starting).{0,80}\b(?:wind|shut|sunset|phase)\w*.{0,80}\b(?:down|out)\b",
        r"\bwill be discontinued\b",
        r"\bshuts down\b",
        r"\bwill wind down\b",
    ),
}

STRONG_BODY_PATTERNS: dict[EventType, tuple[str, ...]] = {
    EventType.PRICE_SHOCK: (
        r"\b(?:sunset|end|retire|limit|deactivat)\w*.{0,140}\bfree.{0,100}\b(?:plans?|tier|users?)\b",
        r"\bfree.{0,120}\b(?:plans?|tier|users?).{0,180}\b(?:sunset|end|retire|limit|deactivat)\w*\b",
        r"\b(?:starting|beginning|effective|from).{0,100}\b(?:free )?(?:users?|plans?|tier).{0,140}\b(?:only|need|require|move|upgrade).{0,100}\b(?:paid|pro|subscription)\b",
        r"\b(?:introduc|new).{0,80}\b(?:runtime )?(?:fee|pricing|charge)\b",
    ),
    EventType.API_TERMS: (
        r"\b(?:adopt|adopted|switch|switched).{0,120}\b(?:business source )?(?:license|licence)\b",
        r"\b(?:data )?API.{0,180}\b(?:access|terms).{0,180}\b(?:change|commercial|pricing|paid)\w*\b",
        r"\b(?:manifest v2|extensions?).{0,220}\b(?:phase out|transition|no longer run|deprecat)\w*\b",
    ),
    EventType.SHUTDOWN: (
        r"\b(?:we|service|product|app|application|platform|device|devices|core).{0,200}\b(?:will|have|has|begin|began|start|started).{0,100}\b(?:shut down|wind down|sunset|phase out|discontinue|retire|decommission)\w*\b",
        r"\bwill be discontinued on\b",
        r"\bwill reach (?:its )?(?:end[- ]of[- ]life|EOL)\b",
        r"\bwill no longer be supported\b",
        r"\bshuts down\b",
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


def classify_entry(title: str, summary: str, *, allow_strong_body: bool = False) -> EventType | None:
    for event_type in CLASSIFICATION_ORDER:
        if _match(TITLE_PATTERNS[event_type], title):
            return event_type

    if _match(BODY_FALLBACK_TITLE_GATE, title):
        for event_type in CLASSIFICATION_ORDER:
            if _match(BODY_PATTERNS[event_type], summary):
                return event_type

    if allow_strong_body:
        for event_type in CLASSIFICATION_ORDER:
            if _match(STRONG_BODY_PATTERNS[event_type], summary):
                return event_type
    return None


def is_allowed_official_url(url: str, allowed_domains: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)


def make_event_id(vendor: str, product: str, headline: str) -> str:
    raw = f"{vendor}|{product}|{headline}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def event_from_document(
    *,
    vendor: str,
    product: str,
    title: str,
    summary: str,
    url: str,
    published_at: datetime | None = None,
    historical: bool = False,
) -> MarketEvent | None:
    event_type = classify_entry(title, summary, allow_strong_body=historical)
    if event_type is None:
        return None
    evidence = SourceEvidence(
        tier=EvidenceTier.TIER_1_OFFICIAL,
        title=title,
        url=url,
        publisher=vendor,
        published_at=published_at,
        excerpt=_clean_html(summary)[:700],
        is_official=True,
    )
    event = MarketEvent(
        id=make_event_id(vendor, product, title),
        product=product,
        vendor=vendor,
        event_type=event_type,
        headline=title,
        summary=evidence.excerpt or title,
        event_date=published_at,
        official_evidence=[evidence],
    )
    return event.verify()


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
        r"\b(?:(?:is|are|was|were|will be|to be)\s+)?(?:now\s+)?(?:deprecated|retired|retiring|discontinued|decommissioned)\b.*$",
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

        product = _infer_product(source, title)
        event = event_from_document(
            vendor=source.vendor,
            product=product,
            title=title,
            summary=summary,
            url=link,
            published_at=published_at,
            historical=False,
        )
        if event is not None:
            events.append(event)

    return events


def _get(source: OfficialSource, timeout: float) -> httpx.Response:
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "GapRadar/0.7 (+https://github.com/AmazingKimi/GapRadar)"},
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
    official_links = sum(1 for entry in entries if is_allowed_official_url(str(entry.get("link", "")), source.allowed_domains))
    return SourceProbe(source=source, http_status=response.status_code, entry_count=len(entries), official_link_count=official_links)
