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
    resolution_status: str = "awaiting_search"
    official_candidate_count: int = 0
    search_coverage: str = "unknown"


@dataclass(frozen=True)
class VerificationMetrics:
    tracked_candidates: int
    tier1_verified: int
    awaiting_tier1: int
    average_awaiting_hours: float
    oldest_awaiting_hours: float
    first_party_candidate_found: int = 0
    no_first_party_candidate: int = 0
    search_failed: int = 0
    verification_failed: int = 0
    first_party_candidate_yield: float = 0.0
    tier1_verification_yield: float = 0.0


def _now_iso(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat()


def _load_history(path: Path) -> dict[str, VerificationHistoryRow]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows: dict[str, VerificationHistoryRow] = {}
    for row in payload:
        rows[row["candidate_id"]] = VerificationHistoryRow(
            candidate_id=row["candidate_id"],
            headline=row.get("headline", ""),
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            status=row.get("status", "unverified"),
            verified_at=row.get("verified_at"),
            resolution_status=row.get("resolution_status", "awaiting_search"),
            official_candidate_count=int(row.get("official_candidate_count", 0)),
            search_coverage=row.get("search_coverage", "unknown"),
        )
    return rows


def _load_official_leads(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(row.get("candidate_id")): row for row in payload if row.get("candidate_id")}


def _resolution_status(verification_status: str, lead: dict[str, object] | None) -> tuple[str, int, str]:
    if verification_status == "tier1_verified":
        count = len((lead or {}).get("candidate_urls") or [])
        return "tier1_verified", count, str((lead or {}).get("search_coverage") or "unknown")
    if not lead:
        return "awaiting_search", 0, "unknown"
    urls = list(lead.get("candidate_urls") or [])
    coverage = str(lead.get("search_coverage") or "unknown")
    status = str(lead.get("status") or "")
    if status == "search_failed" or coverage == "failed":
        return "search_failed", len(urls), coverage
    if not urls:
        return "no_first_party_candidate", 0, coverage
    return "verification_failed", len(urls), coverage


def update_history(
    candidates: list[GapCandidate],
    verification: dict[str, object],
    existing: dict[str, VerificationHistoryRow],
    *,
    now: datetime,
    official_leads: dict[str, dict[str, object]] | None = None,
) -> list[VerificationHistoryRow]:
    stamp = _now_iso(now)
    leads = official_leads or {}
    rows: list[VerificationHistoryRow] = []
    for candidate in candidates:
        prior = existing.get(candidate.id)
        status = getattr(verification.get(candidate.id), "status", "unverified")
        verified_at = prior.verified_at if prior else None
        if status == "tier1_verified" and not verified_at:
            verified_at = stamp
        resolution, candidate_count, coverage = _resolution_status(status, leads.get(candidate.id))
        rows.append(
            VerificationHistoryRow(
                candidate_id=candidate.id,
                headline=candidate.headline,
                first_seen_at=prior.first_seen_at if prior else stamp,
                last_seen_at=stamp,
                status=status,
                verified_at=verified_at,
                resolution_status=resolution,
                official_candidate_count=candidate_count,
                search_coverage=coverage,
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
    candidate_found = sum(row.official_candidate_count > 0 for row in rows)
    no_candidate = sum(row.resolution_status == "no_first_party_candidate" for row in rows)
    search_failed = sum(row.resolution_status == "search_failed" for row in rows)
    verification_failed = sum(row.resolution_status == "verification_failed" for row in rows)
    searchable = max(1, len(rows) - search_failed)
    return VerificationMetrics(
        tracked_candidates=len(rows),
        tier1_verified=verified,
        awaiting_tier1=len(pending),
        average_awaiting_hours=round(sum(ages) / len(ages), 1) if ages else 0.0,
        oldest_awaiting_hours=round(max(ages), 1) if ages else 0.0,
        first_party_candidate_found=candidate_found,
        no_first_party_candidate=no_candidate,
        search_failed=search_failed,
        verification_failed=verification_failed,
        first_party_candidate_yield=round(candidate_found / searchable, 3),
        tier1_verification_yield=round(verified / searchable, 3),
    )


def run(
    candidates_path: Path = Path("data/world-gaps.json"),
    verification_path: Path = Path("data/world-verifications.json"),
    official_leads_path: Path = Path("data/world-official-leads.json"),
    history_path: Path = Path("data/world-verification-history.json"),
    metrics_path: Path = Path("data/world-verification-metrics.json"),
    *,
    now: datetime | None = None,
) -> VerificationMetrics:
    now = now or datetime.now(timezone.utc)
    candidates = load_candidates(candidates_path)
    verification = load_verifications(verification_path)
    official_leads = _load_official_leads(official_leads_path)
    existing = _load_history(history_path)
    rows = update_history(candidates, verification, existing, now=now, official_leads=official_leads)
    summary = metrics(rows, now=now)
    history_path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    metrics_path.write_text(json.dumps(asdict(summary), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Tier-1 tracker: {summary.tier1_verified} verified, {summary.awaiting_tier1} unresolved; "
        f"official candidates for {summary.first_party_candidate_found}/{summary.tracked_candidates}, "
        f"no candidate {summary.no_first_party_candidate}, verification failed {summary.verification_failed}, "
        f"search failed {summary.search_failed}; average unresolved {summary.average_awaiting_hours}h."
    )
    return summary


if __name__ == "__main__":
    run()
