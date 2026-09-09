from __future__ import annotations

import json
from pathlib import Path

from .detector import classify_entry
from .models import MarketEvent


def load_events(path: Path) -> list[MarketEvent]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [MarketEvent.model_validate(item) for item in raw]


def save_events(path: Path, events: list[MarketEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [event.model_dump(mode="json") for event in events]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _still_matches_live_detector(event: MarketEvent) -> bool:
    if not event.official_evidence:
        return False
    official = event.official_evidence[0]
    observed = classify_entry(official.title, official.excerpt, allow_strong_body=False)
    return observed == event.event_type


def merge_events(
    existing: list[MarketEvent],
    incoming: list[MarketEvent],
    *,
    revalidate_existing: bool = False,
) -> list[MarketEvent]:
    incoming_ids = {event.id for event in incoming}
    if revalidate_existing:
        existing = [
            event for event in existing
            if event.id in incoming_ids or _still_matches_live_detector(event)
        ]

    by_id = {event.id: event for event in existing}
    for event in incoming:
        previous = by_id.get(event.id)
        if previous is not None:
            event.reaction_evidence = previous.reaction_evidence
            event.supply_evidence = previous.supply_evidence
            event.reaction_checked_at = previous.reaction_checked_at
            event.reaction_sources_checked = previous.reaction_sources_checked
            event.reaction_candidate_count = previous.reaction_candidate_count
            event.reaction_queries = previous.reaction_queries
            event.reaction_search_quality = previous.reaction_search_quality
            event.notes.extend(note for note in previous.notes if note not in event.notes)
            event.verify()
        by_id[event.id] = event
    return sorted(by_id.values(), key=lambda e: (e.event_date or e.detected_at), reverse=True)
