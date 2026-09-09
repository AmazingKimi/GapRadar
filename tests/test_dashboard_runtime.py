from pathlib import Path

from gapradar.dashboard_runtime import SCRIPT, STYLE, patch_dashboard
from gapradar.strip_legacy_runtime import strip


def test_runtime_covers_complete_bilingual_controls() -> None:
    required = [
        "View today’s opportunities",
        "Browse sector radar",
        "Important Global Changes",
        "Items scanned today",
        "Regulation",
        "Consumer",
        "Dark ✓  |  Light",
        "中文  |  EN ✓",
        "Awaiting Tier-1",
        "Discovery lead",
        "A structural change was detected, but Tier-1 first-party evidence is not verified yet",
    ]
    for token in required:
        assert token in SCRIPT


def test_runtime_keeps_three_truthful_opportunity_slots() -> None:
    assert "function ensureOpportunityCards()" in SCRIPT
    assert "for(let i=cards.length;i<3;i++)" in SCRIPT
    assert "discovery-slot" in SCRIPT
    assert "not promoted to a market opportunity" in SCRIPT


def test_runtime_has_mobile_breakpoints() -> None:
    assert "@media(max-width:640px)" in STYLE
    assert "grid-template-columns:1fr 1fr" in STYLE
    assert ".actions{display:grid" in STYLE
    assert ".stats{grid-template-columns:repeat(2" in STYLE
    assert ".filters{width:100%" in STYLE
    assert "@media(max-width:420px)" in STYLE


def test_export_sequence_removes_legacy_controller_and_injects_single_runtime(tmp_path: Path) -> None:
    html = tmp_path / "index.html"
    html.write_text(
        '<!doctype html><html><body><button id="langToggle"></button><button id="themeToggle"></button>'
        '<script>(function(){var r=document.documentElement,l=document.getElementById("langToggle"),t=document.getElementById("themeToggle");l.onclick=function(){};t.onclick=function(){};})();</script>'
        '</body></html>',
        encoding="utf-8",
    )
    strip(html)
    patch_dashboard(html)
    text = html.read_text(encoding="utf-8")
    assert "gapradar-runtime-v6" in text
    assert "gapradar-runtime-v5" not in text
    assert "var r=document.documentElement,l=document.getElementById" not in text
    assert text.count("gapradar-runtime-v6") == 2  # CSS marker + HTML marker
