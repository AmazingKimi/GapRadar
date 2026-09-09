from datetime import date

from gapradar.discovery import _reaction_query_subset, summarize
from gapradar.models import EventType, MarketEvent


def _event() -> MarketEvent:
    return MarketEvent(
        id="x",
        product="Heroku Free Plans",
        vendor="Heroku",
        event_type=EventType.PRICE_SHOCK,
        headline="Heroku free plans are ending",
        summary="Free plans will end.",
    )


def test_discovery_queries_are_bounded_and_vendor_aware():
    queries = _reaction_query_subset(_event())
    assert 1 <= len(queries) <= 6
    assert any("Heroku" in query for query in queries)


def test_summary_reports_self_discovery_recall_without_hiding_failures():
    rows = [
        {
            "status": "evaluated",
            "ground_truth_demand": "yes",
            "demand_status": "early_signal",
            "reaction_search_quality": "adequate",
            "supply_audit": None,
        },
        {
            "status": "evaluated",
            "ground_truth_demand": "yes",
            "demand_status": "unassessed",
            "reaction_search_quality": "failed",
            "supply_audit": None,
        },
    ]
    metrics = summarize(rows)
    assert metrics["demand_recall"] == 0.5
    assert metrics["search_failed"] == 1
