from datetime import datetime, timezone

from gapradar.detector import OfficialSource, classify_entry, parse_feed
from gapradar.models import EventType


SOURCE = OfficialSource(
    name="Example Changelog",
    vendor="Example",
    url="https://example.com/feed.xml",
    allowed_domains=("example.com",),
    lookback_days=30,
)


def _rss(items: str) -> str:
    return f"""<?xml version='1.0' encoding='UTF-8'?>
    <rss version='2.0'><channel><title>Example</title>{items}</channel></rss>"""


def test_generic_deprecation_mention_in_body_is_not_an_event():
    assert classify_entry(
        "September platform updates",
        "We added a new API that reports runner version deprecations.",
    ) is None


def test_live_style_feature_posts_do_not_become_market_events():
    assert classify_entry(
        "Variants now support multiple barcodes",
        "The old barcode field is deprecated while the new barcodes connection is available.",
    ) is None
    assert classify_entry(
        "Polaris CDN 1.1 release candidate",
        "This release replaces a deprecated component and introduces new components.",
    ) is None
    assert classify_entry(
        "Build Shopify apps in PHP and Python with new official packages",
        "The packages provide API request helpers and replace older patterns.",
    ) is None


def test_explicit_body_removal_requires_migration_framing():
    assert classify_entry(
        "Platform migration notice",
        "The REST API endpoint will be removed on October 1.",
    ) == EventType.API_TERMS


def test_explicit_deprecation_title_is_kept():
    assert classify_entry(
        "Script tags are deprecated and will stop running on March 1, 2027",
        "Apps must replace script tags before the deadline.",
    ) == EventType.SHUTDOWN


def test_feed_enforces_lookback_and_official_domains():
    feed = _rss(
        """
        <item><title>Example API deprecated</title><link>https://example.com/new</link>
        <pubDate>Tue, 01 Sep 2026 12:00:00 GMT</pubDate><description>Migration required.</description></item>
        <item><title>Old Service retired</title><link>https://example.com/old</link>
        <pubDate>Wed, 01 Jul 2026 12:00:00 GMT</pubDate><description>Old.</description></item>
        <item><title>Fake Service retired</title><link>https://attacker.test/fake</link>
        <pubDate>Tue, 01 Sep 2026 12:00:00 GMT</pubDate><description>Fake.</description></item>
        """
    )
    rows = parse_feed(feed, SOURCE, now=datetime(2026, 9, 9, tzinfo=timezone.utc))
    assert len(rows) == 1
    assert rows[0].event_type == EventType.API_TERMS
    assert str(rows[0].official_evidence[0].url) == "https://example.com/new"


def test_shutdown_title_extracts_product_subject():
    feed = _rss(
        """
        <item><title>GitHub Classroom deprecated</title><link>https://example.com/classroom</link>
        <pubDate>Tue, 01 Sep 2026 12:00:00 GMT</pubDate><description>The service is decommissioned.</description></item>
        """
    )
    rows = parse_feed(feed, SOURCE, now=datetime(2026, 9, 9, tzinfo=timezone.utc))
    assert rows[0].product == "GitHub Classroom"
    assert rows[0].event_type == EventType.SHUTDOWN
