from pathlib import Path

from gapradar.dashboard_content_guard import EN_NOTE, ZH_NOTE, patch


def test_content_guard_replaces_template_feed_copy_with_bilingual_evidence_note(tmp_path: Path):
    path = tmp_path / "index.html"
    path.write_text(
        '<div class="what"><b>Example change</b><span>Users must migrate before the old product disappears.</span></div>',
        encoding="utf-8",
    )
    assert patch(path) == 1
    text = path.read_text(encoding="utf-8")
    assert ZH_NOTE in text
    assert EN_NOTE in text
    assert 'class="lang-zh"' in text
    assert 'class="lang-en"' in text
    assert "Users must migrate before the old product disappears." not in text
