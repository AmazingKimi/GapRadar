from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

import httpx

from .models import EvidenceTier, MarketEvent, SourceEvidence

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "will", "are", "now", "been", "being", "this", "that",
    "older", "support", "deprecated", "retired", "retiring", "deprecation", "stop", "stopping", "running",
    "version", "protected", "flows", "flow", "shop", "dev", "app", "apps",
}
REPLACEMENT_RE = re.compile(r"\b(alternative|replacement|replace|migration|migrate|compatible|drop[- ]in|successor)\b", re.I)


@dataclass(frozen=True)
class SupplyCandidate:
    title: str
    url: str
    publisher: str
    source_kind: str
    description: str
    updated_at: datetime | None = None
    popularity: int = 0
    archived: bool = False
    quality_hint: float = 0.0


def _extract_tokens(text: str) -> list[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._+-]{2,}", text)
        if token.lower() not in STOPWORDS
    ]
    seen: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
    return seen


def _product_tokens(event: MarketEvent) -> list[str]:
    return _extract_tokens(event.product)[:8]


def _query(event: MarketEvent) -> str:
    terms = _product_tokens(event)[:5]
    if not terms:
        terms = _extract_tokens(event.vendor)[:2]
    return " ".join(terms) or event.vendor


def _hits(tokens: list[str], text: str) -> int:
    return sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", text, flags=re.I))


def score_supply(candidate: SupplyCandidate, event: MarketEvent, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    title = candidate.title.lower()
    body = candidate.description.lower()
    combined = f"{title} {body}"
    tokens = _product_tokens(event)
    title_hits = _hits(tokens, title)
    total_hits = _hits(tokens, combined)
    explicit_replacement = bool(REPLACEMENT_RE.search(combined))

    # Generic ecosystem packages often repeat words such as "theme", "script",
    # or "CLI" in their descriptions. They are not substitutes. A candidate must
    # either self-identify as a replacement/migration path, or name at least two
    # product-specific concepts in its own title.
    if not explicit_replacement and title_hits < 2:
        return 0
    if explicit_replacement and total_hits < 1:
        return 0

    score = min(total_hits, 3)
    if title_hits >= 2:
        score += 1
    if explicit_replacement:
        score += 2
    if candidate.archived:
        score -= 2
    if candidate.updated_at and candidate.updated_at >= now - timedelta(days=365):
        score += 1
    if candidate.popularity >= 25:
        score += 1
    if candidate.popularity >= 250:
        score += 1
    if candidate.quality_hint >= 0.6:
        score += 1
    return max(score, 0)


def dedupe(items: Iterable[SupplyCandidate]) -> list[SupplyCandidate]:
    best: dict[str, SupplyCandidate] = {}
    for item in items:
        key = item.url.rstrip("/").lower()
        previous = best.get(key)
        if previous is None or item.popularity > previous.popularity:
            best[key] = item
    return list(best.values())


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def search_github_repositories(event: MarketEvent, *, timeout: float = 15.0) -> list[SupplyCandidate]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.4"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    query = f"{_query(event)} in:name,description,topics archived:false"
    response = httpx.get(
        "https://api.github.com/search/repositories",
        params={"q": query, "sort": "stars", "order": "desc", "per_page": 30},
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    rows: list[SupplyCandidate] = []
    for item in response.json().get("items", []):
        url = str(item.get("html_url", "")).strip()
        if not url:
            continue
        rows.append(
            SupplyCandidate(
                title=str(item.get("full_name") or item.get("name") or "GitHub repository"),
                url=url,
                publisher="GitHub Repositories",
                source_kind="github_repository",
                description=str(item.get("description") or "")[:800],
                updated_at=_parse_iso(item.get("pushed_at") or item.get("updated_at")),
                popularity=int(item.get("stargazers_count") or 0),
                archived=bool(item.get("archived", False)),
            )
        )
    return rows


def search_npm(event: MarketEvent, *, timeout: float = 15.0) -> list[SupplyCandidate]:
    response = httpx.get(
        "https://registry.npmjs.org/-/v1/search",
        params={"text": _query(event), "size": 30},
        headers={"User-Agent": "GapRadar/0.4"},
        timeout=timeout,
    )
    response.raise_for_status()
    rows: list[SupplyCandidate] = []
    for item in response.json().get("objects", []):
        package = item.get("package") or {}
        name = str(package.get("name") or "").strip()
        if not name:
            continue
        links = package.get("links") or {}
        url = str(links.get("npm") or f"https://www.npmjs.com/package/{name}")
        score = item.get("score") or {}
        detail = score.get("detail") or {}
        quality_hint = float(detail.get("quality") or 0.0)
        popularity = int(float(detail.get("popularity") or 0.0) * 1000)
        rows.append(
            SupplyCandidate(
                title=name,
                url=url,
                publisher="npm",
                source_kind="npm_package",
                description=str(package.get("description") or "")[:800],
                updated_at=_parse_iso(package.get("date")),
                popularity=popularity,
                quality_hint=quality_hint,
            )
        )
    return rows


def validate_event_supply(event: MarketEvent) -> MarketEvent:
    candidates: list[SupplyCandidate] = []
    checked: list[str] = []
    failures: list[str] = []

    for name, searcher in (("github_repositories", search_github_repositories), ("npm", search_npm)):
        try:
            candidates.extend(searcher(event))
            checked.append(name)
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    unique = dedupe(candidates)
    accepted: list[SourceEvidence] = []
    for candidate in unique:
        score = score_supply(candidate, event)
        if score < 4:
            continue
        accepted.append(
            SourceEvidence(
                tier=EvidenceTier.TIER_3_SUPPLY,
                title=candidate.title[:240],
                url=candidate.url,
                publisher=candidate.publisher,
                published_at=candidate.updated_at,
                excerpt=candidate.description,
                is_official=False,
                source_kind=candidate.source_kind,
                signal="replacement_supply",
                signal_score=score,
                engagement=candidate.popularity,
            )
        )

    accepted.sort(key=lambda item: (item.signal_score, item.engagement), reverse=True)
    event.supply_evidence = accepted[:12]
    event.supply_candidate_count = len(unique)
    event.supply_sources_checked = checked
    event.supply_checked_at = datetime.now(timezone.utc)
    event.notes = [note for note in event.notes if not note.startswith("Supply source failure:")]
    event.notes.extend(f"Supply source failure: {failure}" for failure in failures)
    event.verify()
    return event


def validate_supply(events: list[MarketEvent]) -> list[MarketEvent]:
    return [validate_event_supply(event) for event in events]
