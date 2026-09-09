from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

from .models import MarketEvent
from .worldofficial import WorldOfficialFact
from .worldscan import GapCandidate

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "will", "new", "after", "before",
    "service", "platform", "update", "updates", "latest", "news", "rules", "rule",
}


@dataclass(frozen=True)
class WorldVerification:
    candidate_id: str
    status: str
    event_id: str | None
    official_url: str | None
    match_score: int
    reasons: list[str]


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+.-]{2,}", value or "")
        if token.lower() not in STOPWORDS
    }


def _event_type(event: MarketEvent) -> str:
    return event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)


def _official_url(event: MarketEvent) -> str | None:
    for evidence in event.official_evidence:
        if evidence.is_official and str(evidence.url):
            return str(evidence.url)
    return None


def _published(candidate: GapCandidate) -> datetime | None:
    if not candidate.published_at:
        return None
    try:
        return datetime.fromisoformat(candidate.published_at.replace("Z", "+00:00"))
    except ValueError:
        return None


def score_match(candidate: GapCandidate, event: MarketEvent) -> tuple[int, list[str]]:
    text = f"{candidate.headline} {candidate.summary}".lower()
    reasons: list[str] = []
    score = 0

    if candidate.change_type == _event_type(event):
        score += 3
        reasons.append("event_type")

    vendor = event.vendor.strip().lower()
    vendor_hit = len(vendor) >= 3 and vendor in text
    if vendor_hit:
        score += 3
        reasons.append("vendor")

    product_tokens = _tokens(event.product)
    candidate_tokens = _tokens(f"{candidate.headline} {candidate.summary}")
    product_overlap = len(product_tokens & candidate_tokens) / max(len(product_tokens), 1)
    if product_overlap >= 0.5:
        score += 2
        reasons.append("product_overlap")

    event_headline = _tokens(event.headline)
    headline_overlap = len(event_headline & candidate_tokens) / max(len(event_headline), 1)
    if headline_overlap >= 0.3:
        score += 1
        reasons.append("headline_overlap")

    published = _published(candidate)
    if published and event.event_date:
        delta_days = abs((published.date() - event.event_date.date()).days)
        if delta_days <= 30:
            score += 1
            reasons.append("date_proximity")

    # A matching event type alone is never enough. Require subject identity evidence.
    if not vendor_hit and product_overlap < 0.5:
        score = min(score, 4)

    return score, reasons


def verify_candidate(
    candidate: GapCandidate,
    events: Iterable[MarketEvent],
    official_fact: WorldOfficialFact | None = None,
) -> WorldVerification:
    # A directly fetched first-party page that passed host, subject-overlap and hard-change
    # checks is stronger than a fuzzy bridge to the configured feed corpus.
    if official_fact and official_fact.status == "tier1_verified" and official_fact.official_url:
        return WorldVerification(
            candidate_id=candidate.id,
            status="tier1_verified",
            event_id=None,
            official_url=official_fact.official_url,
            match_score=10,
            reasons=["first_party_page", "subject_overlap", "hard_change_confirmed"],
        )

    best_event: MarketEvent | None = None
    best_score = -1
    best_reasons: list[str] = []

    for event in events:
        url = _official_url(event)
        if not url:
            continue
        score, reasons = score_match(candidate, event)
        if score > best_score:
            best_event, best_score, best_reasons = event, score, reasons

    if best_event is None or best_score < 6:
        return WorldVerification(candidate.id, "unverified", None, None, max(best_score, 0), best_reasons)

    return WorldVerification(
        candidate_id=candidate.id,
        status="tier1_verified",
        event_id=best_event.id,
        official_url=_official_url(best_event),
        match_score=best_score,
        reasons=best_reasons,
    )


def verify_candidates(
    candidates: Iterable[GapCandidate],
    events: Iterable[MarketEvent],
    official_facts: Mapping[str, WorldOfficialFact] | None = None,
) -> list[WorldVerification]:
    event_rows = list(events)
    facts = official_facts or {}
    return [verify_candidate(candidate, event_rows, facts.get(candidate.id)) for candidate in candidates]


def save_verifications(path: Path, rows: Iterable[WorldVerification]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_verifications(path: Path) -> dict[str, WorldVerification]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["candidate_id"]: WorldVerification(**row) for row in payload}
