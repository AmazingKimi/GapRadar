from gapradar.dossier import build_dossier
from gapradar.models import EventType, EvidenceTier, MarketEvent, SourceEvidence


def official() -> SourceEvidence:
    return SourceEvidence(
        tier=EvidenceTier.TIER_1_OFFICIAL,
        title="Official retirement",
        url="https://vendor.example/eol",
        publisher="Vendor",
        is_official=True,
    )


def reaction(i: int) -> SourceEvidence:
    return SourceEvidence(
        tier=EvidenceTier.TIER_2_REACTION,
        title=f"Need replacement {i}",
        url=f"https://community.example/{i}",
        publisher="Community",
        signal="migration_pain",
        signal_score=7,
    )


def supply() -> SourceEvidence:
    return SourceEvidence(
        tier=EvidenceTier.TIER_3_SUPPLY,
        title="Replacement",
        url="https://replacement.example",
        publisher="Directory",
        signal="replacement_supply",
        signal_score=8,
    )


def make_event(**kwargs) -> MarketEvent:
    event = MarketEvent(
        id="event-1",
        product="Example Product",
        vendor="Example",
        event_type=EventType.SHUTDOWN,
        headline="Example Product is shutting down",
        summary="The vendor says the product will stop operating.",
        official_evidence=[official()],
        **kwargs,
    )
    return event.verify()


def test_no_demand_becomes_pass():
    event = make_event()
    event.reaction_checked_at = event.detected_at
    event.verify()
    dossier = build_dossier(event)
    assert dossier.verdict == "PASS"
    assert "Do not build" in dossier.next_action


def test_repeated_demand_and_no_supply_becomes_review():
    event = make_event(reaction_evidence=[reaction(1), reaction(2), reaction(3)])
    event.reaction_checked_at = event.detected_at
    event.supply_checked_at = event.detected_at
    event.verify()
    dossier = build_dossier(event)
    assert event.gap_status == "potential_gap"
    assert dossier.verdict == "REVIEW"
    assert dossier.evidence_counts["tier_2_reaction"] == 3


def test_served_gap_is_not_recommended():
    event = make_event(reaction_evidence=[reaction(1), reaction(2), reaction(3)], supply_evidence=[supply()])
    event.reaction_checked_at = event.detected_at
    event.supply_checked_at = event.detected_at
    event.verify()
    dossier = build_dossier(event)
    assert event.gap_status == "likely_served"
    assert dossier.verdict == "LIKELY SERVED"
