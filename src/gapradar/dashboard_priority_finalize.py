from __future__ import annotations

from pathlib import Path

STYLE = r'''
/* gapradar-priority-finalize-v1 */
.priority-card h3{margin:62px 0 8px!important;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden!important}
.priority-card p{margin:0!important;max-width:92%!important;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden!important;line-height:1.42!important}
.priority-card .bottommeta{max-width:72%!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
.priority-card[data-priority-status="INVESTIGATE"] .status{background:#5b4420!important;border-color:#a77a2d!important;color:#ffe0a2!important}
.priority-card[data-priority-status="REVIEW"] .status{background:#7b432f!important;border-color:#b96e4f!important;color:#ffd8c7!important}
'''


def patch(path: Path = Path("docs/index.html")) -> None:
    html = path.read_text(encoding="utf-8")
    # Runtime language switching used to overwrite card evidence metadata with the
    # generic "Business market / Watch" string. Keep priority-card copy intact.
    html = html.replace(
        "$$('.bottommeta:not(.discovery-slot .bottommeta)').forEach",
        "$$('.bottommeta').filter(el=>!el.closest('.discovery-slot,.priority-card')).forEach",
    )
    # The fourth funnel metric is now an attention recommendation, not only a
    # fully verified gap. This prevents the UI from showing a misleading zero
    # while preserving REVIEW as the stricter market-gap verdict.
    html = html.replace("'值得关注机会'", "'优先调查线索'")
    html = html.replace("'Opportunities to watch'", "'Priority leads'")
    if "gapradar-priority-finalize-v1" not in html:
        html = html.replace("</head>", f"<style>{STYLE}</style></head>", 1)
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch()
    print("Dashboard priority finalize: priority copy preserved and card layout clamped.")
