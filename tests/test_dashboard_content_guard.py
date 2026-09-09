import json
from pathlib import Path

from gapradar.dashboard_content_guard import patch


def test_content_guard_replaces_template_feed_copy_with_event_specific_evidence(tmp_path: Path):
    html = tmp_path / "index.html"
    candidates = tmp_path / "world-gaps.json"
    verifications = tmp_path / "world-verifications.json"
    html.write_text(
        '<div class="what"><b>Apple price change</b><span>Users must migrate before the old product disappears.</span></div>',
        encoding="utf-8",
    )
    candidates.write_text(json.dumps([{
        "id": "apple",
        "discovered_at": "2026-09-09T00:00:00+00:00",
        "published_at": "2026-09-09T00:00:00+00:00",
        "source": "Google News · SaaS pricing shocks",
        "headline": "Apple TV price hike",
        "url": "https://example.com",
        "summary": "Apple TV price hike",
        "change_type": "price_shock",
        "matched_signal": "price hike",
        "recommendation": "WATCH",
        "why_now": "",
        "gap_hypothesis": "",
        "validation_status": "STRUCTURAL SIGNAL",
        "validation_summary": "",
        "sector": "AI & Technology"
    }]), encoding="utf-8")
    verifications.write_text("[]", encoding="utf-8")

    assert patch(html, candidates, verifications) == 1
    text = html.read_text(encoding="utf-8")
    assert "price hike" in text
    assert "SaaS pricing shocks" in text
    assert "Tier-1 pending" in text
    assert "Tier-1 待确认" in text
    assert 'class="lang-zh"' in text
    assert 'class="lang-en"' in text
    assert "Users must migrate before the old product disappears." not in text
