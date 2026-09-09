from datetime import datetime, timezone

from gapradar.worldscan import classify_change


def test_worldscan_detects_shutdown():
    result = classify_change("A cloud software platform is shutting down next month")
    assert result is not None
    assert result[0] == "shutdown_eol"


def test_worldscan_detects_price_shock():
    result = classify_change("The SaaS vendor announced a price increase for business customers")
    assert result is not None
    assert result[0] == "price_shock"


def test_worldscan_detects_api_change():
    result = classify_change("The developer API pricing change will affect third-party integrations")
    assert result is not None
    assert result[0] == "api_terms_change"


def test_worldscan_does_not_turn_generic_launch_into_gap():
    assert classify_change("A startup launches a new AI note-taking app") is None
