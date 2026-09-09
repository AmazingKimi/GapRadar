from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .worldscan import load_candidates

OUT = Path("data/sector-trends.json")


def build(path: Path = Path("data/world-gaps.json"), out: Path = OUT) -> dict:
    candidates = load_candidates(path)
    current = Counter((row.sector or "Other") for row in candidates)
    types = defaultdict(Counter)
    for row in candidates:
        types[row.sector or "Other"][row.change_type] += 1

    previous = {}
    if out.exists():
        try:
            previous = json.loads(out.read_text(encoding="utf-8")).get("current", {})
        except Exception:
            previous = {}

    rows = {}
    for sector in sorted(set(previous) | set(current)):
        now = int(current.get(sector, 0))
        before = previous.get(sector)
        delta = None if before is None else now - int(before)
        dominant = types[sector].most_common(1)[0][0] if types[sector] else None
        rows[sector] = {"count": now, "previous": before, "delta": delta, "dominant_change_type": dominant}

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "current": {k: int(v) for k, v in current.items()},
        "sectors": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    data = build()
    print(f"Sector trends tracked for {len(data['sectors'])} sector(s).")
