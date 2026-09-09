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


def test_no_detected_demand_is_not_pass():
    event = make_event()
    event.reaction_checked_at = event.detected_at
    event.reaction_search_quality = "adequate"
    event.reaction_queries = [{"source": "forum", "query": "Example Product migration", "candidate_count": 0, "ok": True}]
    event.verify()
    dossier = build_dossier(event)
    assert dossier.verdict == "NO DETECTED SIGNAL"
    assert "not that demand does not exist" in dossier.rationale
    assert dossier.reaction_queries


def test_failed_search_is_not_mapped_to_no_signal():
    event = make_event()
    event.reaction_checked_at = event.detected_at
    event.reaction_search_quality = "failed"
    event.verify()
    dossier = build_dossier(event)
    assert event.demand_status == "unassessed"
    assert dossier.verdict == "SEARCH FAILED"


def test_repeated_demand_and_no_supply_becomes_review():
    event = make_event(reaction_evidence=[reaction(1), reaction(2), reaction(3)])
    event.reaction_checked_at = event.detected_at
    event.reaction_search_quality = "adequate"
    event.supply_checked_at = event.detected_at
    event.verify()
    dossier = build_dossier(event)
    assert event.gap_status == "potential_gap"
    assert dossier.verdict == "REVIEW"
    assert dossier.evidence_counts["tier_2_reaction"] == 3


def test_served_gap_is_not_recommended():
    event = make_event(reaction_evidence=[reaction(1), reaction(2), reaction(3)], supply_evidence=[supply()])
    event.reaction_checked_at = event.detected_at
    event.reaction_search_quality = "adequate"
    event.supply_checked_at = event.detected_at
    event.verify()
    dossier = build_dossier(event)
    assert event.gap_status == "likely_served"
    assert dossier.verdict == "LIKELY SERVED"
