from pathlib import Path

from gapradar.backtest import extract_page, run_backtest


FIXTURE = Path("data/backtest/events.json")


def test_historical_fixture_has_real_benchmark_size():
    report = run_backtest(FIXTURE, mode="fixture")
    assert report["metrics"]["cases_total"] >= 20
    positives = sum(1 for row in report["results"] if row.get("expected_detect"))
    assert positives >= 15


def test_fixture_detector_precision_and_recall_have_minimum_floor():
    report = run_backtest(FIXTURE, mode="fixture")
    metrics = report["metrics"]
    assert metrics["precision"] is not None and metrics["precision"] >= 0.90
    assert metrics["recall"] is not None and metrics["recall"] >= 0.75


def test_as_of_filters_future_cases_without_changing_ground_truth():
    report = run_backtest(FIXTURE, mode="fixture", as_of=__import__("datetime").date(2022, 12, 31))
    assert all(row["event_date"] <= "2022-12-31" for row in report["results"])
    assert report["metrics"]["cases_total"] < run_backtest(FIXTURE, mode="fixture")["metrics"]["cases_total"]


def test_extract_page_uses_h1_and_strips_markup():
    title, body = extract_page("<html><title>fallback</title><body><h1>Sunsetting <b>Example</b></h1><p>We will shut it down.</p></body></html>")
    assert title == "Sunsetting Example"
    assert "We will shut it down." in body
