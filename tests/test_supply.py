from datetime import datetime, timezone

from gapradar.models import EventType, EvidenceTier, MarketEvent, SourceEvidence
from gapradar.supply import SupplyCandidate, dedupe, score_supply

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


def event() -> MarketEvent:
    return MarketEvent(
        id="e1",
        product="Shopify Script Tags",
        vendor="Shopify",
        event_type=EventType.SHUTDOWN,
        headline="Script tags are deprecated",
        summary="Official change",
        official_evidence=[
            SourceEvidence(
                tier=EvidenceTier.TIER_1_OFFICIAL,
                title="Official",
                url="https://shopify.dev/changelog/example",
                publisher="Shopify",
                is_official=True,
            )
        ],
    )


def test_irrelevant_popular_repo_is_rejected():
    candidate = SupplyCandidate(
        title="popular/tool",
        url="https://github.com/popular/tool",
        publisher="GitHub Repositories",
        source_kind="github_repository",
        description="A popular database migration utility",
        popularity=50000,
        updated_at=NOW,
    )
    assert score_supply(candidate, event(), now=NOW) == 0


def test_same_ecosystem_package_is_not_automatically_a_replacement():
    candidate = SupplyCandidate(
        title="@shopify/graphql-client",
        url="https://www.npmjs.com/package/@shopify/graphql-client",
        publisher="npm",
        source_kind="npm_package",
        description="A Shopify client for Storefront API scripts and app integrations",
        popularity=1000,
        quality_hint=0.9,
        updated_at=NOW,
    )
    assert score_supply(candidate, event(), now=NOW) == 0


def test_active_relevant_alternative_scores_high():
    candidate = SupplyCandidate(
        title="acme/shopify-script-tag-alternative",
        url="https://github.com/acme/shopify-script-tag-alternative",
        publisher="GitHub Repositories",
        source_kind="github_repository",
        description="Alternative replacement for Shopify script tags using theme extensions",
        popularity=420,
        updated_at=NOW,
    )
    assert score_supply(candidate, event(), now=NOW) >= 7


def test_archived_replacement_is_penalized():
    active = SupplyCandidate(
        title="shopify-script-tags-replacement",
        url="https://github.com/acme/active",
        publisher="GitHub Repositories",
        source_kind="github_repository",
        description="Replacement alternative for Shopify Script Tags",
        popularity=50,
        updated_at=NOW,
    )
    archived = SupplyCandidate(
        title=active.title,
        url="https://github.com/acme/archived",
        publisher=active.publisher,
        source_kind=active.source_kind,
        description=active.description,
        popularity=50,
        updated_at=NOW,
        archived=True,
    )
    assert score_supply(active, event(), now=NOW) > score_supply(archived, event(), now=NOW)


def test_dedupe_keeps_more_popular_duplicate():
    low = SupplyCandidate("one", "https://github.com/acme/x", "GitHub", "github_repository", "x", popularity=1)
    high = SupplyCandidate("two", "https://github.com/acme/x/", "GitHub", "github_repository", "x", popularity=20)
    rows = dedupe([low, high])
    assert len(rows) == 1
    assert rows[0].popularity == 20
