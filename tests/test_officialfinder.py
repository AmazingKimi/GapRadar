from gapradar.officialfinder import _looks_first_party, _query_variants
from gapradar.worldscan import GapCandidate


def _candidate(headline: str, summary: str = "structural change") -> GapCandidate:
    return GapCandidate(
        id="x",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at=None,
        source="news",
        headline=headline,
        url="https://news.google.com/x",
        summary=summary,
        change_type="regulatory_shift",
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


def test_company_owned_domain_can_be_source_candidate():
    candidate = _candidate("Apple changes Apple TV subscription pricing")
    assert _looks_first_party("https://www.apple.com/newsroom/apple-tv-pricing/", candidate) is True


def test_news_domain_is_never_tier1_candidate():
    candidate = _candidate("Apple changes Apple TV subscription pricing")
    assert _looks_first_party("https://www.reuters.com/technology/apple-tv-price/", candidate) is False
