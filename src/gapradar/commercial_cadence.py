from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class DailyCadence:
    date: str
    runs: int
    raw_entries: int
    kept_candidates: int
    official_candidates: int
    tier1_verified: int
    deep_analyses: int
    review_opportunities: int


@dataclass(frozen=True)
class CadenceSummary:
    days_observed: int
    review_opportunities_total: int
    days_with_review: int
    review_opportunities_per_day: float
    tier1_verified_per_day: float
    deep_analyses_per_day: float


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _current_snapshot() -> tuple[int, int, int, int, int, int]:
    scan = _read_json(Path("data/world-scan-stats.json"), {})
    quality = _read_json(Path("data/world-quality-report.json"), {})
    verification = _read_json(Path("data/world-verification-metrics.json"), {})
    assessments = _read_json(Path("data/world-assessments.json"), [])
    return (
        int(scan.get("raw_entries", 0)),
        int(quality.get("kept_candidates", 0)),
        int(verification.get("first_party_candidate_found", 0)),
        int(verification.get("tier1_verified", 0)),
        len(assessments),
        sum(str(row.get("final_recommendation", "")).upper() == "REVIEW" for row in assessments),
    )


def _load_days(path: Path) -> list[DailyCadence]:
    payload = _read_json(path, {})
    rows = payload.get("days", []) if isinstance(payload, dict) else []
    result: list[DailyCadence] = []
    for row in rows:
        try:
            result.append(DailyCadence(**row))
        except TypeError:
            continue
    return result


def summarize(days: list[DailyCadence]) -> CadenceSummary:
    count = len(days)
    total_reviews = sum(row.review_opportunities for row in days)
    return CadenceSummary(
        days_observed=count,
        review_opportunities_total=total_reviews,
        days_with_review=sum(row.review_opportunities > 0 for row in days),
        review_opportunities_per_day=round(total_reviews / count, 2) if count else 0.0,
        tier1_verified_per_day=round(sum(row.tier1_verified for row in days) / count, 2) if count else 0.0,
        deep_analyses_per_day=round(sum(row.deep_analyses for row in days) / count, 2) if count else 0.0,
    )


def run(path: Path = Path("data/commercial-cadence.json"), *, now: datetime | None = None) -> CadenceSummary:
    now = now or datetime.now(timezone.utc)
    day_key = now.astimezone(timezone.utc).date().isoformat()
    raw, kept, official, verified, deep, reviews = _current_snapshot()
    days = _load_days(path)
    by_date = {row.date: row for row in days}
    prior = by_date.get(day_key)
    by_date[day_key] = DailyCadence(
        date=day_key,
        runs=(prior.runs if prior else 0) + 1,
        # The product-value question is whether a useful item was delivered at any
        # point that day, so stages use the daily maximum rather than summing four
        # overlapping six-hour windows.
        raw_entries=max(raw, prior.raw_entries if prior else 0),
        kept_candidates=max(kept, prior.kept_candidates if prior else 0),
        official_candidates=max(official, prior.official_candidates if prior else 0),
        tier1_verified=max(verified, prior.tier1_verified if prior else 0),
        deep_analyses=max(deep, prior.deep_analyses if prior else 0),
        review_opportunities=max(reviews, prior.review_opportunities if prior else 0),
    )
    ordered = sorted(by_date.values(), key=lambda row: row.date)[-30:]
    summary = summarize(ordered)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"days": [asdict(row) for row in ordered], "summary": asdict(summary)},
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    print(
        f"Commercial cadence: {summary.days_observed} observed day(s), "
        f"{summary.review_opportunities_total} REVIEW opportunity result(s), "
        f"{summary.days_with_review} day(s) with at least one REVIEW."
    )
    return summary


if __name__ == "__main__":
    run()
