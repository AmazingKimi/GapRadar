from pathlib import Path

from gapradar.dashboard_priority_finalize import MARKER, patch


def test_finalize_uses_priority_leads_and_disables_runtime_filler(tmp_path: Path):
    page = tmp_path / "index.html"
    page.write_text(
        """<html><head></head><body>
        <a>查看今日机会　→</a>
        <h2>今日推荐机会</h2>
        <p>基于最新变化，我们认为以下机会最值得关注。</p>
        <script>
        const COPY={zh:{opp:'今日推荐机会',oppP:'基于最新变化，我们认为以下机会最值得关注。',today:'查看今日机会　→',allOpp:'查看全部机会　→'},en:{opp:'Today’s Opportunities',oppP:'The opportunities most worth watching based on the latest changes.',today:'View today’s opportunities　→',allOpp:'View all opportunities　→'}};
        function boot(){ensureOpportunityCards();}
        </script>
        </body></html>""",
        encoding="utf-8",
    )

    patch(page)
    html = page.read_text(encoding="utf-8")

    assert "今日优先线索" in html
    assert "Today’s Priority Leads" in html
    assert "查看今日优先线索" in html
    assert "View today’s priority leads" in html
    assert "只有 REVIEW 才代表市场缺口证据链完成" in html
    assert "Only REVIEW means the market-gap evidence chain is complete" in html
    assert "ensureOpportunityCards();" not in html
    assert "no filler recommendations" in html
    assert MARKER in html
    assert ".priority-card .bottommeta{display:none!important}" in html
    assert "priority-copy" in html
