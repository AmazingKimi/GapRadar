import json
from pathlib import Path

from gapradar.dashboard_priority_patch import patch


def _candidate(cid: str, headline: str, publisher: str, sector: str, change_type: str):
    return {
        "id": cid,
        "discovered_at": "2026-09-09T00:00:00+00:00",
        "published_at": "2026-09-09T00:00:00+00:00",
        "source": publisher,
        "headline": headline,
        "url": f"https://example.com/{cid}",
        "summary": publisher,
        "change_type": change_type,
        "matched_signal": "mandatory" if change_type == "regulatory_shift" else "shutdown",
        "recommendation": "WATCH",
        "why_now": "",
        "gap_hypothesis": "",
        "validation_status": "STRUCTURAL SIGNAL",
        "validation_summary": "",
        "sector": sector,
    }


def _priority(cid: str, evidence: str = "Tier-1 pending"):
    return {
        "candidate_id": cid,
        "status": "INVESTIGATE",
        "priority_score": 6,
        "evidence_state": "news_only",
        "evidence_label": evidence,
        "reason": "THIS GENERIC ANALYSIS MUST NOT RENDER ON THE HOMEPAGE CARD.",
        "next_check": "Do more research.",
    }


def test_priority_patch_renders_distinct_story_intros_without_overlay_metadata(tmp_path: Path):
    html = tmp_path / "index.html"
    priorities = tmp_path / "priority-leads.json"
    candidates = tmp_path / "world-gaps.json"
    html.write_text(
        '<section class="section" id="opps"><div class="opps"><article class="opp">old filler</article></div></section>'
        '<section class="section" id="feed"><div></div></section>',
        encoding="utf-8",
    )
    candidates.write_text(json.dumps([
        _candidate("ev", "EV BMS Cybersecurity Testing Now Mandatory in India", "Autocar Professional", "Mobility", "regulatory_shift"),
        _candidate("mass", "Massachusetts Will Require New Data Centers to Use Clean Energy", "EnergyNow.com", "Energy & Climate", "regulatory_shift"),
        _candidate("samsung", "Samsung preps the shutdown of two more apps late in 2026", "Android Central", "Consumer & Society", "shutdown_eol"),
    ]), encoding="utf-8")
    priorities.write_text(json.dumps([
        _priority("ev", "Official lead · heavyindustries.gov.in"),
        _priority("mass", "Official lead · mass.gov"),
        _priority("samsung"),
    ]), encoding="utf-8")

    assert patch(html, priorities, candidates) == 1
    text = html.read_text(encoding="utf-8")
    assert "old filler" not in text
    assert text.count('class="news-intro"') == 3
    assert "Source: Autocar Professional" in text and "mandatory" in text
    assert "Source: EnergyNow.com" in text
    assert "Source: Android Central" in text and "shutdown" in text
    assert text.count('data-candidate-id=') == 3
    assert "THIS GENERIC ANALYSIS MUST NOT RENDER" not in text
    assert "bottommeta" not in text
    assert "Official lead · mass.gov" not in text
    assert "View evidence chain" in text
