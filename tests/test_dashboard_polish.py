import json
from pathlib import Path

from gapradar.dashboard_polish import MARKER, patch


def test_dashboard_polish_injects_compact_funnel_and_decision_flow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "docs/index.html").write_text(
        '<html><body><section class="hero"><div><div class="stats"></div></div></section><section class="section" id="sectors"></section><div class="opps"></div><div class="feed"></div></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "data/world-scan-stats.json").write_text(json.dumps({"raw_entries": 755, "candidates": 25}), encoding="utf-8")
    (tmp_path / "data/world-quality-report.json").write_text(
        json.dumps({"input_candidates": 25, "context_rejected": 9, "duplicate_collapsed": 2, "kept_candidates": 14}), encoding="utf-8")
    (tmp_path / "data/world-verification-metrics.json").write_text(json.dumps({"tier1_verified": 2}), encoding="utf-8")
    (tmp_path / "data/commercial-cadence.json").write_text(json.dumps({"summary":{"priority_leads_total":3,"review_opportunities_total":1}}), encoding="utf-8")
    (tmp_path / "data/sector-trends.json").write_text(json.dumps({"sectors":{"Mobility":{"count":2,"previous":1,"delta":1,"dominant_change_type":"regulatory_shift"}}}), encoding="utf-8")
    patch()
    text = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    assert MARKER in text
    assert "755" in text and "14" in text and "3" in text
    assert "Evidence funnel details" in text
    assert "World Change" in text and "Priority Lead" in text and "Gap Validation" in text
    assert "sector-trend" in text
    assert "feed-tag" in text
    assert "ensureOpportunityCards();" not in text
