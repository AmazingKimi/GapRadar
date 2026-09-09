from gapradar.worlddeep import analyze_candidate
from gapradar.worldscan import GapCandidate


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
        recommendation="REVIEW",
        why_now="Users must migrate.",
        gap_hypothesis="Look for compatible replacements.",
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
        recommendation="REVIEW",
        why_now="Price-sensitive users may switch.",
        gap_hypothesis="Look for lower-cost substitutes.",
        validation_status="STRUCTURAL SIGNAL",
        validation_summary="Candidate awaiting deeper validation.",
    )


def test_failed_supply_search_never_becomes_gap(monkeypatch):
    monkeypatch.setattr("gapradar.worlddeep._github_search", lambda *a, **k: ([], False, "timeout"))
    monkeypatch.setattr("gapradar.worlddeep._npm_search", lambda *a, **k: ([], False, "timeout"))
    result = analyze_candidate(lead())
    assert result.gap_assessment == "INSUFFICIENT COVERAGE"
    assert result.final_recommendation == "WATCH"
    assert result.supply_status == "unassessed"


def test_multiple_relevant_suppliers_downgrade_broad_gap(monkeypatch):
    rows = [
        {"title": "Acme API alternative one", "url": "https://one.example", "snippet": "replacement migration tool for Acme developer API", "source": "one.example"},
        {"title": "Acme API alternative two", "url": "https://two.example", "snippet": "compatible replacement for Acme developer API", "source": "two.example"},
        {"title": "Acme API alternative three", "url": "https://three.example", "snippet": "migration platform replacing Acme API", "source": "three.example"},
    ]
    monkeypatch.setattr("gapradar.worlddeep._github_search", lambda *a, **k: (rows, True, None))
    monkeypatch.setattr("gapradar.worlddeep._npm_search", lambda *a, **k: ([], True, None))
    result = analyze_candidate(lead())
    assert result.supply_status == "served"
    assert result.gap_assessment == "LIKELY SERVED"
    assert result.final_recommendation == "DISMISS"


def test_no_supply_with_complete_coverage_is_only_potential_gap(monkeypatch):
    monkeypatch.setattr("gapradar.worlddeep._web_search", lambda *a, **k: ([], True, None))
    result = analyze_candidate(commercial_price_lead())
    assert result.supply_coverage == "adequate"
    assert result.supply_status == "no_supply_detected"
    assert result.gap_assessment == "POTENTIAL GAP"
    assert result.final_recommendation == "REVIEW"
