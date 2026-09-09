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


def score_migration_pain(candidate: ReactionCandidate, event: MarketEvent) -> int:
    text = _normalize(f"{candidate.title} {candidate.excerpt}")
    product_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._+-]{2,}", event.product)
        if token.lower() not in STOPWORDS
    ]
    product_hit = any(re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE) for token in product_tokens)
    if product_tokens and not product_hit:
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


def _query_terms(event: MarketEvent) -> str:
    product = re.sub(r"\s+", " ", event.product).strip()
    if len(product) > 72:
        product = " ".join(product.split()[:8])
    return f"{event.vendor} {product}".strip()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def search_hacker_news(event: MarketEvent, *, timeout: float = 15.0, days: int = 120) -> list[ReactionCandidate]:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    params = {
        "query": _query_terms(event),
        "tags": "story,comment",
        "numericFilters": f"created_at_i>{since}",
        "hitsPerPage": 40,
    }
    response = httpx.get("https://hn.algolia.com/api/v1/search_by_date", params=params, timeout=timeout)
    response.raise_for_status()
    rows: list[ReactionCandidate] = []
    for hit in response.json().get("hits", []):
        object_id = str(hit.get("objectID", "")).strip()
        if not object_id:
            continue
        title = str(hit.get("title") or hit.get("story_title") or "Hacker News discussion").strip()
        text = str(hit.get("comment_text") or hit.get("story_text") or "")
        rows.append(
            ReactionCandidate(
                title=_normalize(title),
                url=f"https://news.ycombinator.com/item?id={object_id}",
                publisher="Hacker News",
                source_kind="hacker_news",
                published_at=_parse_iso(hit.get("created_at")),
                excerpt=_normalize(text)[:800],
                engagement=int(hit.get("points") or 0) + int(hit.get("num_comments") or 0),
            )
        )
    return rows


def search_github_issues(event: MarketEvent, *, timeout: float = 15.0, days: int = 120) -> list[ReactionCandidate]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    query = f'"{event.product}" created:>={cutoff} is:issue'
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.3"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
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
        rows.append(
            ReactionCandidate(
                title=_normalize(str(item.get("title", "GitHub issue"))),
                url=html_url,
                publisher="GitHub Issues",
                source_kind="github_issue",
                published_at=_parse_iso(item.get("created_at")),
                excerpt=_normalize(str(item.get("body") or ""))[:800],
                engagement=int(item.get("comments") or 0),
            )
        )
    return rows


def validate_event_reaction(event: MarketEvent) -> MarketEvent:
    candidates: list[ReactionCandidate] = []
    checked: list[str] = []
    failures: list[str] = []

    for name, searcher in (("hacker_news", search_hacker_news), ("github_issues", search_github_issues)):
        try:
            candidates.extend(searcher(event))
            checked.append(name)
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    unique = dedupe_candidates(candidates)
    accepted: list[SourceEvidence] = []
    for candidate in unique:
        score = score_migration_pain(candidate, event)
        if score < 3:
            continue
        accepted.append(
            SourceEvidence(
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
            )
        )

    accepted.sort(key=lambda item: (item.signal_score, item.engagement), reverse=True)
    event.reaction_evidence = accepted[:12]
    event.reaction_candidate_count = len(unique)
    event.reaction_sources_checked = checked
    event.reaction_checked_at = datetime.now(timezone.utc)
    event.notes = [note for note in event.notes if not note.startswith("Reaction source failure:")]
    event.notes.extend(f"Reaction source failure: {failure}" for failure in failures)
    event.verify()
    return event


def validate_reactions(events: list[MarketEvent]) -> list[MarketEvent]:
    return [validate_event_reaction(event) for event in events]
