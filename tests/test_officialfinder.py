from gapradar.officialfinder import _authority_route, _looks_first_party, _query_variants, _subject_tokens
from gapradar.worldscan import GapCandidate


def _candidate(headline: str, summary: str = "structural change", change_type: str = "regulatory_shift") -> GapCandidate:
    return GapCandidate(
        id="x",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at=None,
        source="news",
        headline=headline,
        url="https://news.google.com/x",
        summary=summary,
        change_type=change_type,
        matched_signal="will require",
        recommendation="WATCH",
        why_now="new mandatory work",
        gap_hypothesis="compliance tooling",
        validation_status="NEWS SIGNAL",
        validation_summary="lead only",
        sector="Energy & Climate",
    )


def test_government_domain_is_first_party_candidate():
    candidate = _candidate("Massachusetts will require new data centers to use clean energy")
    assert _authority_route(candidate) == "public_regulator"
    assert _looks_first_party("https://www.mass.gov/news/new-data-center-rule", candidate) is True


def test_massachusetts_does_not_accept_unrelated_government_domain():
    candidate = _candidate("Massachusetts will require new data centers to use clean energy")
    assert _looks_first_party("https://www.ferc.gov/example", candidate) is False


def test_india_candidate_gets_jurisdiction_site_query():
    candidate = _candidate("India makes EV BMS cybersecurity testing mandatory")
    assert any("site:gov.in" in query for query in _query_variants(candidate))


def test_india_regulation_does_not_accept_publisher_with_india_in_domain():
    candidate = _candidate("India makes EV BMS cybersecurity testing mandatory")
    assert _looks_first_party("https://auto.economictimes.indiatimes.com/news/example", candidate) is False
    assert _looks_first_party("https://www.mercomindia.com/story", candidate) is False


def test_private_platform_policy_routes_to_company_owner_not_government():
    candidate = _candidate("Apple Music to make AI labels mandatory for music created with artificial intelligence")
    assert _authority_route(candidate) == "company_owner"
    assert _looks_first_party("https://www.apple.com/newsroom/example", candidate) is True
    assert _looks_first_party("https://www.ftc.gov/example", candidate) is False
    assert not any("government regulator" in query for query in _query_variants(candidate))


def test_company_owned_domain_can_be_source_candidate():
    candidate = _candidate("Apple changes Apple TV subscription pricing", change_type="price_shock")
    assert _authority_route(candidate) == "company_owner"
    assert _looks_first_party("https://www.apple.com/newsroom/apple-tv-pricing/", candidate) is True


def test_news_domain_is_never_tier1_candidate():
    candidate = _candidate("Apple changes Apple TV subscription pricing", change_type="price_shock")
    assert _looks_first_party("https://www.reuters.com/technology/apple-tv-price/", candidate) is False


def test_summary_publisher_tokens_do_not_pollute_official_queries():
    candidate = _candidate(
        "The latest Apple price hike: Apple TV streaming service",
        summary="Mashable.com reports that the service changed price.",
        change_type="price_shock",
    )
    assert "mashable" not in _subject_tokens(candidate)
    assert all("mashable" not in query.lower() for query in _query_variants(candidate))
