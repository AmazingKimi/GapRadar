import json
from pathlib import Path

from gapradar.dashboard_priority_patch import patch


def test_priority_patch_renders_specific_reason_and_research_status(tmp_path: Path):
    html = tmp_path / "index.html"
    priorities = tmp_path / "priority-leads.json"
    candidates = tmp_path / "world-gaps.json"
    html.write_text(
        '<div class="stats"><div><b>10</b><span>a</span></div><div><b>3</b><span>b</span></div><div><b>1</b><span>c</span></div><div><b>0</b><span>d</span></div></div>'
        '<section class="section" id="opps"><div class="opps"><article class="opp">old filler</article></div></section>'
        '<section class="section" id="feed"><div></div></section>',
        encoding="utf-8",
    )
    candidates.write_text(json.dumps([{
        "id": "apple",
        "discovered_at": "2026-09-09T00:00:00+00:00",
        "published_at": "2026-09-09T00:00:00+00:00",
        "source": "news",
        "headline": "Apple TV service price hike reaches 20%",
        "url": "https://example.com/apple",
        "summary": "Apple TV service price hike reaches 20%",
        "change_type": "price_shock",
        "matched_signal": "price hike",
        "recommendation": "WATCH",
        "why_now": "",
        "gap_hypothesis": "",
        "validation_status": "STRUCTURAL SIGNAL",
        "validation_summary": "",
        "sector": "AI & Technology"
    }]), encoding="utf-8")
    priorities.write_text(json.dumps([{
        "candidate_id": "apple",
        "status": "INVESTIGATE",
        "priority_score": 6,
        "evidence_state": "news_only",
        "evidence_label": "Tier-1 pending",
        "reason": "Apple TV has a concrete 20% price shock; switching demand should be investigated while Tier-1 remains pending.",
        "next_check": "Find Apple's first-party pricing page."
    }]), encoding="utf-8")

    assert patch(html, priorities, candidates) == 1
    text = html.read_text(encoding="utf-8")
    assert "old filler" not in text
    assert 'data-priority-status="INVESTIGATE"' in text
    assert "Apple TV has a concrete 20% price shock" in text
    assert "price hike" in text
    assert "优先调查线索" in text
    assert ">1</b>" in text
