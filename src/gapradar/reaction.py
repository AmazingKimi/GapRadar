from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

import httpx

from .models import EvidenceTier, MarketEvent, SourceEvidence


MIGRATION_TERMS = (
    r"\bmigrat(?:e|ed|ing|ion)\b",
    r"\bswitch(?:ed|ing)?\b",
    r"\bmoving away\b",
    r"\bmove off\b",
    r"\breplac(?:e|ed|ement|ing)\b",
    r"\balternative(?:s)?\b",
    r"\bworkaround(?:s)?\b",
)

PAIN_TERMS = (
    r"\bforced\b",
    r"\bhave to\b",
    r"\bneed to\b",
    r"\bno longer works?\b",
    r"\bbroken\b",
    r"\bblocked\b",
    r"\bstuck\b",
    r"\bfrustrat(?:ed|ing)\b",
    r"\bexpensive\b",
    r"\bcost(?:ly|s? more)\b",
    r"\bwhat (?:do|should|can) (?:i|we) use\b",
    r"\bhow (?:do|can) (?:i|we) replace\b",
)

EVENT_TERMS = (
    r"\bdeprecat(?:e|ed|ing|ion)\b",
    r"\bsunset\b",
    r"\bshut(?:ting)? down\b",
    r"\bretir(?:e|ed|ing|ement)\b",
    r"\bdiscontinu(?:e|ed|ing|ation)\b",
    r"\bend[- ]of[- ]life\b",
    r"\bprice increase\b",
    r"\bpricing change\b",
)

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "will", "are", "now", "been", "being",
    "this", "that", "older", "support", "shopify", "github", "slack", "cloudflare", "deprecated",
    "retired", "retiring", "deprecation", "stop", "stopping", "running", "version",
}


@dataclass(frozen=True)
class ReactionCandidate:
    title: str
    url: str
    publisher: str
    source_kind: str
    published_at: datetime | None
    excerpt: str
    engagement: int = 0


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", text or "").split())


def _has(patterns: Iterable[str], text: str) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL))


def _product_tokens(event: MarketEvent) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._+-]{2,}", event.product)
        if token.lower() not in STOPWORDS
    ]


def _relevant_to_event(text: str, event: MarketEvent) -> bool:
    text = _normalize(text).lower()
    product = _normalize(event.product).lower()
    vendor = _normalize(event.vendor).lower()
    tokens = _product_tokens(event)
    hits = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE))
    if product and product in text:
        return True
    if vendor and vendor in text and hits >= 1:
        return True
    return hits >= min(2, len(tokens)) if tokens else bool(vendor and vendor in text)


def score_migration_pain(candidate: ReactionCandidate, event: MarketEvent) -> int:
    text = _normalize(f"{candidate.title} {candidate.excerpt}")
    if not _relevant_to_event(text, event):
        return 0

    migration = _has(MIGRATION_TERMS, text)
    pain = _has(PAIN_TERMS, text)
    event_language = _has(EVENT_TERMS, text)

    score = 0
    if migration:
        score += 2
    if pain:
        score += 2
    if event_language:
        score += 1
    if "?" in candidate.title and (migration or pain):
        score += 1
    if candidate.engagement >= 5:
        score += 1
    if candidate.engagement >= 20:
        score += 1
    return score


def is_migration_pain(candidate: ReactionCandidate, event: MarketEvent) -> bool:
    return score_migration_pain(candidate, event) >= 3


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def dedupe_candidates(items: Iterable[ReactionCandidate]) -> list[ReactionCandidate]:
    best: dict[str, ReactionCandidate] = {}
    for item in items:
        key = canonical_url(item.url)
        previous = best.get(key)
        if previous is None or item.engagement > previous.engagement:
            best[key] = item
    return list(best.values())


def _product_phrase(event: MarketEvent) -> str:
    product = re.sub(r"\s+", " ", event.product).strip()
    if len(product) > 72:
        product = " ".join(product.split()[:8])
    return product


def _event_query_words(event: MarketEvent) -> list[str]:
    if event.event_type.value == "price_shock":
        return ["pricing", "price increase", "alternative", "switch"]
    if event.event_type.value == "api_terms_change":
        return ["deprecated", "migration", "alternative", "API change"]
    return ["deprecated", "sunset", "migration", "alternative"]


def hacker_news_queries(event: MarketEvent) -> list[str]:
    product = _product_phrase(event)
    candidates = [product, f"{event.vendor} {product}"]
    candidates.extend(f"{product} {word}" for word in _event_query_words(event))
    return list(dict.fromkeys(q.strip() for q in candidates if q.strip()))


def github_issue_queries(event: MarketEvent, cutoff: str) -> list[str]:
    product = _product_phrase(event)
    base = [
        f'"{product}" {event.vendor} created:>={cutoff} is:issue',
        f'"{product}" created:>={cutoff} is:issue',
    ]
    base.extend(f'"{product}" {word} created:>={cutoff} is:issue' for word in _event_query_words(event))
    return list(dict.fromkeys(base))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hn_query(query: str, since: int, timeout: float) -> list[ReactionCandidate]:
    response = httpx.get(
        "https://hn.algolia.com/api/v1/search_by_date",
        params={"query": query, "tags": "story,comment", "numericFilters": f"created_at_i>{since}", "hitsPerPage": 40},
        timeout=timeout,
    )
    response.raise_for_status()
    rows: list[ReactionCandidate] = []
    for hit in response.json().get("hits", []):
        object_id = str(hit.get("objectID", "")).strip()
        if not object_id:
            continue
        title = str(hit.get("title") or hit.get("story_title") or "Hacker News discussion").strip()
        text = str(hit.get("comment_text") or hit.get("story_text") or "")
        rows.append(ReactionCandidate(
            title=_normalize(title),
            url=f"https://news.ycombinator.com/item?id={object_id}",
            publisher="Hacker News",
            source_kind="hacker_news",
            published_at=_parse_iso(hit.get("created_at")),
            excerpt=_normalize(text)[:800],
            engagement=int(hit.get("points") or 0) + int(hit.get("num_comments") or 0),
        ))
    return rows


def search_hacker_news(event: MarketEvent, *, timeout: float = 15.0, days: int = 120) -> list[ReactionCandidate]:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    rows: list[ReactionCandidate] = []
    for query in hacker_news_queries(event):
        rows.extend(_hn_query(query, since, timeout))
    return dedupe_candidates(rows)


def _github_query(query: str, headers: dict[str, str], timeout: float) -> list[ReactionCandidate]:
    response = httpx.get(
        "https://api.github.com/search/issues",
        params={"q": query, "sort": "comments", "order": "desc", "per_page": 40},
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    rows: list[ReactionCandidate] = []
    for item in response.json().get("items", []):
        html_url = str(item.get("html_url", "")).strip()
        if not html_url:
            continue
        rows.append(ReactionCandidate(
            title=_normalize(str(item.get("title", "GitHub issue"))),
            url=html_url,
            publisher="GitHub Issues",
            source_kind="github_issue",
            published_at=_parse_iso(item.get("created_at")),
            excerpt=_normalize(str(item.get("body") or ""))[:800],
            engagement=int(item.get("comments") or 0),
        ))
    return rows


def search_github_issues(event: MarketEvent, *, timeout: float = 15.0, days: int = 120) -> list[ReactionCandidate]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.6"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    rows: list[ReactionCandidate] = []
    for query in github_issue_queries(event, cutoff):
        rows.extend(_github_query(query, headers, timeout))
    return dedupe_candidates(rows)


def validate_event_reaction(event: MarketEvent) -> MarketEvent:
    candidates: list[ReactionCandidate] = []
    checked: list[str] = []
    failures: list[str] = []
    audits: list[dict[str, object]] = []

    since = int((datetime.now(timezone.utc) - timedelta(days=120)).timestamp())
    for query in hacker_news_queries(event):
        try:
            found = _hn_query(query, since, 15.0)
            candidates.extend(found)
            audits.append({"source": "hacker_news", "query": query, "candidate_count": len(found), "ok": True})
            if "hacker_news" not in checked:
                checked.append("hacker_news")
        except Exception as exc:
            failures.append(f"hacker_news [{query}]: {type(exc).__name__}: {exc}")
            audits.append({"source": "hacker_news", "query": query, "candidate_count": 0, "ok": False})

    cutoff = (datetime.now(timezone.utc) - timedelta(days=120)).date().isoformat()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.6"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for query in github_issue_queries(event, cutoff):
        try:
            found = _github_query(query, headers, 15.0)
            candidates.extend(found)
            audits.append({"source": "github_issues", "query": query, "candidate_count": len(found), "ok": True})
            if "github_issues" not in checked:
                checked.append("github_issues")
        except Exception as exc:
            failures.append(f"github_issues [{query}]: {type(exc).__name__}: {exc}")
            audits.append({"source": "github_issues", "query": query, "candidate_count": 0, "ok": False})

    unique = dedupe_candidates(candidates)
    accepted: list[SourceEvidence] = []
    for candidate in unique:
        score = score_migration_pain(candidate, event)
        if score < 3:
            continue
        accepted.append(SourceEvidence(
            tier=EvidenceTier.TIER_2_REACTION,
            title=candidate.title[:240] or "Reaction",
            url=candidate.url,
            publisher=candidate.publisher,
            published_at=candidate.published_at,
            excerpt=candidate.excerpt,
            is_official=False,
            source_kind=candidate.source_kind,
            signal="migration_pain",
            signal_score=score,
            engagement=candidate.engagement,
        ))

    accepted.sort(key=lambda item: (item.signal_score, item.engagement), reverse=True)
    event.reaction_evidence = accepted[:12]
    event.reaction_candidate_count = len(unique)
    event.reaction_sources_checked = checked
    event.reaction_queries = audits
    event.reaction_checked_at = datetime.now(timezone.utc)
    successful = sum(1 for row in audits if row.get("ok"))
    if successful == 0:
        event.reaction_search_quality = "failed"
    elif successful < len(audits):
        event.reaction_search_quality = "degraded"
    else:
        event.reaction_search_quality = "adequate"
    event.notes = [note for note in event.notes if not note.startswith("Reaction source failure:")]
    event.notes.extend(f"Reaction source failure: {failure}" for failure in failures)
    event.verify()
    return event


def validate_reactions(events: list[MarketEvent]) -> list[MarketEvent]:
    return [validate_event_reaction(event) for event in events]
