from __future__ import annotations

import json
from pathlib import Path

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


def merge_events(existing: list[MarketEvent], incoming: list[MarketEvent]) -> list[MarketEvent]:
    by_id = {event.id: event for event in existing}
    for event in incoming:
        previous = by_id.get(event.id)
        if previous is not None:
            # Preserve prior downstream observations long enough for the same run
            # to refresh them. This avoids losing context between scan and the
            # demand/supply validators, while each validator still overwrites its
            # own evidence with the newly computed result.
            event.reaction_evidence = previous.reaction_evidence
            event.reaction_checked_at = previous.reaction_checked_at
            event.reaction_sources_checked = previous.reaction_sources_checked
            event.reaction_candidate_count = previous.reaction_candidate_count
            event.supply_evidence = previous.supply_evidence
            event.supply_checked_at = previous.supply_checked_at
            event.supply_sources_checked = previous.supply_sources_checked
            event.supply_candidate_count = previous.supply_candidate_count
            event.notes.extend(note for note in previous.notes if note not in event.notes)
            event.verify()
        by_id[event.id] = event
    return sorted(by_id.values(), key=lambda e: (e.event_date or e.detected_at), reverse=True)
