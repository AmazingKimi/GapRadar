import pytest

from gapradar.models import (
    Confidence,
    EventType,
    EvidenceTier,
    MarketEvent,
    SourceEvidence,
)


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
        url="https://community.example.net/post",
        publisher="Community",
    )


def supply() -> SourceEvidence:
    return SourceEvidence(
        tier=EvidenceTier.TIER_3_SUPPLY,
        title="Alternatives",
        url="https://directory.example.net/alternatives",
        publisher="Directory",
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


def test_reaction_makes_signal_emerging():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_evidence=[reaction("Need an alternative")],
    ).verify()
    assert event.confidence == Confidence.EMERGING


def test_strong_requires_reaction_and_supply_evidence():
    event = make_event(
        official_evidence=[official_evidence()],
        reaction_evidence=[reaction("A"), reaction("B"), reaction("C")],
        supply_evidence=[supply()],
    ).verify()
    assert event.confidence == Confidence.STRONG


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
