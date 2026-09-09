from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from .models import MarketEvent
from .routing import reaction_coverage


@dataclass(frozen=True)
class OpportunityDossier:
    event_id: str
    vendor: str
    product: str
    headline: str
    verdict: str
    rationale: str
    what_changed: str
    demand_hypothesis: dict[str, object] | None
    displaced_demand: list[dict[str, object]]
    replacement_supply: list[dict[str, object]]
    unresolved_gap: str
    next_action: str
    evidence_counts: dict[str, int]
    reaction_search_quality: str
    reaction_queries: list[dict[str, object]]
    reaction_coverage: dict[str, object]


def _clean(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]


def _coverage_sentence(event: MarketEvent) -> str:
    coverage = reaction_coverage(event)
    checked = ", ".join(str(item) for item in coverage["checked_sources"]) or "none"
    missing = ", ".join(str(item) for item in coverage["missing_sources"]) or "none"
    return f"Checked: {checked}. Preferred-but-unchecked ecosystem sources: {missing}."


def _verdict(event: MarketEvent) -> tuple[str, str, str]:
    if event.status != "verified":
        return (
            "INSUFFICIENT EVIDENCE",
            "The event does not have qualifying first-party verification.",
            "Do not investigate commercially until the event itself is verified.",
        )
    if event.demand_hypothesis is None:
        return (
            "NEEDS HYPOTHESIS",
            "The market change is verified, but GapRadar has not yet recorded an explicit demand hypothesis.",
            "Record the affected users, job-to-be-done, disruption, basis and unknowns before judging the gap.",
        )
    if event.supply_status == "unassessed":
        reaction_context = "Reaction search failed, but that does not block supply analysis." if event.reaction_search_quality == "failed" else "Reaction evidence is optional supporting context."
        return (
            "NEEDS SUPPLY CHECK",
            f"A verified change and explicit demand hypothesis exist. {reaction_context}",
            "Map credible replacement supply before deciding whether the hypothesis points to an underserved gap.",
        )
    if event.gap_status == "likely_served":
        return (
            "LIKELY SERVED",
            "The demand hypothesis exists, but credible replacement supply already appears strong.",
            "Do not clone the incumbent. Look only for a narrower job existing substitutes handle badly.",
        )
    if event.gap_status == "potential_gap":
        return (
            "REVIEW",
            "A verified demand hypothesis has repeated reaction support and replacement supply appears absent or thin.",
            "Interview affected users and define the narrow unmet job before writing product code.",
        )
    if event.gap_status == "watch":
        reaction_note = (
            "Repeated reaction evidence is not present, so confidence remains bounded. " + _coverage_sentence(event)
            if event.demand_status in {"no_signal", "unassessed"}
            else "Some reaction evidence supports the hypothesis, but the chain is still early."
        )
        return (
            "WATCH",
            "The demand hypothesis survived supply analysis, but evidence is not strong enough for REVIEW. " + reaction_note,
            "Keep the hypothesis alive, improve reaction coverage where useful, and inspect whether the remaining supply actually satisfies the affected job.",
        )
    return (
        "WATCH",
        "The event is verified and the demand hypothesis is recorded, but the commercial evidence chain is incomplete.",
        "Continue supply and evidence review without treating missing reaction as proof of no demand.",
    )


def build_dossier(event: MarketEvent) -> OpportunityDossier:
    event.verify()
    verdict, rationale, next_action = _verdict(event)
    reactions = [
        {
            "title": item.title,
            "url": str(item.url),
            "publisher": item.publisher,
            "excerpt": _clean(item.excerpt, 420),
            "signal_score": item.signal_score,
            "engagement": item.engagement,
        }
        for item in event.reaction_evidence[:8]
    ]
    supply = [
        {
            "title": item.title,
            "url": str(item.url),
            "publisher": item.publisher,
            "excerpt": _clean(item.excerpt, 420),
            "signal_score": item.signal_score,
            "engagement": item.engagement,
        }
        for item in event.supply_evidence[:8]
    ]
    hypothesis = event.demand_hypothesis.model_dump() if event.demand_hypothesis else None

    if event.gap_status == "potential_gap":
        unresolved = "Repeated migration pain is visible while qualifying replacement supply is absent or thin. The exact unmet job still requires human validation."
    elif event.gap_status == "likely_served":
        unresolved = "No broad supply gap is established. Any opportunity would need to come from a narrower failure shared across existing substitutes."
    elif event.gap_status == "watch":
        unresolved = "A plausible demand hypothesis remains after supply review, but confidence is still bounded. Missing reaction evidence does not invalidate the hypothesis."
    else:
        unresolved = "The evidence chain is incomplete; GapRadar does not infer the missing commercial conclusion."

    return OpportunityDossier(
        event_id=event.id,
        vendor=event.vendor,
        product=event.product,
        headline=event.headline,
        verdict=verdict,
        rationale=rationale,
        what_changed=_clean(event.summary),
        demand_hypothesis=hypothesis,
        displaced_demand=reactions,
        replacement_supply=supply,
        unresolved_gap=unresolved,
        next_action=next_action,
        evidence_counts={
            "tier_1_official": len(event.official_evidence),
            "tier_2_reaction": len(event.reaction_evidence),
            "tier_3_supply": len(event.supply_evidence),
            "reaction_candidates_checked": event.reaction_candidate_count,
            "supply_candidates_checked": event.supply_candidate_count,
        },
        reaction_search_quality=event.reaction_search_quality,
        reaction_queries=list(event.reaction_queries),
        reaction_coverage=reaction_coverage(event),
    )


def _markdown(dossier: OpportunityDossier, event: MarketEvent) -> str:
    official = event.official_evidence[0] if event.official_evidence else None
    lines = [
        f"# {dossier.vendor} — {dossier.product}",
        "",
        f"**Verdict: {dossier.verdict}**",
        "",
        dossier.rationale,
        "",
        "## What changed",
        "",
        dossier.what_changed,
        "",
        "## Demand hypothesis",
        "",
    ]
    if dossier.demand_hypothesis:
        h = dossier.demand_hypothesis
        lines.extend([
            f"- Confidence: `{h.get('confidence', 'low')}`",
            f"- Affected users: {h.get('affected_users', '')}",
            f"- Job to be done: {h.get('job_to_be_done', '')}",
            f"- Disruption: {h.get('disruption', '')}",
            f"- Official successor: {h.get('official_successor', 'unknown')}",
            f"- Basis: {'; '.join(str(x) for x in h.get('basis', [])) or 'none recorded'}",
            f"- Unknowns: {'; '.join(str(x) for x in h.get('unknowns', [])) or 'none recorded'}",
        ])
    else:
        lines.append("No explicit demand hypothesis recorded.")

    lines.extend([
        "",
        "## Evidence chain",
        "",
        f"- Tier 1 official: {dossier.evidence_counts['tier_1_official']}",
        f"- Tier 2 migration-pain reactions: {dossier.evidence_counts['tier_2_reaction']} (from {dossier.evidence_counts['reaction_candidates_checked']} unique candidates checked)",
        f"- Reaction search quality: `{dossier.reaction_search_quality}`",
        f"- Reaction ecosystem: `{dossier.reaction_coverage['ecosystem']}`",
        f"- Checked reaction sources: {', '.join(dossier.reaction_coverage['checked_sources']) or 'none'}",
        f"- Preferred but unchecked: {', '.join(dossier.reaction_coverage['missing_sources']) or 'none'}",
        f"- Tier 3 replacement supply: {dossier.evidence_counts['tier_3_supply']} (from {dossier.evidence_counts['supply_candidates_checked']} candidates checked)",
        f"- Demand state: `{event.demand_status}`",
        f"- Supply state: `{event.supply_status}`",
        f"- Gap state: `{event.gap_status}`",
        "",
    ])
    if official:
        lines.extend([f"Official source: {official.url}", ""])

    lines.extend(["## Reaction queries", ""])
    if dossier.reaction_queries:
        for row in dossier.reaction_queries:
            status = "ok" if row.get("ok") else "failed"
            lines.append(f"- `{row.get('source')}` · {status} · {row.get('candidate_count', 0)} candidates · `{row.get('query')}`")
    else:
        lines.append("No reaction query audit is available.")

    lines.extend(["", "## Supporting reaction evidence", ""])
    if dossier.displaced_demand:
        for row in dossier.displaced_demand:
            lines.append(f"- [{row['title']}]({row['url']}) — {row['publisher']} · signal {row['signal_score']} · engagement {row['engagement']}")
    else:
        lines.append("No qualifying migration-pain evidence was detected in the checked queries. This does not invalidate the demand hypothesis.")

    lines.extend(["", "## Replacement supply", ""])
    if dossier.replacement_supply:
        for row in dossier.replacement_supply:
            lines.append(f"- [{row['title']}]({row['url']}) — {row['publisher']} · relevance {row['signal_score']} · popularity {row['engagement']}")
    else:
        if event.supply_checked_at:
            lines.append("No qualifying replacement supply found in the checked sources.")
        else:
            lines.append("Supply analysis has not run yet. Reaction evidence is not a prerequisite for running it.")

    lines.extend([
        "",
        "## What remains unsolved",
        "",
        dossier.unresolved_gap,
        "",
        "## Next action",
        "",
        dossier.next_action,
        "",
        "---",
        "Generated by GapRadar. This dossier is an evidence review, not a revenue forecast or instruction to build.",
        "",
    ])
    return "\n".join(lines)


def export_dossiers(events: list[MarketEvent], output_dir: Path, index_path: Path | None = None) -> list[OpportunityDossier]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dossiers = [build_dossier(event) for event in events]
    for event, dossier in zip(events, dossiers):
        (output_dir / f"{event.id}.md").write_text(_markdown(dossier, event), encoding="utf-8")
        (output_dir / f"{event.id}.json").write_text(json.dumps(asdict(dossier), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if index_path:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps([asdict(item) for item in dossiers], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dossiers
