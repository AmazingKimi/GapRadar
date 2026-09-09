from gapradar.detector import classify, classify_entry, is_allowed_official_url
from gapradar.models import EventType


def test_classifies_shutdown():
    assert classify("We are retiring Example Cloud on December 1") == EventType.SHUTDOWN


def test_classifies_price_change():
    assert classify("Pricing update: our free tier will be discontinued") == EventType.PRICE_SHOCK


def test_classifies_api_change():
    assert classify("API deprecation notice for v1 endpoints") == EventType.API_TERMS


def test_ignores_unrelated_text():
    assert classify("We launched a faster dashboard") is None


def test_live_feed_does_not_treat_new_free_access_as_price_shock():
    title = "Oxygen is now available on trial plan stores"
    summary = "You can now deploy from trial plan stores. Previously hosting required a paid plan."
    assert classify_entry(title, summary) is None


def test_historical_mode_can_use_strong_full_page_signals():
    title = "Heroku's Next Chapter"
    summary = "We will begin to sunset our free product plans and free dynos."
    assert classify_entry(title, summary, allow_strong_body=True) == EventType.PRICE_SHOCK


def test_official_domain_matching_is_strict():
    allowed = ("example.com",)
    assert is_allowed_official_url("https://blog.example.com/news", allowed)
    assert is_allowed_official_url("https://example.com/news", allowed)
    assert not is_allowed_official_url("https://example.com.attacker.test/news", allowed)
