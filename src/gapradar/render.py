from __future__ import annotations

from html import escape
from pathlib import Path

from .dossier import build_dossier
from .models import MarketEvent
from .worldscan import GapCandidate, WorldScanStats


CSS = """
:root { color-scheme: dark; --bg:#081019; --panel:#0f1823; --panel2:#0b131c; --line:#223143; --text:#eef5fb; --muted:#94a3b5; --accent:#69d6ff; --green:#71e5b5; --yellow:#ffd36b; --red:#ff8585; --purple:#bba7ff; }
* { box-sizing:border-box; }
body { margin:0; background:radial-gradient(circle at 20% 0%,#10283b 0,var(--bg) 36%); color:var(--text); font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { max-width:1280px; margin:0 auto; padding:44px 24px 80px; }
.topbar { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
.eyebrow { color:var(--accent); font-size:12px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
h1 { font-size:clamp(42px,7vw,78px); line-height:.96; margin:12px 0 16px; letter-spacing:-.055em; }
.lede { max-width:920px; color:#bdc8d6; font-size:18px; margin:0; }
.pulse { display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border:1px solid #294057; border-radius:999px; color:#cdefff; background:#0d1b27; white-space:nowrap; }
.dot { width:8px; height:8px; border-radius:50%; background:var(--green); box-shadow:0 0 18px var(--green); }
.metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:30px 0 26px; }
.metric { padding:18px; background:rgba(15,24,35,.86); border:1px solid var(--line); border-radius:18px; }
.metric strong { display:block; font-size:30px; }.metric span { color:var(--muted); font-size:12px; letter-spacing:.08em; text-transform:uppercase; }
.funnel { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; margin:10px 0 30px; }
.funnel .step { position:relative; padding:16px; background:#0b141e; border:1px solid #26374a; border-radius:16px; }
.funnel .step b { display:block; font-size:24px; margin-bottom:3px; }.funnel .step span { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.07em; }
.section-head { display:flex; justify-content:space-between; align-items:end; gap:20px; margin:34px 0 14px; }
.section-head h2 { margin:0; font-size:24px; }.section-head p { margin:0; color:var(--muted); max-width:720px; }
.grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
.card { background:linear-gradient(180deg,rgba(17,29,42,.95),rgba(11,19,28,.95)); border:1px solid var(--line); border-radius:20px; padding:22px; }
.card.verified { border-color:#2d6353; box-shadow:0 0 0 1px rgba(113,229,181,.08) inset; }
.card h3 { margin:12px 0 7px; font-size:21px; line-height:1.25; }.meta,.summary,.small { color:var(--muted); }.summary { margin:8px 0 0; }
.badges { display:flex; flex-wrap:wrap; gap:7px; }.badge { display:inline-flex; padding:5px 9px; border:1px solid #33465c; border-radius:999px; font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:#c8d6e5; }
.badge.review { color:#09121a; background:var(--green); border-color:var(--green); font-weight:800; }.badge.watch { color:#1d1600; background:var(--yellow); border-color:var(--yellow); font-weight:800; }.badge.verified { color:var(--green); border-color:#326b59; }.badge.signal { color:var(--accent); border-color:#315b73; }.badge.low { color:var(--yellow); border-color:#665524; }.badge.medium { color:var(--accent); border-color:#315b73; }.badge.high { color:var(--green); border-color:#326b59; }
.block { margin-top:16px; padding:14px; border:1px solid #233247; border-radius:14px; background:#0a121b; }.block h4 { margin:0 0 7px; color:#d8e5ef; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }.block p { margin:0; color:#aebcca; }
.block.reco { border-color:#315a4f; background:#0b1716; }.block.validate { border-color:#34445b; }.block.hypothesis { border-color:#51476d; background:#12101c; }
a { color:var(--accent); text-decoration:none; }.evidence { margin-top:14px; display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; font-size:13px; }
.empty { padding:28px; border:1px dashed #334153; border-radius:18px; color:var(--muted); }.footer { margin-top:38px; color:#6f8194; font-size:12px; }
@media(max-width:1000px){.funnel{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:820px){.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.funnel{grid-template-columns:repeat(2,minmax(0,1fr))}.topbar{flex-direction:column}.section-head{align-items:flex-start;flex-direction:column}}
"""


def _verified_recommendation(event: MarketEvent) -> tuple[str, str, str]:
    if event.event_type.value == "shutdown_eol":
        return "REVIEW", "The incumbent is removing a workflow or capability, so affected users must migrate.", "Investigate replacement products, compatibility layers, migration services, and vertical substitutes. The best gap is usually not a clone; it is the part of the old workflow that alternatives handle badly."
    if event.event_type.value == "price_shock":
        return "REVIEW", "A pricing discontinuity can release budget-sensitive users from an incumbent.", "Map lower-cost substitutes and identify which customer segment is now overpaying for features it does not need."
    return "REVIEW", "A platform/API change can force businesses to rewrite integrations or replace dependencies.", "Look for migration tooling, compatibility layers, alternate providers, and products that reduce dependence on the changed platform."


def _world_card(row: GapCandidate) -> str:
    recommendation_class = "review" if row.recommendation == "REVIEW" else "watch"
    summary = row.summary or "No feed summary supplied."
    return f"""
    <article class="card">
      <div class="badges"><span class="badge {recommendation_class}">{escape(row.recommendation)}</span><span class="badge signal">{escape(row.change_type.replace('_',' '))}</span><span class="badge">candidate</span></div>
      <h3>{escape(row.headline)}</h3>
      <div class="meta">{escape(row.source)} · {escape(row.published_at or 'time unavailable')}</div>
      <p class="summary">{escape(summary[:650])}</p>
      <div class="block reco"><h4>Candidate gap hypothesis</h4><p><b>Why now:</b> {escape(row.why_now)}<br><br><b>Potential gap:</b> {escape(row.gap_hypothesis)}</p></div>
      <div class="block validate"><h4>Discovery status</h4><p>{escape(row.validation_summary)}</p></div>
      <div class="evidence"><span class="small">Matched signal: “{escape(row.matched_signal)}”</span><a href="{escape(row.url)}" target="_blank" rel="noreferrer">open source ↗</a></div>
    </article>"""


def _verified_card(event: MarketEvent) -> str:
    dossier = build_dossier(event)
    official = event.official_evidence[0] if event.official_evidence else None
    recommendation, why_now, fallback_hypothesis = _verified_recommendation(event)
    evidence_link = f'<a href="{escape(str(official.url))}" target="_blank" rel="noreferrer">official source ↗</a>' if official else "no official source"
    reaction_note = f"Reaction evidence: {len(event.reaction_evidence)} qualifying signal(s); search quality {event.reaction_search_quality}." if event.reaction_checked_at else "Reaction search has not run yet."
    supply_note = f"Replacement supply: {event.supply_status}; accepted evidence {len(event.supply_evidence)}." if event.supply_checked_at else "Replacement supply has not yet been mapped."
    validation = "Tier-1 official evidence verifies the market change. " + reaction_note + " " + supply_note + " Reaction adjusts confidence only; it never blocks the demand hypothesis or the supply search."
    when = event.event_date.date().isoformat() if event.event_date else "date unknown"
    hypothesis = event.demand_hypothesis
    if hypothesis:
        hypothesis_html = (
            f'<div class="block hypothesis"><h4>Demand hypothesis · {escape(hypothesis.confidence)} confidence</h4>'
            f'<p><b>Affected users:</b> {escape(hypothesis.affected_users)}<br><br>'
            f'<b>Job to be done:</b> {escape(hypothesis.job_to_be_done)}<br><br>'
            f'<b>Disruption:</b> {escape(hypothesis.disruption)}<br><br>'
            f'<b>Official successor:</b> {escape(hypothesis.official_successor)}<br><br>'
            f'<b>Unknowns:</b> {escape("; ".join(hypothesis.unknowns) or "none recorded")}</p></div>'
        )
        confidence_badge = f'<span class="badge {escape(hypothesis.confidence)}">hypothesis {escape(hypothesis.confidence)}</span>'
    else:
        hypothesis_html = f'<div class="block hypothesis"><h4>Demand hypothesis</h4><p>{escape(fallback_hypothesis)}</p></div>'
        confidence_badge = '<span class="badge low">hypothesis unassessed</span>'
    return f"""
    <article class="card verified">
      <div class="badges"><span class="badge review">{recommendation}</span><span class="badge verified">officially verified</span><span class="badge signal">{escape(event.event_type.value.replace('_',' '))}</span>{confidence_badge}</div>
      <h3>{escape(event.headline)}</h3>
      <div class="meta">{escape(event.vendor)} · {escape(event.product)} · {when}</div>
      <p class="summary">{escape(event.summary[:650])}</p>
      <div class="block reco"><h4>Why this change matters</h4><p>{escape(why_now)}</p></div>
      {hypothesis_html}
      <div class="block validate"><h4>Validation summary</h4><p>{escape(validation)}<br><br><b>Dossier:</b> {escape(dossier.verdict)} — {escape(dossier.rationale)}</p></div>
      <div class="evidence"><span class="small">Tier 1: {len(event.official_evidence)} · Reaction: {len(event.reaction_evidence)} · Supply: {len(event.supply_evidence)} · Gap: {escape(event.gap_status)}</span>{evidence_link}</div>
    </article>"""


def render_dashboard(events: list[MarketEvent], output: Path, world_candidates: list[GapCandidate] | None = None, scan_stats: WorldScanStats | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    world_candidates = world_candidates or []
    for event in events:
        event.verify()
    verified_cards = "\n".join(_verified_card(event) for event in events) or '<div class="empty">No new first-party verified market changes in the current window.</div>'
    world_cards = "\n".join(_world_card(row) for row in world_candidates[:40]) or '<div class="empty">No broad world-scan candidates matched the structural-change rules in this run.</div>'

    hypotheses = sum(1 for event in events if event.demand_hypothesis is not None)
    supply_mapped = sum(1 for event in events if event.supply_checked_at is not None)
    gap_watch = sum(1 for event in events if event.gap_status in {"watch", "potential_gap"})
    likely_served = sum(1 for event in events if event.gap_status == "likely_served")
    raw_entries = scan_stats.raw_entries if scan_stats else len(world_candidates)
    recent_entries = scan_stats.recent_entries if scan_stats else len(world_candidates)
    structural_matches = scan_stats.structural_matches if scan_stats else len(world_candidates)
    source_health = f"{scan_stats.sources_ok}/{scan_stats.sources_configured} discovery sources healthy" if scan_stats else "discovery source health unavailable"

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GapRadar — Today Opportunity Board</title><style>{CSS}</style></head>
<body><main>
<div class="topbar"><div><div class="eyebrow">Market Gap Intelligence · Today</div><h1>Today’s Market Gaps</h1><p class="lede">GapRadar watches what changes in the world, verifies which changes are real, then investigates where they may create demand the market has not adequately served. Community reaction is supporting evidence, never the discovery engine or a veto.</p></div><div class="pulse"><span class="dot"></span> {escape(source_health)}</div></div>
<section class="metrics"><div class="metric"><strong>{len(world_candidates)}</strong><span>candidate signals</span></div><div class="metric"><strong>{len(events)}</strong><span>officially verified</span></div><div class="metric"><strong>{gap_watch}</strong><span>verified gaps to watch</span></div><div class="metric"><strong>{likely_served}</strong><span>likely served</span></div></section>
<div class="section-head"><div><div class="eyebrow">Signal funnel</div><h2>What survived today’s pipeline</h2></div><p>This funnel is a health check, not a quota. A correct day may scan hundreds of items and end with zero credible gaps.</p></div>
<section class="funnel"><div class="step"><b>{raw_entries}</b><span>raw items scanned</span></div><div class="step"><b>{recent_entries}</b><span>inside lookback</span></div><div class="step"><b>{structural_matches}</b><span>structural matches</span></div><div class="step"><b>{len(world_candidates)}</b><span>deduped candidates</span></div><div class="step"><b>{len(events)}</b><span>Tier-1 verified</span></div><div class="step"><b>{gap_watch}</b><span>gaps worth watching</span></div></section>
<div class="section-head"><div><div class="eyebrow">Verified market changes</div><h2>Opportunity hypotheses that survived verification</h2></div><p>Every verified event carries an explicit demand hypothesis. Reaction can raise confidence; it cannot erase the hypothesis or stop supply analysis.</p></div>
<section class="grid">{verified_cards}</section>
<div class="section-head"><div><div class="eyebrow">Broad world scan</div><h2>New structural-change candidates</h2></div><p>These are noisy discovery leads from news and industry feeds. They are candidates awaiting verification, not proven business opportunities.</p></div>
<section class="grid">{world_cards}</section>
<div class="footer">GapRadar · WORLD SCAN → CANDIDATE → VERIFY → DEMAND HYPOTHESIS → REACTION + SUPPLY → GAP → DOSSIER. Event confidence and opportunity confidence are separate. Hypotheses: {hypotheses}; supply maps completed: {supply_mapped}.</div>
</main></body></html>"""
    output.write_text(html, encoding="utf-8")
