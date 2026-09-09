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


def test_official_only_is_verified_but_weak():
    event = make_event(official_evidence=[official_evidence()]).verify()
    assert event.status == "verified"
    assert event.confidence == Confidence.WEAK
    assert event.gap_status == "unassessed"


def test_no_demand_never_becomes_gap_even_when_supply_is_empty():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_checked_at=NOW,
        supply_checked_at=NOW,
    ).verify()
    assert event.demand_status == "no_signal"
    assert event.supply_status == "no_supply"
    assert event.gap_status == "no_demand"


def test_repeated_demand_plus_thin_supply_becomes_potential_gap():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_evidence=[reaction("A"), reaction("B"), reaction("C")],
        supply_evidence=[supply()],
        reaction_checked_at=NOW,
        supply_checked_at=NOW,
    ).verify()
    assert event.demand_status == "repeated_signal"
    assert event.supply_status == "thin_supply"
    assert event.gap_status == "potential_gap"
    assert event.confidence == Confidence.STRONG


def test_strong_replacement_supply_marks_market_likely_served():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_evidence=[reaction("A"), reaction("B"), reaction("C")],
        supply_evidence=[supply(8)],
        reaction_checked_at=NOW,
        supply_checked_at=NOW,
    ).verify()
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
