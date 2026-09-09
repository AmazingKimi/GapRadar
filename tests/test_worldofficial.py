from gapradar.officialfinder import OfficialSourceLead
from gapradar.worldofficial import _claim_target_alignment, verify_official_lead
from gapradar.worldscan import GapCandidate


def _candidate(headline: str = "Massachusetts will require data centers to use clean energy") -> GapCandidate:
    return GapCandidate(
        id="x",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at=None,
        source="news",
        headline=headline,
        url="https://example.com/news",
        summary="Structural regulatory change.",
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


def test_regulatory_claim_requires_target_outcome_and_local_mandatory_language():
    candidate = _candidate()
    generic = "Massachusetts clean energy regulation requires utilities to comply. Far elsewhere the report discusses data centers and clean energy investment."
    advisory = "The statement discusses data centers and clean energy. The administration encourages responsible development and offers guidance."
    specific = "Massachusetts will require data centers to use clean energy under the new standard."
    assert _claim_target_alignment(candidate, generic) is False
    assert _claim_target_alignment(candidate, advisory) is False
    assert _claim_target_alignment(candidate, specific) is True


def test_bms_advisory_is_not_equivalent_to_mandatory_testing():
    candidate = _candidate("EV BMS Cybersecurity Testing Now Mandatory in India")
    advisory = "CERT-In identified cybersecurity vulnerabilities in BMS devices. MHI issued an advisory to industry bodies and testing agencies."
    mandatory = "Cybersecurity testing of BMS is mandatory before certification and market approval."
    assert _claim_target_alignment(candidate, advisory) is False
    assert _claim_target_alignment(candidate, mandatory) is True
