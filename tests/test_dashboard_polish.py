import json
from pathlib import Path

from gapradar.dashboard_polish import MARKER, patch


def test_dashboard_polish_injects_funnel_and_unique_card_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "docs/index.html").write_text(
        '<html><body><section class="hero"><div><div class="stats"></div></div></section><section class="section" id="sectors"></section><div class="opps"></div><div class="feed"></div></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "data/world-scan-stats.json").write_text(json.dumps({"raw_entries": 755, "candidates": 25}), encoding="utf-8")
    (tmp_path / "data/world-quality-report.json").write_text(
        json.dumps({"input_candidates": 25, "context_rejected": 9, "duplicate_collapsed": 2, "kept_candidates": 14}),
        encoding="utf-8",
    )
    (tmp_path / "data/world-verification-metrics.json").write_text(
        json.dumps({"tier1_verified": 2, "awaiting_tier1": 12, "average_awaiting_hours": 4.5, "oldest_awaiting_hours": 9.0}),
        encoding="utf-8",
    )
    patch()
    text = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    assert MARKER in text
    assert "Signal funnel:" in text
    assert "755" in text and "14" in text and "2" in text
    assert "duplicates collapsed" in text
    assert "seen.has(key)" in text
    assert "-webkit-line-clamp:3" in text
