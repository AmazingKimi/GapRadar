from gapradar.officialfinder import OfficialSourceLead
from gapradar.worldofficial import _claim_target_alignment, verify_official_lead
from gapradar.worldscan import GapCandidate


def _candidate() -> GapCandidate:
    return GapCandidate(
        id="x",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at=None,
        source="news",
        headline="Massachusetts will require data centers to use clean energy",
        url="https://example.com/news",
        summary="The state will require data centers to meet a new clean-energy requirement.",
        change_type="regulatory_shift",
        matched_signal="will require",
        recommendation="WATCH",
        why_now="mandatory work",
        gap_hypothesis="compliance workflow",
        validation_status="NEWS SIGNAL",
        validation_summary="lead only",
        sector="Energy & Climate",
    )


def test_missing_first_party_candidates_never_verify():
    lead = OfficialSourceLead("x", "not_found", "query", [], [], "adequate", [], ["query"])
    fact = verify_official_lead(_candidate(), lead)
    assert fact.status == "unverified"
    assert fact.official_url is None


def test_news_url_cannot_become_tier1_even_if_supplied():
    lead = OfficialSourceLead(
        "x",
        "first_party_candidates",
        "query",
        ["https://www.reuters.com/world/example"],
        ["www.reuters.com"],
        "adequate",
        [],
        ["query"],
    )
    fact = verify_official_lead(_candidate(), lead)
    assert fact.status == "unverified"


def test_regulatory_claim_requires_target_and_outcome_phrases():
    candidate = _candidate()
    generic = "Massachusetts clean energy regulation requires utilities to comply with clean energy standards."
    specific = "Massachusetts will require data centers to use clean energy under the new regulation."
    assert _claim_target_alignment(candidate, generic) is False
    assert _claim_target_alignment(candidate, specific) is True
