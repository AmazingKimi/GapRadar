from datetime import datetime, timezone

from gapradar.models import EvidenceTier, EventType, MarketEvent, SourceEvidence
from gapradar.worldscan import GapCandidate
from gapradar.worldverify import score_match, verify_candidate


def _event() -> MarketEvent:
    event = MarketEvent(
        id="shopify-cli",
        product="Shopify Theme CLI",
        vendor="Shopify",
        event_type=EventType.SHUTDOWN,
        headline="Older Shopify Theme CLI versions will no longer be supported",
        summary="Theme CLI versions 3.83.x and earlier lose support.",
        event_date=datetime(2026, 8, 27, tzinfo=timezone.utc),
    )
    event.official_evidence.append(
        SourceEvidence(
            tier=EvidenceTier.TIER_1_OFFICIAL,
            title="Shopify changelog",
            url="https://shopify.dev/changelog/theme-cli-deprecation",
            publisher="Shopify",
            published_at=event.event_date,
            excerpt="Older Theme CLI versions are deprecated.",
            is_official=True,
        )
    )
    event.verify()
    return event


def _candidate(headline: str, summary: str = "Shopify Theme CLI versions 3.83.x and older will no longer be supported.") -> GapCandidate:
    return GapCandidate(
        id="candidate-1",
        discovered_at="2026-08-28T00:00:00+00:00",
        published_at="2026-08-27T18:00:00+00:00",
        source="news",
        headline=headline,
        url="https://example.com/story",
        summary=summary,
        change_type="shutdown_eol",
        matched_signal="deprecated",
        recommendation="WATCH",
        why_now="workflow disruption",
        gap_hypothesis="migration tooling",
        validation_status="NEWS SIGNAL",
        validation_summary="candidate only",
        sector="AI & Technology",
    )


def test_verified_event_can_bridge_matching_world_candidate():
    result = verify_candidate(_candidate("Shopify deprecates older Theme CLI versions"), [_event()])
    assert result.status == "tier1_verified"
    assert result.event_id == "shopify-cli"
    assert result.official_url == "https://shopify.dev/changelog/theme-cli-deprecation"
    assert result.match_score >= 6


def test_event_type_without_subject_identity_cannot_verify_candidate():
    candidate = _candidate(
        "Another vendor is shutting down an unrelated platform",
        "A different product will no longer be supported next month.",
    )
    score, _ = score_match(candidate, _event())
    result = verify_candidate(candidate, [_event()])
    assert score < 6
    assert result.status == "unverified"
    assert result.official_url is None
