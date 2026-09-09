from gapradar.officialfinder import _looks_first_party
from gapradar.worldscan import GapCandidate


def _candidate(headline: str) -> GapCandidate:
    return GapCandidate(
        id="x",
        discovered_at="2026-09-09T00:00:00+00:00",
        published_at=None,
        source="news",
        headline=headline,
        url="https://news.google.com/x",
        summary="structural change",
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


def test_company_owned_domain_can_be_source_candidate():
    candidate = _candidate("Apple changes Apple TV subscription pricing")
    assert _looks_first_party("https://www.apple.com/newsroom/apple-tv-pricing/", candidate) is True


def test_news_domain_is_never_tier1_candidate():
    candidate = _candidate("Apple changes Apple TV subscription pricing")
    assert _looks_first_party("https://www.reuters.com/technology/apple-tv-price/", candidate) is False
