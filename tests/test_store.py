from gapradar.models import EventType, EvidenceTier, MarketEvent, SourceEvidence
from gapradar.store import merge_events


def _event(event_id: str, title: str, summary: str, event_type: EventType) -> MarketEvent:
    event = MarketEvent(
        id=event_id,
        product=title,
        vendor="Shopify",
        event_type=event_type,
        headline=title,
        summary=summary,
        official_evidence=[
            SourceEvidence(
                tier=EvidenceTier.TIER_1_OFFICIAL,
                title=title,
                url=f"https://shopify.dev/changelog/{event_id}",
                publisher="Shopify",
                excerpt=summary,
                is_official=True,
            )
        ],
    )
    return event.verify()


def test_revalidation_drops_event_that_no_longer_matches_live_rules():
    stale = _event(
        "stale",
        "Oxygen is now available on trial plan stores",
        "Previously Oxygen hosting required a paid plan.",
        EventType.PRICE_SHOCK,
    )
    rows = merge_events([stale], [], revalidate_existing=True)
    assert rows == []


def test_revalidation_keeps_explicit_deprecation():
    real = _event(
        "real",
        "Script tags are deprecated and will stop running",
        "Script tags will stop running.",
        EventType.SHUTDOWN,
    )
    rows = merge_events([real], [], revalidate_existing=True)
    assert [row.id for row in rows] == ["real"]
