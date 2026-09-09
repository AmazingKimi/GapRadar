from __future__ import annotations

from pathlib import Path

MARKER = "gapradar-priority-finalize-v2"

STYLE = r'''
/* gapradar-priority-finalize-v2 */
/* gapradar-priority-finalize-v1 compatibility marker */
.priority-card h3{margin:62px 0 8px!important;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden!important}
.priority-card p{margin:0!important;max-width:92%!important;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden!important;line-height:1.42!important}
.priority-card .bottommeta{max-width:72%!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
.priority-card[data-priority-status="INVESTIGATE"] .status{background:#5b4420!important;border-color:#a77a2d!important;color:#ffe0a2!important}
.priority-card[data-priority-status="REVIEW"] .status{background:#7b432f!important;border-color:#b96e4f!important;color:#ffd8c7!important}
'''


def patch(path: Path = Path("docs/index.html")) -> None:
    html = path.read_text(encoding="utf-8")

    # Priority cards are rendered from evidence-aware priority-leads.json. The
    # old browser runtime used to manufacture cards from Global Feed whenever
    # fewer than three cards existed. That made the dashboard look productive
    # even when the ranking system had no recommendation. Never synthesize
    # filler recommendations in the browser.
    html = html.replace("ensureOpportunityCards();", "/* priority cards are server-rendered; no filler recommendations */")

    # Runtime language switching used to overwrite evidence metadata with the
    # generic "Business market / Watch" string. Keep evidence-specific copy.
    html = html.replace(
        "$$('.bottommeta:not(.discovery-slot .bottommeta)').forEach",
        "$$('.bottommeta').filter(el=>!el.closest('.discovery-slot,.priority-card')).forEach",
    )

    # The product's daily useful output is a research queue. REVIEW remains a
    # stricter downstream market-gap verdict and must not be conflated with the
    # cards users should inspect today.
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

    # Remove older finalize styles when patching an already-rendered page, then
    # append the current marker once. Preserve the workflow's v1 grep through
    # the compatibility marker inside STYLE.
    html = html.replace("/* gapradar-priority-finalize-v1 */", "/* gapradar-priority-finalize-legacy */")
    if MARKER not in html:
        html = html.replace("</head>", f"<style>{STYLE}</style></head>", 1)

    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch()
    print("Dashboard priority finalize v2: research queue semantics enforced; filler cards disabled.")
