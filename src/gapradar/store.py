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
        by_id[event.id] = event
    return sorted(by_id.values(), key=lambda e: (e.event_date or e.detected_at), reverse=True)
