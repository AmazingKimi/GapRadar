from datetime import datetime, timezone

import pytest

from gapradar.models import Confidence, EventType, EvidenceTier, MarketEvent, SourceEvidence

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


def official_evidence() -> SourceEvidence:
    return SourceEvidence(
        tier=EvidenceTier.TIER_1_OFFICIAL,
        title="Service retirement",
        url="https://example.com/retirement",
        publisher="Example",
        is_official=True,
    )


def reaction(title: str) -> SourceEvidence:
    return SourceEvidence(
        tier=EvidenceTier.TIER_2_REACTION,
        title=title,
        url=f"https://community.example.net/{title.lower()}",
        publisher="Community",
        signal="migration_pain",
        signal_score=4,
    )


def supply(score: int = 5, suffix: str = "one") -> SourceEvidence:
    return SourceEvidence(
        tier=EvidenceTier.TIER_3_SUPPLY,
        title="Alternative",
        url=f"https://directory.example.net/{suffix}",
        publisher="Directory",
        signal="replacement_supply",
        signal_score=score,
    )


def make_event(**kwargs) -> MarketEvent:
    return MarketEvent(
        id="event-1",
        product="Example",
        vendor="Example Inc",
        event_type=EventType.SHUTDOWN,
        headline="Example is shutting down",
        summary="Official shutdown notice",
        **kwargs,
    )


def test_no_official_source_never_verifies():
    event = make_event().verify()
    assert event.status == "candidate"
    assert event.confidence == Confidence.INSUFFICIENT
    assert event.demand_hypothesis is None


def test_verified_event_creates_explicit_low_confidence_hypothesis():
    event = make_event(official_evidence=[official_evidence()]).verify()
    assert event.status == "verified"
    assert event.confidence == Confidence.WEAK
    assert event.gap_status == "unassessed"
    assert event.demand_hypothesis is not None
    assert event.demand_hypothesis.confidence == "low"
    assert event.demand_hypothesis.basis


def test_failed_reaction_search_does_not_delete_hypothesis():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_checked_at=NOW,
        reaction_search_quality="failed",
    ).verify()
    assert event.demand_status == "unassessed"
    assert event.demand_hypothesis is not None
    assert event.demand_hypothesis.confidence == "low"


def test_no_reaction_signal_can_still_be_watch_if_supply_is_thin():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_checked_at=NOW,
        reaction_search_quality="adequate",
        supply_evidence=[supply()],
        supply_checked_at=NOW,
    ).verify()
    assert event.demand_status == "no_signal"
    assert event.demand_hypothesis is not None
    assert event.demand_hypothesis.confidence == "low"
    assert event.supply_status == "thin_supply"
    assert event.gap_status == "watch"


def test_reaction_increases_hypothesis_confidence():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_evidence=[reaction("A")],
        reaction_checked_at=NOW,
        reaction_search_quality="adequate",
    ).verify()
    assert event.demand_hypothesis is not None
    assert event.demand_hypothesis.confidence == "medium"


def test_repeated_demand_plus_thin_supply_becomes_potential_gap():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_evidence=[reaction("A"), reaction("B"), reaction("C")],
        reaction_checked_at=NOW,
        reaction_search_quality="adequate",
        supply_evidence=[supply()],
        supply_checked_at=NOW,
    ).verify()
    assert event.demand_status == "repeated_signal"
    assert event.demand_hypothesis is not None
    assert event.demand_hypothesis.confidence == "high"
    assert event.supply_status == "thin_supply"
    assert event.gap_status == "potential_gap"
    assert event.confidence == Confidence.STRONG


def test_strong_replacement_supply_marks_market_likely_served_even_without_reaction():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_checked_at=NOW,
        reaction_search_quality="adequate",
        supply_evidence=[supply(8)],
        supply_checked_at=NOW,
    ).verify()
    assert event.demand_status == "no_signal"
    assert event.supply_status == "served"
    assert event.gap_status == "likely_served"


def test_non_official_item_cannot_enter_official_evidence():
    with pytest.raises(ValueError):
        make_event(
            official_evidence=[
                SourceEvidence(
                    tier=EvidenceTier.TIER_2_REACTION,
                    title="Rumor",
                    url="https://forum.example.net/rumor",
                    publisher="Forum",
                )
            ]
        )
