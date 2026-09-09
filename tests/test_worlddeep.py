from gapradar.worlddeep import analyze_candidate
from gapradar.worldscan import GapCandidate
from gapradar.worldverify import WorldVerification


def lead(change_type: str = "shutdown_eol") -> GapCandidate:
    return GapCandidate(
        id="lead-1",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at="2026-09-09T00:00:00+00:00",
        source="Test News",
        headline="Acme Cloud is shutting down its developer API",
        url="https://example.com/news",
        summary="Acme says the API will stop operating.",
        change_type=change_type,
        matched_signal="shutting down",
        recommendation="WATCH",
        why_now="Provisional lead.",
        gap_hypothesis="No conclusion before verification.",
        validation_status="STRUCTURAL SIGNAL",
        validation_summary="Candidate awaiting deeper validation.",
    )


def commercial_price_lead() -> GapCandidate:
    return GapCandidate(
        id="lead-2",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at="2026-09-09T00:00:00+00:00",
        source="Test News",
        headline="Acme TV announces a major subscription price hike",
        url="https://example.com/tv-price",
        summary="The consumer streaming subscription becomes materially more expensive.",
        change_type="price_shock",
        matched_signal="price hike",
        recommendation="WATCH",
        why_now="Provisional lead.",
        gap_hypothesis="No conclusion before verification.",
        validation_status="STRUCTURAL SIGNAL",
        validation_summary="Candidate awaiting deeper validation.",
    )


def verified(candidate: GapCandidate) -> WorldVerification:
    return WorldVerification(
        candidate_id=candidate.id,
        status="tier1_verified",
        event_id="official-event",
        official_url="https://acme.example/official-change",
        match_score=9,
        reasons=["official_page"],
    )


def test_unverified_candidate_is_blocked_before_supply_search(monkeypatch):
    monkeypatch.setattr("gapradar.worlddeep._github_search", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    result = analyze_candidate(lead())
    assert result.gap_assessment == "UNVERIFIED"
    assert result.supply_status == "unassessed"
    assert result.supply_coverage == "blocked_unverified"


def test_failed_supply_search_never_becomes_gap(monkeypatch):
    row = lead()
    monkeypatch.setattr("gapradar.worlddeep._github_search", lambda *a, **k: ([], False, "timeout"))
    monkeypatch.setattr("gapradar.worlddeep._npm_search", lambda *a, **k: ([], False, "timeout"))
    result = analyze_candidate(row, verified(row))
    assert result.gap_assessment == "INSUFFICIENT COVERAGE"
    assert result.final_recommendation == "WATCH"
    assert result.supply_status == "unassessed"


def test_multiple_relevant_suppliers_downgrade_broad_gap(monkeypatch):
    row = lead()
    rows = [
        {"title": "Acme API alternative one", "url": "https://one.example", "snippet": "replacement migration tool for Acme developer API", "source": "one.example"},
        {"title": "Acme API alternative two", "url": "https://two.example", "snippet": "compatible replacement for Acme developer API", "source": "two.example"},
        {"title": "Acme API alternative three", "url": "https://three.example", "snippet": "migration platform replacing Acme API", "source": "three.example"},
    ]
    monkeypatch.setattr("gapradar.worlddeep._github_search", lambda *a, **k: (rows, True, None))
    monkeypatch.setattr("gapradar.worlddeep._npm_search", lambda *a, **k: ([], True, None))
    result = analyze_candidate(row, verified(row))
    assert result.supply_status == "served"
    assert result.gap_assessment == "LIKELY SERVED"
    assert result.final_recommendation == "DISMISS"


def test_empty_web_result_set_does_not_create_gap(monkeypatch):
    row = commercial_price_lead()
    monkeypatch.setattr("gapradar.worlddeep._web_search", lambda *a, **k: ([], True, None))
    result = analyze_candidate(row, verified(row))
    assert result.supply_status == "no_supply_detected"
    assert result.gap_assessment == "INSUFFICIENT COVERAGE"
    assert result.final_recommendation == "WATCH"


def test_broad_checked_result_set_without_relevant_supply_can_be_reviewed(monkeypatch):
    row = commercial_price_lead()
    rows = [
        {"title": f"General market result {i}", "url": f"https://site{i}.example", "snippet": "market overview", "source": f"site{i}.example"}
        for i in range(6)
    ]
    monkeypatch.setattr("gapradar.worlddeep._web_search", lambda *a, **k: (rows, True, None))
    result = analyze_candidate(row, verified(row))
    assert result.supply_candidate_count == 6
    assert result.supply_status == "no_supply_detected"
    assert result.gap_assessment == "POTENTIAL GAP"
    assert result.final_recommendation == "REVIEW"
