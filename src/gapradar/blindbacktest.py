from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .worldscan import TECH_TERMS, _candidate_gate, classify_change


@dataclass(frozen=True)
class BlindResult:
    id: str
    expected_detect: bool
    expected_type: str | None
    observed_detect: bool
    observed_type: str | None
    outcome: str
    type_match: bool | None


def _detect(title: str, summary: str) -> tuple[bool, str | None]:
    text = f"{title} {summary}".strip()
    classified = classify_change(text)
    if not classified:
        return False, None
    change_type, _ = classified
    if not _candidate_gate(change_type, text):
        return False, None
    if not TECH_TERMS.search(text):
        return False, None
    return True, change_type


def replay_fixture(path: Path, *, seed: int = 620) -> dict[str, Any]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("blind benchmark fixture must be a JSON list")

    stream = list(cases)
    random.Random(seed).shuffle(stream)
    rows: list[BlindResult] = []
    for case in stream:
        expected = bool(case.get("expected_detect", True))
        expected_type = str(case.get("event_type")) if expected and case.get("event_type") else None
        observed, observed_type = _detect(str(case.get("title_hint") or ""), str(case.get("excerpt_hint") or ""))
        if expected and observed:
            outcome = "tp"
        elif expected:
            outcome = "fn"
        elif observed:
            outcome = "fp"
        else:
            outcome = "tn"
        rows.append(
            BlindResult(
                id=str(case["id"]),
                expected_detect=expected,
                expected_type=expected_type,
                observed_detect=observed,
                observed_type=observed_type,
                outcome=outcome,
                type_match=(observed_type == expected_type) if expected and observed else None,
            )
        )

    counts = {key: sum(row.outcome == key for row in rows) for key in ("tp", "fp", "tn", "fn")}
    precision_den = counts["tp"] + counts["fp"]
    recall_den = counts["tp"] + counts["fn"]
    type_rows = [row for row in rows if row.type_match is not None]
    metrics = {
        "cases_total": len(rows),
        **counts,
        "precision": round(counts["tp"] / precision_den, 4) if precision_den else None,
        "recall": round(counts["tp"] / recall_den, 4) if recall_den else None,
        "event_type_accuracy": round(sum(bool(row.type_match) for row in type_rows) / len(type_rows), 4) if type_rows else None,
    }
    return {
        "mode": "blind_noisy_stream_offline",
        "seed": seed,
        "fixture": str(path),
        "metrics": metrics,
        "results": [asdict(row) for row in rows],
        "limitations": [
            "The scanner is not told which rows are positives before evaluation; positives and negative controls are shuffled into one stream.",
            "This measures the WORLD SCAN structural-language/context gate against the historical corpus, not internet retrieval coverage.",
            "The text snippets remain hand-curated historical fixtures, so this is a stricter discovery-logic benchmark but not proof of all-web recall.",
            "A separate live/archived retrieval benchmark is still required before making market-wide coverage claims.",
        ],
    }


def run(fixture: Path, output: Path, *, seed: int = 620) -> dict[str, Any]:
    report = replay_fixture(fixture, seed=seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
