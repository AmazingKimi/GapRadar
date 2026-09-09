from datetime import datetime, timezone

from gapradar.models import EventType, EvidenceTier, MarketEvent, SourceEvidence
from gapradar.reaction import (
    ReactionCandidate,
    canonical_url,
    dedupe_candidates,
    github_issue_queries,
    hacker_news_queries,
    is_migration_pain,
    score_migration_pain,
)


def _event() -> MarketEvent:
    event = MarketEvent(
        id="evt",
        product="Script tags",
        vendor="Shopify",
        event_type=EventType.SHUTDOWN,
        headline="Script tags are deprecated and will stop running",
        summary="Official change.",
        official_evidence=[
            SourceEvidence(
                tier=EvidenceTier.TIER_1_OFFICIAL,
                title="Official notice",
                url="https://shopify.dev/changelog/example",
                publisher="Shopify",
                is_official=True,
            )
        ],
    )
    event.verify()
    return event


def test_forced_migration_is_kept():
    candidate = ReactionCandidate(
        title="What should we use instead of Shopify Script tags?",
        url="https://example.com/thread/1",
        publisher="Forum",
        source_kind="forum",
        published_at=datetime.now(timezone.utc),
        excerpt="We have to migrate because script tags will stop working. Looking for an alternative.",
        engagement=8,
    )
    assert score_migration_pain(candidate, _event()) >= 3
    assert is_migration_pain(candidate, _event())


def test_ordinary_product_discussion_is_rejected():
    candidate = ReactionCandidate(
        title="Useful patterns for Shopify Script tags",
        url="https://example.com/thread/2",
        publisher="Forum",
        source_kind="forum",
        published_at=datetime.now(timezone.utc),
        excerpt="Here are implementation tips and examples.",
        engagement=50,
    )
    assert score_migration_pain(candidate, _event()) < 3
    assert not is_migration_pain(candidate, _event())


def test_unrelated_migration_is_rejected_even_if_painful():
    candidate = ReactionCandidate(
        title="We are forced to migrate our database",
        url="https://example.com/thread/3",
        publisher="Forum",
        source_kind="forum",
        published_at=datetime.now(timezone.utc),
        excerpt="Everything is broken and we need an alternative immediately.",
        engagement=100,
    )
    assert score_migration_pain(candidate, _event()) == 0


def test_generic_script_noise_without_product_phrase_is_rejected():
    candidate = ReactionCandidate(
        title="HTML script loading issue",
        url="https://example.com/thread/4",
        publisher="Forum",
        source_kind="forum",
        published_at=datetime.now(timezone.utc),
        excerpt="Need to migrate a script loader because it is broken.",
        engagement=100,
    )
    assert score_migration_pain(candidate, _event()) == 0


def test_query_plan_contains_broad_and_event_queries():
    event = _event()
    hn = hacker_news_queries(event)
    gh = github_issue_queries(event, "2026-05-01")
    assert "Script tags" in hn
    assert any("deprecated" in query for query in hn)
    assert any('"Script tags" Shopify' in query for query in gh)
    assert any("migration" in query for query in gh)


def test_canonical_url_drops_tracking_and_dedupes():
    a = ReactionCandidate("A", "https://example.com/x/?utm_source=a", "X", "forum", None, "", 1)
    b = ReactionCandidate("B", "https://example.com/x#reply", "X", "forum", None, "", 9)
    assert canonical_url(a.url) == "https://example.com/x"
    rows = dedupe_candidates([a, b])
    assert len(rows) == 1
    assert rows[0].title == "B"


def test_failed_search_does_not_become_no_signal():
    event = _event()
    event.reaction_checked_at = datetime.now(timezone.utc)
    event.reaction_search_quality = "failed"
    event.verify()
    assert event.demand_status == "unassessed"


def test_verify_sets_no_signal_only_after_adequate_search():
    event = _event()
    assert event.demand_status == "unassessed"
    event.reaction_checked_at = datetime.now(timezone.utc)
    event.reaction_search_quality = "adequate"
    event.verify()
    assert event.demand_status == "no_signal"

    event.reaction_evidence = [
        SourceEvidence(
            tier=EvidenceTier.TIER_2_REACTION,
            title="Need to migrate Script tags",
            url="https://example.com/reaction",
            publisher="Forum",
            is_official=False,
            signal="migration_pain",
            signal_score=5,
        )
    ]
    event.verify()
    assert event.demand_status == "early_signal"
    assert event.confidence.value == "emerging"
