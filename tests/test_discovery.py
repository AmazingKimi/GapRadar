from datetime import date, datetime, timezone

from gapradar.discovery import _candidate_in_event_window, _reaction_query_subset, summarize
from gapradar.models import EventType, MarketEvent
from gapradar.reaction import ReactionCandidate


def _event() -> MarketEvent:
    return MarketEvent(
        id="x",
        product="Heroku Free Plans",
        vendor="Heroku",
        event_type=EventType.PRICE_SHOCK,
        headline="Heroku free plans are ending",
        summary="Free plans will end.",
        event_date=datetime(2022, 8, 25, tzinfo=timezone.utc),
    )


def test_discovery_queries_are_bounded_and_vendor_aware():
    queries = _reaction_query_subset(_event())
    assert 1 <= len(queries) <= 6
    assert any("Heroku" in query for query in queries)


def test_pre_event_reaction_is_not_counted_as_displacement():
    event = _event()
    before = ReactionCandidate(
        title="Old migration",
        url="https://example.com/old",
        publisher="test",
        source_kind="test",
        published_at=datetime(2022, 8, 1, tzinfo=timezone.utc),
        excerpt="Heroku alternative migration",
    )
    after = ReactionCandidate(
        title="New migration",
        url="https://example.com/new",
        publisher="test",
        source_kind="test",
        published_at=datetime(2022, 8, 26, tzinfo=timezone.utc),
        excerpt="Heroku alternative migration",
    )
    assert _candidate_in_event_window(before, event, date(2022, 9, 1)) is False
    assert _candidate_in_event_window(after, event, date(2022, 9, 1)) is True


def test_summary_reports_self_discovery_recall_without_hiding_failures():
    rows = [
        {
            "status": "evaluated",
            "cohort": "headline",
            "ground_truth_demand": "yes",
            "demand_status": "early_signal",
            "reaction_search_quality": "adequate",
            "missing_reaction_sources": [],
            "supply_audit": None,
        },
        {
            "status": "evaluated",
            "cohort": "medium",
            "ground_truth_demand": "yes",
            "demand_status": "unassessed",
            "reaction_search_quality": "failed",
            "missing_reaction_sources": ["vendor_community"],
            "supply_audit": None,
        },
    ]
    metrics = summarize(rows)
    assert metrics["demand_recall"] == 0.5
    assert metrics["search_failed"] == 1
    assert metrics["coverage_degraded"] == 1
    assert metrics["by_cohort"]["headline"]["demand_recall"] == 1.0
    assert metrics["by_cohort"]["medium"]["demand_recall"] == 0.0
