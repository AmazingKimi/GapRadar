from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .worldscan import GapCandidate, load_candidates
from .worldverify import load_verifications


@dataclass(frozen=True)
class VerificationHistoryRow:
    candidate_id: str
    headline: str
    first_seen_at: str
    last_seen_at: str
    status: str
    verified_at: str | None


@dataclass(frozen=True)
class VerificationMetrics:
    tracked_candidates: int
    tier1_verified: int
    awaiting_tier1: int
    average_awaiting_hours: float
    oldest_awaiting_hours: float


def _now_iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat()


def _load_history(path: Path) -> dict[str, VerificationHistoryRow]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {row["candidate_id"]: VerificationHistoryRow(**row) for row in payload}


def update_history(
    candidates: list[GapCandidate],
    verification: dict[str, object],
    existing: dict[str, VerificationHistoryRow],
    *,
    now: datetime,
) -> list[VerificationHistoryRow]:
    stamp = _now_iso(now)
    rows: list[VerificationHistoryRow] = []
    for candidate in candidates:
        prior = existing.get(candidate.id)
        status = getattr(verification.get(candidate.id), "status", "unverified")
        verified_at = prior.verified_at if prior else None
        if status == "tier1_verified" and not verified_at:
            verified_at = stamp
        rows.append(
            VerificationHistoryRow(
                candidate_id=candidate.id,
                headline=candidate.headline,
                first_seen_at=prior.first_seen_at if prior else stamp,
                last_seen_at=stamp,
                status=status,
                verified_at=verified_at,
            )
        )
    return rows


def metrics(rows: list[VerificationHistoryRow], *, now: datetime) -> VerificationMetrics:
    pending = [row for row in rows if row.status != "tier1_verified"]
    ages: list[float] = []
    for row in pending:
        try:
            first = datetime.fromisoformat(row.first_seen_at.replace("Z", "+00:00"))
            ages.append(max(0.0, (now.astimezone(timezone.utc) - first.astimezone(timezone.utc)).total_seconds() / 3600))
        except ValueError:
            continue
    verified = sum(row.status == "tier1_verified" for row in rows)
    return VerificationMetrics(
        tracked_candidates=len(rows),
        tier1_verified=verified,
        awaiting_tier1=len(pending),
        average_awaiting_hours=round(sum(ages) / len(ages), 1) if ages else 0.0,
        oldest_awaiting_hours=round(max(ages), 1) if ages else 0.0,
    )


def run(
    candidates_path: Path = Path("data/world-gaps.json"),
    verification_path: Path = Path("data/world-verifications.json"),
    history_path: Path = Path("data/world-verification-history.json"),
    metrics_path: Path = Path("data/world-verification-metrics.json"),
    *,
    now: datetime | None = None,
) -> VerificationMetrics:
    now = now or datetime.now(timezone.utc)
    candidates = load_candidates(candidates_path)
    verification = load_verifications(verification_path)
    existing = _load_history(history_path)
    rows = update_history(candidates, verification, existing, now=now)
    summary = metrics(rows, now=now)
    history_path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(asdict(summary), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Tier-1 tracker: {summary.tier1_verified} verified, {summary.awaiting_tier1} awaiting; "
        f"average pending {summary.average_awaiting_hours}h, oldest {summary.oldest_awaiting_hours}h."
    )
    return summary


if __name__ == "__main__":
    run()
