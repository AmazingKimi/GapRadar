import json
from pathlib import Path

from gapradar.blindbacktest import replay_fixture


def test_blind_benchmark_reports_precision_and_recall(tmp_path: Path):
    fixture = tmp_path / "events.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "id": "positive",
                    "expected_detect": True,
                    "event_type": "shutdown_eol",
                    "title_hint": "Cloud software service is shutting down",
                    "excerpt_hint": "The platform will close and customers must migrate.",
                },
                {
                    "id": "negative",
                    "expected_detect": False,
                    "title_hint": "Cloud software product launches new dashboard",
                    "excerpt_hint": "A routine feature release adds analytics and collaboration controls for customers.",
                },
            ]
        ),
        encoding="utf-8",
    )
    report = replay_fixture(fixture)
    assert report["mode"] == "blind_noisy_stream_offline"
    assert report["metrics"]["cases_total"] == 2
    assert report["metrics"]["tp"] == 1
    assert report["metrics"]["tn"] == 1
    assert report["metrics"]["precision"] == 1.0
    assert report["metrics"]["recall"] == 1.0
