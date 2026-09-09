from __future__ import annotations

from html import escape
from pathlib import Path

from .models import MarketEvent


CSS = """
:root { color-scheme: dark; --bg:#090b10; --panel:#11151d; --line:#232a36; --text:#eef2f7; --muted:#8d98a8; --accent:#7ce7c4; --warn:#ffcf70; --hot:#ff8f8f; }
* { box-sizing:border-box; }
body { margin:0; background:radial-gradient(circle at 20% 0%, #132028 0, var(--bg) 38%); color:var(--text); font:15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width:1180px; margin:0 auto; padding:56px 24px 80px; }
.eyebrow { color:var(--accent); font-size:12px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; }
h1 { font-size:clamp(42px,8vw,84px); line-height:.95; margin:14px 0 18px; letter-spacing:-.055em; }
.lede { max-width:840px; color:#b8c1cf; font-size:18px; }
.metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:34px 0; }
.metric,.card,.empty { background:rgba(17,21,29,.78); border:1px solid var(--line); border-radius:18px; backdrop-filter:blur(14px); }
.metric { padding:18px; }.metric strong { display:block; font-size:28px; }.metric span { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
.grid { display:grid; gap:14px; }.card { padding:22px; }.row { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.badges { display:flex; flex-wrap:wrap; gap:8px; }.badge { display:inline-flex; padding:5px 9px; border:1px solid #334052; border-radius:999px; color:#c7d0dd; font-size:11px; text-transform:uppercase; letter-spacing:.06em; }
.badge.signal { border-color:#35594f; color:var(--accent); }.badge.none { color:var(--warn); border-color:#665733; }.badge.gap { color:var(--hot); border-color:#674141; }
.card h2 { margin:14px 0 8px; font-size:22px; }.meta,.summary { color:var(--muted); }.summary { margin:10px 0 0; }a { color:var(--accent); text-decoration:none; }
.evidence { margin-top:14px; padding-top:14px; border-top:1px solid var(--line); }.evidence-head { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; }
.columns { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }.box { padding:12px; background:#0d1118; border:1px solid #1d2530; border-radius:12px; }.box h3 { font-size:12px; letter-spacing:.08em; text-transform:uppercase; margin:0 0 8px; color:#b8c1cf; }
.item { padding:8px 0; border-top:1px solid #18202b; }.item:first-of-type { border-top:0; padding-top:0; }.item strong { font-size:13px; }.item .meta { font-size:12px; margin-top:3px; }
.empty { padding:32px; color:var(--muted); }footer { margin-top:34px; color:#657084; font-size:12px; }
@media (max-width:760px) { .metrics { grid-template-columns:repeat(2,minmax(0,1fr)); } .row { align-items:flex-start; flex-direction:column; } .columns { grid-template-columns:1fr; } }
"""


def render_dashboard(events: list[MarketEvent], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    cards = []
    for event in events:
        official = event.official_evidence[0] if event.official_evidence else None
        evidence_link = f'<a href="{escape(str(official.url))}" target="_blank" rel="noreferrer">official evidence ↗</a>' if official else "no official evidence"
        when = event.event_date.date().isoformat() if event.event_date else "date unknown"
        demand_class = "signal" if event.demand_status in {"early_signal", "repeated_signal"} else "none"
        supply_class = "signal" if event.supply_status == "served" else "none"
        gap_class = "gap" if event.gap_status == "potential_gap" else ("signal" if event.gap_status == "likely_served" else "none")

        reaction_rows = []
        for reaction in event.reaction_evidence[:3]:
            reaction_rows.append(
                f'<div class="item"><strong><a href="{escape(str(reaction.url))}" target="_blank" rel="noreferrer">{escape(reaction.title)}</a></strong>'
                f'<div class="meta">{escape(reaction.publisher)} · pain {reaction.signal_score} · engagement {reaction.engagement}</div></div>'
            )
        if not reaction_rows:
            message = "No qualifying migration-pain signal found." if event.reaction_checked_at else "Demand validation has not run."
            reaction_rows.append(f'<div class="item meta">{message}</div>')

        supply_rows = []
        for supply in event.supply_evidence[:3]:
            supply_rows.append(
                f'<div class="item"><strong><a href="{escape(str(supply.url))}" target="_blank" rel="noreferrer">{escape(supply.title)}</a></strong>'
                f'<div class="meta">{escape(supply.publisher)} · relevance {supply.signal_score} · popularity {supply.engagement}</div></div>'
            )
        if not supply_rows:
            message = "No qualifying replacement supply found." if event.supply_checked_at else "Supply validation has not run."
            supply_rows.append(f'<div class="item meta">{message}</div>')

        cards.append(f"""
        <article class="card">
          <div class="row"><div class="badges">
            <span class="badge">{escape(event.event_type.value.replace('_',' '))}</span>
            <span class="badge {demand_class}">demand: {escape(event.demand_status.replace('_',' '))}</span>
            <span class="badge {supply_class}">supply: {escape(event.supply_status.replace('_',' '))}</span>
            <span class="badge {gap_class}">gap: {escape(event.gap_status.replace('_',' '))}</span>
          </div></div>
          <h2>{escape(event.headline)}</h2>
          <div class="meta">{escape(event.vendor)} · {escape(event.product)} · {when}</div>
          <p class="summary">{escape(event.summary[:700])}</p>
          <div class="evidence"><div class="evidence-head">{evidence_link}<span class="meta">Tier 1: {len(event.official_evidence)} · Reaction: {len(event.reaction_evidence)} · Supply: {len(event.supply_evidence)}</span></div>
            <div class="columns"><div class="box"><h3>Displaced demand</h3>{''.join(reaction_rows)}</div><div class="box"><h3>Replacement supply</h3>{''.join(supply_rows)}</div></div>
          </div>
        </article>""")

    cards_html = "\n".join(cards) if cards else '<div class="empty">No verified market-change events in the current window. Silence is a valid result.</div>'
    supply_checked = sum(1 for event in events if event.supply_checked_at is not None)
    gaps = sum(1 for event in events if event.gap_status == "potential_gap")
    served = sum(1 for event in events if event.gap_status == "likely_served")
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GapRadar</title><style>{CSS}</style></head>
<body><main><div class="eyebrow">Market Gap Intelligence · v0.4</div><h1>GapRadar</h1>
<p class="lede">Verified market changes, displaced-demand evidence, and replacement-supply analysis. V0.4 does not call a change a gap until demand survives the supply check.</p>
<section class="metrics"><div class="metric"><strong>{len(events)}</strong><span>verified events</span></div><div class="metric"><strong>{supply_checked}</strong><span>supply checked</span></div><div class="metric"><strong>{gaps}</strong><span>potential gaps</span></div><div class="metric"><strong>{served}</strong><span>likely served</span></div></section>
<section class="grid">{cards_html}</section><footer>Generated by GapRadar v0.4 · Event ≠ demand ≠ gap. Evidence before opportunity.</footer></main></body></html>"""
    output.write_text(html, encoding="utf-8")
