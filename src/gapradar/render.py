from __future__ import annotations

from html import escape
from pathlib import Path

from .dossier import build_dossier
from .models import MarketEvent
from .worlddeep import WorldLeadAssessment, load_assessments
from .worldscan import GapCandidate, WorldScanStats

CSS = """
:root{color-scheme:dark;--bg:#081019;--panel:#0f1823;--line:#223143;--text:#eef5fb;--muted:#94a3b5;--accent:#69d6ff;--green:#71e5b5;--yellow:#ffd36b;--red:#ff8585;--purple:#bba7ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0%,#10283b 0,var(--bg) 36%);color:var(--text);font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1280px;margin:0 auto;padding:44px 24px 80px}.topbar{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.eyebrow{color:var(--accent);font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase}h1{font-size:clamp(42px,7vw,78px);line-height:.96;margin:12px 0 16px;letter-spacing:-.055em}.lede{max-width:940px;color:#bdc8d6;font-size:18px;margin:0}.pulse{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border:1px solid #294057;border-radius:999px;color:#cdefff;background:#0d1b27;white-space:nowrap}.dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 18px var(--green)}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:30px 0 26px}.metric{padding:18px;background:rgba(15,24,35,.86);border:1px solid var(--line);border-radius:18px}.metric strong{display:block;font-size:30px}.metric span{color:var(--muted);font-size:12px;letter-spacing:.08em;text-transform:uppercase}.funnel{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:10px 0 30px}.funnel .step{padding:16px;background:#0b141e;border:1px solid #26374a;border-radius:16px}.funnel .step b{display:block;font-size:24px;margin-bottom:3px}.funnel .step span{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.07em}.section-head{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:34px 0 14px}.section-head h2{margin:0;font-size:25px}.section-head p{margin:0;color:var(--muted);max-width:760px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.card{background:linear-gradient(180deg,rgba(17,29,42,.95),rgba(11,19,28,.95));border:1px solid var(--line);border-radius:20px;padding:22px}.card.review{border-color:#315a4f}.card.dismiss{opacity:.75}.card h3{margin:12px 0 7px;font-size:21px;line-height:1.25}.meta,.summary,.small{color:var(--muted)}.summary{margin:8px 0 0}.badges{display:flex;flex-wrap:wrap;gap:7px}.badge{display:inline-flex;padding:5px 9px;border:1px solid #33465c;border-radius:999px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#c8d6e5}.badge.review{color:#09121a;background:var(--green);border-color:var(--green);font-weight:800}.badge.watch{color:#1d1600;background:var(--yellow);border-color:var(--yellow);font-weight:800}.badge.dismiss{color:#d7dee8;background:#34404e;border-color:#34404e;font-weight:800}.badge.signal{color:var(--accent);border-color:#315b73}.badge.verified{color:var(--green);border-color:#326b59}.block{margin-top:16px;padding:14px;border:1px solid #233247;border-radius:14px;background:#0a121b}.block h4{margin:0 0 7px;color:#d8e5ef;font-size:12px;text-transform:uppercase;letter-spacing:.08em}.block p{margin:0;color:#aebcca}.block.reco{border-color:#315a4f;background:#0b1716}.block.supply{border-color:#51476d;background:#12101c}.evidence{margin-top:14px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:13px}a{color:var(--accent);text-decoration:none}.empty{padding:28px;border:1px dashed #334153;border-radius:18px;color:var(--muted)}.footer{margin-top:38px;color:#6f8194;font-size:12px}@media(max-width:1000px){.funnel{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:820px){.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.funnel{grid-template-columns:repeat(2,minmax(0,1fr))}.topbar{flex-direction:column}.section-head{align-items:flex-start;flex-direction:column}}
"""


def _assessment_card(candidate: GapCandidate, assessment: WorldLeadAssessment) -> str:
    cls = assessment.final_recommendation.lower()
    badge_cls = "review" if assessment.final_recommendation == "REVIEW" else ("watch" if assessment.final_recommendation == "WATCH" else "dismiss")
    evidence = assessment.supply_evidence[:4]
    if evidence:
        evidence_html = "<br>".join(
            f'<a href="{escape(str(row.get("url") or "#"))}" target="_blank" rel="noreferrer">{escape(str(row.get("title") or row.get("source") or "supply evidence"))}</a>'
            for row in evidence
        )
    else:
        evidence_html = "No qualifying supply evidence surfaced in the checked sources."
    coverage = f"checked: {', '.join(assessment.supply_sources_checked) or 'none'}"
    if assessment.supply_sources_missing:
        coverage += f" · missing: {', '.join(assessment.supply_sources_missing)}"
    return f"""
    <article class="card {escape(cls)}">
      <div class="badges"><span class="badge {badge_cls}">{escape(assessment.final_recommendation)}</span><span class="badge signal">{escape(assessment.gap_assessment)}</span><span class="badge">{escape(candidate.change_type.replace('_',' '))}</span></div>
      <h3>{escape(candidate.headline)}</h3>
      <div class="meta">{escape(candidate.source)} · {escape(candidate.published_at or 'time unavailable')}</div>
      <div class="block reco"><h4>Gap hypothesis</h4><p><b>Why now:</b> {escape(candidate.why_now)}<br><br><b>Potential gap:</b> {escape(candidate.gap_hypothesis)}</p></div>
      <div class="block supply"><h4>Supply map + gap judgement</h4><p><b>Supply:</b> {escape(assessment.supply_status)} · {assessment.supply_candidate_count} candidates scanned<br><b>Coverage:</b> {escape(assessment.supply_coverage)} · {escape(coverage)}<br><br>{escape(assessment.summary)}</p></div>
      <div class="block"><h4>Supply evidence</h4><p>{evidence_html}</p></div>
      <div class="evidence"><span class="small">ecosystem: {escape(assessment.ecosystem)} · event status: {escape(candidate.validation_status)}</span><a href="{escape(candidate.url)}" target="_blank" rel="noreferrer">source event ↗</a></div>
    </article>"""


def _candidate_card(row: GapCandidate) -> str:
    return f"""
    <article class="card">
      <div class="badges"><span class="badge watch">UNDER INVESTIGATION</span><span class="badge signal">{escape(row.change_type.replace('_',' '))}</span></div>
      <h3>{escape(row.headline)}</h3><div class="meta">{escape(row.source)} · {escape(row.published_at or 'time unavailable')}</div>
      <p class="summary">{escape((row.summary or 'No feed summary supplied.')[:650])}</p>
      <div class="block"><h4>Discovery status</h4><p>{escape(row.validation_summary)}</p></div>
      <div class="evidence"><span class="small">Matched signal: “{escape(row.matched_signal)}”</span><a href="{escape(row.url)}" target="_blank" rel="noreferrer">open source ↗</a></div>
    </article>"""


def _verified_card(event: MarketEvent) -> str:
    dossier = build_dossier(event)
    official = event.official_evidence[0] if event.official_evidence else None
    link = f'<a href="{escape(str(official.url))}" target="_blank" rel="noreferrer">official source ↗</a>' if official else "no official source"
    hypothesis = event.demand_hypothesis
    h = hypothesis.job_to_be_done if hypothesis else "Demand hypothesis unavailable."
    return f"""
    <article class="card">
      <div class="badges"><span class="badge verified">TIER-1 VERIFIED</span><span class="badge signal">{escape(event.gap_status)}</span></div>
      <h3>{escape(event.headline)}</h3><div class="meta">{escape(event.vendor)} · {escape(event.product)}</div>
      <div class="block reco"><h4>Demand hypothesis</h4><p>{escape(h)}</p></div>
      <div class="block supply"><h4>Verified-event conclusion</h4><p>{escape(dossier.verdict)} — {escape(dossier.rationale)}</p></div>
      <div class="evidence"><span class="small">Reaction: {len(event.reaction_evidence)} · Supply: {len(event.supply_evidence)}</span>{link}</div>
    </article>"""


def render_dashboard(events: list[MarketEvent], output: Path, world_candidates: list[GapCandidate] | None = None, scan_stats: WorldScanStats | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    world_candidates = world_candidates or []
    assessments = load_assessments(Path("data/world-assessments.json"))
    by_id = {item.candidate_id: item for item in assessments}
    assessed_pairs = [(candidate, by_id[candidate.id]) for candidate in world_candidates if candidate.id in by_id]
    order = {"REVIEW": 0, "WATCH": 1, "DISMISS": 2}
    assessed_pairs.sort(key=lambda pair: (order.get(pair[1].final_recommendation, 9), pair[0].published_at or ""))
    unresolved = [candidate for candidate in world_candidates if candidate.id not in by_id]
    review_count = sum(1 for _, a in assessed_pairs if a.final_recommendation == "REVIEW")
    watch_count = sum(1 for _, a in assessed_pairs if a.final_recommendation == "WATCH")
    served_count = sum(1 for _, a in assessed_pairs if a.final_recommendation == "DISMISS")
    raw_entries = scan_stats.raw_entries if scan_stats else len(world_candidates)
    recent_entries = scan_stats.recent_entries if scan_stats else len(world_candidates)
    structural_matches = scan_stats.structural_matches if scan_stats else len(world_candidates)
    source_health = f"{scan_stats.sources_ok}/{scan_stats.sources_configured} discovery sources healthy" if scan_stats else "discovery source health unavailable"
    reviewed_cards = "\n".join(_assessment_card(c, a) for c, a in assessed_pairs) or '<div class="empty">No world leads have completed supply deep-dive yet.</div>'
    unresolved_cards = "\n".join(_candidate_card(row) for row in unresolved[:30]) or '<div class="empty">All current world leads have completed deep-dive.</div>'
    verified_cards = "\n".join(_verified_card(event.verify()) for event in events) or '<div class="empty">No separate first-party changelog events in the current window.</div>'

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GapRadar — Today’s Market Gaps</title><style>{CSS}</style></head><body><main>
<div class="topbar"><div><div class="eyebrow">Market Gap Intelligence · Today</div><h1>Today’s Market Gaps</h1><p class="lede">GapRadar scans world changes, forms a demand hypothesis, maps existing supply, then shows the gaps worth human attention. News is an input. The product is the market-gap judgement.</p></div><div class="pulse"><span class="dot"></span> {escape(source_health)}</div></div>
<section class="metrics"><div class="metric"><strong>{review_count}</strong><span>review now</span></div><div class="metric"><strong>{watch_count}</strong><span>watch</span></div><div class="metric"><strong>{served_count}</strong><span>likely served</span></div><div class="metric"><strong>{len(unresolved)}</strong><span>still investigating</span></div></section>
<div class="section-head"><div><div class="eyebrow">Recommended + validated summary</div><h2>Deep-dived market gaps</h2></div><p>These leads have already passed through supply mapping. Supply conclusions are coverage-bound; missing sources are shown instead of being silently treated as no competition.</p></div><section class="grid">{reviewed_cards}</section>
<div class="section-head"><div><div class="eyebrow">Pipeline health</div><h2>Today’s discovery funnel</h2></div><p>A correct day may end with zero REVIEW results. The funnel exists to expose whether discovery is too loose, too strict, or source-degraded.</p></div>
<section class="funnel"><div class="step"><b>{raw_entries}</b><span>raw items</span></div><div class="step"><b>{recent_entries}</b><span>inside lookback</span></div><div class="step"><b>{structural_matches}</b><span>structural matches</span></div><div class="step"><b>{len(world_candidates)}</b><span>deduped leads</span></div><div class="step"><b>{len(assessed_pairs)}</b><span>supply deep-dives</span></div><div class="step"><b>{review_count}</b><span>review now</span></div></section>
<div class="section-head"><div><div class="eyebrow">Under investigation</div><h2>Structural changes not yet deep-dived</h2></div><p>These are not called gaps yet.</p></div><section class="grid">{unresolved_cards}</section>
<div class="section-head"><div><div class="eyebrow">Tier-1 lane</div><h2>Officially verified changelog events</h2></div><p>The older first-party verification lane remains visible, but it no longer defines the whole product.</p></div><section class="grid">{verified_cards}</section>
<div class="footer">GapRadar · WORLD SCAN → CANDIDATE → DEMAND HYPOTHESIS → SUPPLY MAP → GAP ASSESSMENT → DOSSIER. Reaction remains supporting evidence, never a veto.</div>
</main></body></html>"""
    output.write_text(html, encoding="utf-8")
