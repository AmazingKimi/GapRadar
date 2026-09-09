from datetime import date, datetime, timezone

from gapradar.discovery import DiscoveryAudit, _candidate_in_event_window, _reaction_query_subset, apply_discovered_supply, summarize
from gapradar.models import EvidenceTier, EventType, MarketEvent, SourceEvidence
from gapradar.reaction import ReactionCandidate
from gapradar.supply import SupplyCandidate


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


def _verified_event() -> MarketEvent:
    event = _event()
    event.official_evidence.append(
        SourceEvidence(
            tier=EvidenceTier.TIER_1_OFFICIAL,
            title="Heroku's Next Chapter",
            url="https://blog.heroku.com/next-chapter",
            publisher="Heroku",
            published_at=event.event_date,
            excerpt="Heroku free plans are ending.",
            is_official=True,
        )
    )
    event.verify()
    return event


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


def test_supply_discovery_runs_without_reaction_signal():
    event = _verified_event()
    assert event.demand_hypothesis is not None
    assert event.demand_status == "unassessed"
    candidate = SupplyCandidate(
        title="Heroku migration replacement",
        url="https://github.com/example/heroku-migration",
        publisher="GitHub Repositories",
        source_kind="github_repository",
        description="Alternative platform and migration tool for Heroku applications and free plan users.",
        updated_at=datetime(2022, 8, 30, tzinfo=timezone.utc),
        popularity=0,
        archived=False,
    )
    audit = DiscoveryAudit("github_supply", "query", True, 1)
    apply_discovered_supply(event, [candidate], audit, as_of=date(2022, 9, 1))
    assert event.supply_checked_at is not None
    assert event.supply_candidate_count == 1
    assert event.supply_status != "unassessed"


def test_summary_reports_self_discovery_recall_without_hiding_failures():
    rows = [
        {
            "status": "evaluated",
            "cohort": "headline",
            "ground_truth_demand": "yes",
            "demand_status": "early_signal",
            "reaction_search_quality": "adequate",
            "missing_reaction_sources": [],
            "supply_audit": {},
        },
        {
            "status": "evaluated",
            "cohort": "medium",
            "ground_truth_demand": "yes",
            "demand_status": "unassessed",
            "reaction_search_quality": "failed",
            "missing_reaction_sources": ["vendor_community"],
            "supply_audit": {},
        },
    ]
    metrics = summarize(rows)
    assert metrics["demand_recall"] == 0.5
    assert metrics["search_failed"] == 1
    assert metrics["coverage_degraded"] == 1
    assert metrics["supply_runs"] == 2
    assert metrics["by_cohort"]["headline"]["demand_recall"] == 1.0
    assert metrics["by_cohort"]["medium"]["demand_recall"] == 0.0
