from gapradar.worldquality import PROVISIONAL_GAP, PROVISIONAL_WHY, collapse_duplicate_events, refine_candidate, rejection_reason
from gapradar.worldscan import GapCandidate


def candidate(headline: str, change_type: str, summary: str = "", source: str = "test") -> GapCandidate:
    return GapCandidate(
        id=(headline + source)[:16],
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at="2026-09-09T00:00:00+00:00",
        source=source,
        headline=headline,
        url=f"https://example.com/{source}",
        summary=summary or headline,
        change_type=change_type,
        matched_signal="test",
        recommendation="REVIEW",
        why_now="old template",
        gap_hypothesis="old template",
        validation_status="STRUCTURAL SIGNAL",
        validation_summary="candidate",
        sector="Other",
    )


def test_rejects_rhetorical_shutdown_headline():
    row = candidate(
        "From Shutdown to Showcase: Holtec's IPO Puts Palisades at Center of Nuclear Industry's Future",
        "shutdown_eol",
    )
    assert rejection_reason(row) == "rhetorical_shutdown_context"
    assert refine_candidate(row) is None


def test_rejects_physical_power_shutdown_without_product_target():
    row = candidate("Ossiomo Power shutdown weakens businesses and SMEs", "shutdown_eol")
    assert rejection_reason(row) == "physical_shutdown_not_product_eol"


def test_rejects_negated_mandate():
    row = candidate("Hyundai's 60% Electrified Target Isn't an EV Mandate", "regulatory_shift")
    assert rejection_reason(row) == "negated_mandate"


def test_rejects_commercial_investment_mandate():
    row = candidate("Brookfield wins $1 billion mandate from UK's Nuclear Liabilities Fund", "regulatory_shift")
    assert rejection_reason(row) == "commercial_mandate_not_regulation"


def test_rejects_speculative_or_promised_regulation_before_tier1_search():
    assert rejection_reason(candidate("India May Mandate Storage For Solar, Wind Projects From 2027", "regulatory_shift")) == "speculative_or_proposed_regulation"
    assert rejection_reason(candidate("Labour promises new rules for data centre electricity use", "regulatory_shift")) == "speculative_or_proposed_regulation"
    assert rejection_reason(candidate("Tories launch bid to revoke ZEV mandate", "regulatory_shift")) == "speculative_or_proposed_regulation"


def test_keeps_real_regulatory_requirement_but_does_not_promote_it_to_opportunity():
    row = candidate("Massachusetts Will Require New Data Centers to Use Clean Energy", "regulatory_shift")
    refined = refine_candidate(row)
    assert refined is not None
    assert refined.recommendation == "WATCH"
    assert refined.why_now == PROVISIONAL_WHY
    assert refined.gap_hypothesis == PROVISIONAL_GAP


def test_keeps_product_shutdown():
    row = candidate("Podcast app will shut down next month", "shutdown_eol")
    assert refine_candidate(row) is not None


def test_semantic_dedup_collapses_same_event_from_different_feeds():
    left = candidate(
        "Labour promises new rules for data centre electricity use and coordinated AI policy",
        "regulatory_shift",
        source="feed-a",
    )
    right = candidate(
        "Labour promises coordinated AI policy and new rules for data centre electricity use",
        "regulatory_shift",
        source="feed-b",
    )
    rows, collapsed = collapse_duplicate_events([left, right])
    assert len(rows) == 1
    assert collapsed == 1


def test_semantic_dedup_keeps_distinct_events():
    left = candidate("Massachusetts requires new data centers to use clean energy", "regulatory_shift")
    right = candidate("India makes EV BMS cybersecurity testing mandatory", "regulatory_shift")
    rows, collapsed = collapse_duplicate_events([left, right])
    assert len(rows) == 2
    assert collapsed == 0
