from __future__ import annotations

from pathlib import Path

MARKER = "gapradar-priority-finalize-v5"

STYLE = r'''
/* gapradar-priority-finalize-v5 */
/* gapradar-priority-finalize-v4 compatibility marker */
/* gapradar-priority-finalize-v3 compatibility marker */
/* gapradar-priority-finalize-v2 compatibility marker */
/* gapradar-priority-finalize-v1 compatibility marker */
.priority-card{padding:18px!important}
.priority-card .priority-copy{position:absolute!important;left:18px!important;right:54px!important;top:112px!important;bottom:54px!important;z-index:3!important;display:flex!important;flex-direction:column!important;justify-content:flex-start!important;overflow:hidden!important}
.priority-card h3{position:static!important;margin:0 0 9px!important;max-width:100%!important;font-size:20px!important;line-height:1.24!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}
.priority-card .news-intro{position:static!important;margin:0!important;max-width:100%!important;color:color-mix(in srgb,var(--text) 76%,var(--muted))!important;font-size:12px!important;line-height:1.42!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}
.priority-card .bottommeta{display:none!important}
.priority-card .arrow{position:absolute!important;right:17px!important;bottom:14px!important;top:auto!important;left:auto!important;z-index:4!important}
.priority-card[data-priority-status="INVESTIGATE"] .status{background:#5b4420!important;border-color:#a77a2d!important;color:#ffe0a2!important}
.priority-card[data-priority-status="REVIEW"] .status{background:#7b432f!important;border-color:#b96e4f!important;color:#ffd8c7!important}
'''


def patch(path: Path = Path("docs/index.html")) -> None:
    html = path.read_text(encoding="utf-8")
    html = html.replace("ensureOpportunityCards();", "/* priority cards are server-rendered; no filler recommendations */")
    html = html.replace(
        "$$('.bottommeta:not(.discovery-slot .bottommeta)').forEach",
        "$$('.bottommeta').filter(el=>!el.closest('.discovery-slot,.priority-card')).forEach",
    )

    replacements = {
        "今日推荐机会": "今日优先线索",
        "基于最新变化，我们认为以下机会最值得关注。": "从今天的全球变化中，以下线索最值得你现在投入调查时间；只有 REVIEW 才代表市场缺口证据链完成。",
        "Today’s Opportunities": "Today’s Priority Leads",
        "The opportunities most worth watching based on the latest changes.": "The leads most worth investigating now. Only REVIEW means the market-gap evidence chain is complete.",
        "查看今日机会　→": "查看今日优先线索　→",
        "View today’s opportunities　→": "View today’s priority leads　→",
        "查看全部机会　→": "查看全部优先线索　→",
        "View all opportunities　→": "View all priority leads　→",
        "'值得关注机会'": "'优先调查线索'",
        "'Opportunities to watch'": "'Priority leads'",
        "opp:'今日推荐机会'": "opp:'今日优先线索'",
        "oppP:'基于最新变化，我们认为以下机会最值得关注。'": "oppP:'从今天的全球变化中，以下线索最值得你现在投入调查时间；只有 REVIEW 才代表市场缺口证据链完成。'",
        "allOpp:'查看全部机会　→'": "allOpp:'查看全部优先线索　→'",
        "today:'查看今日机会　→'": "today:'查看今日优先线索　→'",
        "opp:'Today’s Opportunities'": "opp:'Today’s Priority Leads'",
        "oppP:'The opportunities most worth watching based on the latest changes.'": "oppP:'The leads most worth investigating now. Only REVIEW means the market-gap evidence chain is complete.'",
        "allOpp:'View all opportunities　→'": "allOpp:'View all priority leads　→'",
        "today:'View today’s opportunities　→'": "today:'View today’s priority leads　→'",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)

    for old in (
        "/* gapradar-priority-finalize-v1 */",
        "/* gapradar-priority-finalize-v2 */",
        "/* gapradar-priority-finalize-v3 */",
        "/* gapradar-priority-finalize-v4 */",
    ):
        html = html.replace(old, "/* gapradar-priority-finalize-legacy */")
    if MARKER not in html:
        html = html.replace("</head>", f"<style>{STYLE}</style></head>", 1)

    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch()
    print("Dashboard priority finalize v5: distinct story intros with collision-proof card layout enforced.")
