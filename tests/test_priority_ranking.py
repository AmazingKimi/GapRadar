from gapradar.officialfinder import _query_variants
from gapradar.priority import score_candidate
from gapradar.worldscan import GapCandidate


def _candidate(candidate_id: str, headline: str, change_type: str, matched_signal: str, summary: str = "") -> GapCandidate:
    return GapCandidate(
        id=candidate_id,
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at="2026-09-09T00:00:00+00:00",
        source="news",
        headline=headline,
        url=f"https://example.com/{candidate_id}",
        summary=summary or headline,
        change_type=change_type,
        matched_signal=matched_signal,
        recommendation="WATCH",
        why_now="",
        gap_hypothesis="",
        validation_status="STRUCTURAL SIGNAL",
        validation_summary="",
        sector="AI & Technology",
    )


def test_consumer_brand_price_story_does_not_win_priority_by_fame_alone():
    consumer = _candidate(
        "consumer",
        "Apple TV streaming service price hike",
        "price_shock",
        "price hike",
    )
    business = _candidate(
        "business",
        "Developer platform will shut down API service in 2026",
        "shutdown_eol",
        "shut down",
        "Developers and businesses using the API must migrate before end of support in 2026.",
    )

    assert score_candidate(consumer, None, None, None) < 7
    assert score_candidate(business, None, None, None) > score_candidate(consumer, None, None, None)


def test_speculative_change_is_penalized_until_verified():
    speculative = _candidate(
        "speculative",
        "Vendor may shut down enterprise API next year",
        "shutdown_eol",
        "shut down",
        "Businesses and developers could need to migrate.",
    )
    concrete = _candidate(
        "concrete",
        "Vendor will shut down enterprise API next year",
        "shutdown_eol",
        "shut down",
        "Businesses and developers must migrate before end of support.",
    )

    assert score_candidate(speculative, None, None, None) < score_candidate(concrete, None, None, None)


def test_known_owner_domain_is_searched_directly_for_company_change():
    apple = _candidate(
        "apple",
        "Apple TV streaming service price hike",
        "price_shock",
        "price hike",
    )
    samsung = _candidate(
        "samsung",
        "Samsung will shut down two apps in 2026",
        "shutdown_eol",
        "shut down",
    )

    assert _query_variants(apple)[0].startswith("site:apple.com ")
    assert _query_variants(samsung)[0].startswith("site:samsung.com ")
