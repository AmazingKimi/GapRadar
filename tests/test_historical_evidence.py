from datetime import datetime, timezone

from gapradar.models import EventType, EvidenceTier, MarketEvent, SourceEvidence
from gapradar.reaction import archived_reaction_evidence
from gapradar.supply import archived_supply_evidence


NOW = datetime(2023, 9, 18, tzinfo=timezone.utc)


def _event() -> MarketEvent:
    event = MarketEvent(
        id="unity-runtime-fee",
        product="Unity Runtime Fee",
        vendor="Unity",
        event_type=EventType.PRICE_SHOCK,
        headline="Unity pricing updates",
        summary="Unity introduces a Runtime Fee.",
        official_evidence=[
            SourceEvidence(
                tier=EvidenceTier.TIER_1_OFFICIAL,
                title="Unity pricing updates",
                url="https://unity.com/products/pricing-updates",
                publisher="Unity",
                is_official=True,
            )
        ],
    )
    return event.verify()


def test_archived_reaction_uses_live_pain_scorer():
    evidence = archived_reaction_evidence(
        _event(),
        title="Unity Runtime Fee: what alternative should we use?",
        body="We have to migrate away from Unity because the Runtime Fee is too expensive.",
        url="https://community.example/unity-runtime-fee",
        published_at=NOW,
        engagement=25,
    )
    assert evidence is not None
    assert evidence.tier == EvidenceTier.TIER_2_REACTION
    assert evidence.signal == "migration_pain"


def test_archived_unrelated_reaction_is_rejected():
    evidence = archived_reaction_evidence(
        _event(),
        title="Database migration help",
        body="We are forced to replace our database.",
        url="https://community.example/database",
        published_at=NOW,
    )
    assert evidence is None


def test_archived_supply_uses_live_supply_scorer():
    evidence = archived_supply_evidence(
        _event(),
        title="OpenUnityFeeAlternative",
        body="An alternative replacement for Unity Runtime Fee affected games and Unity migrations.",
        url="https://github.com/example/unity-fee-alternative",
        publisher="GitHub",
        observed_at=NOW,
        popularity=300,
        quality_hint=0.8,
    )
    assert evidence is not None
    assert evidence.tier == EvidenceTier.TIER_3_SUPPLY
    assert evidence.signal == "replacement_supply"
