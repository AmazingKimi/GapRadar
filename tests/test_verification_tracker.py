from datetime import datetime, timezone

from gapradar.verification_tracker import VerificationHistoryRow, metrics, update_history
from gapradar.worldscan import GapCandidate


def _candidate() -> GapCandidate:
    return GapCandidate(
        id="c1",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at="2026-09-09T00:00:00+00:00",
        source="test",
        headline="Example structural change",
        url="https://example.com",
        summary="summary",
        change_type="regulatory_shift",
        matched_signal="signal",
        recommendation="WATCH",
        why_now="provisional",
        gap_hypothesis="provisional",
        validation_status="STRUCTURAL SIGNAL",
        validation_summary="candidate",
        sector="AI & Technology",
    )


class Verification:
    def __init__(self, status: str):
        self.status = status


def test_tracker_preserves_first_seen_and_measures_pending_age():
    existing = {
        "c1": VerificationHistoryRow(
            candidate_id="c1",
            headline="old",
            first_seen_at="2026-09-09T00:00:00+00:00",
            last_seen_at="2026-09-09T01:00:00+00:00",
            status="unverified",
            verified_at=None,
        )
    }
    now = datetime(2026, 9, 9, 6, tzinfo=timezone.utc)
    rows = update_history([_candidate()], {"c1": Verification("unverified")}, existing, now=now)
    summary = metrics(rows, now=now)
    assert rows[0].first_seen_at == "2026-09-09T00:00:00+00:00"
    assert summary.awaiting_tier1 == 1
    assert summary.average_awaiting_hours == 6.0
    assert summary.oldest_awaiting_hours == 6.0


def test_tracker_records_first_verification_time():
    now = datetime(2026, 9, 9, 6, tzinfo=timezone.utc)
    rows = update_history([_candidate()], {"c1": Verification("tier1_verified")}, {}, now=now)
    assert rows[0].verified_at == "2026-09-09T06:00:00+00:00"
    assert metrics(rows, now=now).tier1_verified == 1
