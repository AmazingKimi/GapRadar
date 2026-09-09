from gapradar.officialfinder import OfficialSourceLead
from gapradar.priority import build_priority_leads
from gapradar.worldscan import GapCandidate
from gapradar.worldverify import WorldVerification


def _candidate(cid: str, headline: str, change_type: str, signal: str) -> GapCandidate:
    return GapCandidate(
        id=cid,
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at="2026-09-09T00:00:00+00:00",
        source="news",
        headline=headline,
        url="https://example.com",
        summary=headline,
        change_type=change_type,
        matched_signal=signal,
        recommendation="WATCH",
        why_now="",
        gap_hypothesis="",
        validation_status="STRUCTURAL SIGNAL",
        validation_summary="",
        sector="AI & Technology",
    )


def test_high_specificity_unverified_lead_can_be_recommended_for_investigation_without_becoming_review():
    candidate = _candidate("apple", "Apple TV service price hike reaches 20% in 2026", "price_shock", "price hike")
    rows = build_priority_leads([candidate], {}, [], [])
    assert rows[0].status == "INVESTIGATE"
    assert rows[0].evidence_state == "news_only"
    assert "No acceptable first-party source" in rows[0].reason


def test_tier1_confirmation_raises_priority_but_does_not_fake_gap_review():
    candidate = _candidate("mass", "Massachusetts will require new data centers to use clean energy", "regulatory_shift", "will require")
    verification = WorldVerification(
        candidate_id="mass",
        status="tier1_verified",
        event_id=None,
        official_url="https://www.mass.gov/example",
        match_score=8,
        reasons=["official_page"],
    )
    rows = build_priority_leads([candidate], {"mass": verification}, [], [])
    assert rows[0].status == "INVESTIGATE"
    assert rows[0].evidence_state == "tier1_verified"
    assert "mass.gov" in rows[0].evidence_label


def test_weak_single_source_lead_remains_watch():
    candidate = _candidate("weak", "Small service changes terms", "regulatory_shift", "terms")
    rows = build_priority_leads([candidate], {}, [], [])
    assert rows[0].status == "WATCH"


def test_official_candidate_is_distinct_from_verified_fact():
    candidate = _candidate("ev", "EV BMS cybersecurity testing now mandatory in India", "regulatory_shift", "mandatory")
    lead = OfficialSourceLead(
        candidate_id="ev",
        status="first_party_candidates",
        query="ev bms mandatory",
        candidate_urls=["https://www.pib.gov.in/example"],
        candidate_hosts=["www.pib.gov.in"],
        search_coverage="adequate",
        errors=[],
    )
    rows = build_priority_leads([candidate], {}, [], [lead])
    assert rows[0].status == "INVESTIGATE"
    assert rows[0].evidence_state == "official_candidate"
    assert rows[0].evidence_label.startswith("Official lead")
