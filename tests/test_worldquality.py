from gapradar.worldquality import PROVISIONAL_GAP, PROVISIONAL_WHY, refine_candidate, rejection_reason
from gapradar.worldscan import GapCandidate


def candidate(headline: str, change_type: str, summary: str = "") -> GapCandidate:
    return GapCandidate(
        id="x",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at="2026-09-09T00:00:00+00:00",
        source="test",
        headline=headline,
        url="https://example.com",
        summary=summary,
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
