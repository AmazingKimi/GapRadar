from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from .models import MarketEvent


@dataclass(frozen=True)
class OpportunityDossier:
    event_id: str
    vendor: str
    product: str
    headline: str
    verdict: str
    rationale: str
    what_changed: str
    displaced_demand: list[dict[str, object]]
    replacement_supply: list[dict[str, object]]
    unresolved_gap: str
    next_action: str
    evidence_counts: dict[str, int]
    reaction_search_quality: str
    reaction_queries: list[dict[str, object]]


def _clean(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]


def _verdict(event: MarketEvent) -> tuple[str, str, str]:
    if event.status != "verified":
        return (
            "INSUFFICIENT EVIDENCE",
            "The event does not have qualifying first-party verification.",
            "Do not investigate commercially until the event itself is verified.",
        )
    if event.demand_status == "unassessed":
        if event.reaction_search_quality == "failed":
            return (
                "SEARCH FAILED",
                "The event is verified, but the demand search did not complete successfully.",
                "Repair or rerun reaction search before making any demand conclusion.",
            )
        return (
            "NEEDS DEMAND CHECK",
            "A real market change is verified, but displaced demand has not been adequately assessed.",
            "Run reaction validation before spending time on substitutes or product design.",
        )
    if event.demand_status == "no_signal":
        return (
            "NO DETECTED SIGNAL",
            "The checked queries found no qualifying displaced-demand evidence. This means demand was not detected, not that demand does not exist.",
            "Do not infer zero demand. Keep monitoring, inspect the recorded queries, and broaden sources if this event is strategically important.",
        )
    if event.supply_status == "unassessed":
        return (
            "WATCH",
            "Displaced-demand evidence exists, but replacement supply has not been assessed.",
            "Map credible substitutes before deciding whether a gap exists.",
        )
    if event.gap_status == "likely_served":
        return (
            "LIKELY SERVED",
            "Displaced demand exists, but credible replacement supply already appears strong.",
            "Do not clone the displaced product. Look only for specific complaints that existing substitutes fail to solve.",
        )
    if event.gap_status == "potential_gap":
        return (
            "REVIEW",
            "Repeated displaced demand survived the replacement-supply check; the evidence supports human opportunity review.",
            "Interview affected users and define the narrow unmet job before writing product code.",
        )
    return (
        "WATCH",
        "Some displaced-demand evidence exists, but it is not yet strong enough to establish an underserved gap.",
        "Keep monitoring for repeated pain, failed migrations, and evidence that substitutes are inadequate.",
    )


def build_dossier(event: MarketEvent) -> OpportunityDossier:
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

    if event.gap_status == "potential_gap":
        unresolved = "Repeated migration pain is visible while qualifying replacement supply is absent or thin. The exact unmet job still requires human validation."
    elif event.gap_status == "likely_served":
        unresolved = "No broad supply gap is established. Any opportunity would need to come from a narrower failure shared across existing substitutes."
    elif event.demand_status == "no_signal":
        unresolved = "No migration pain was detected by the recorded queries. This is a detection result, not proof that no displaced demand exists."
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
        "## Evidence chain",
        "",
        f"- Tier 1 official: {dossier.evidence_counts['tier_1_official']}",
        f"- Tier 2 migration-pain reactions: {dossier.evidence_counts['tier_2_reaction']} (from {dossier.evidence_counts['reaction_candidates_checked']} unique candidates checked)",
        f"- Reaction search quality: `{dossier.reaction_search_quality}`",
        f"- Tier 3 replacement supply: {dossier.evidence_counts['tier_3_supply']} (from {dossier.evidence_counts['supply_candidates_checked']} candidates checked)",
        f"- Demand state: `{event.demand_status}`",
        f"- Supply state: `{event.supply_status}`",
        f"- Gap state: `{event.gap_status}`",
        "",
    ]
    if official:
        lines.extend([f"Official source: {official.url}", ""])

    lines.extend(["## Reaction queries", ""])
    if dossier.reaction_queries:
        for row in dossier.reaction_queries:
            status = "ok" if row.get("ok") else "failed"
            lines.append(f"- `{row.get('source')}` · {status} · {row.get('candidate_count', 0)} candidates · `{row.get('query')}`")
    else:
        lines.append("No reaction query audit is available.")

    lines.extend(["", "## Displaced demand", ""])
    if dossier.displaced_demand:
        for row in dossier.displaced_demand:
            lines.append(f"- [{row['title']}]({row['url']}) — {row['publisher']} · signal {row['signal_score']} · engagement {row['engagement']}")
    else:
        lines.append("No qualifying migration-pain evidence was detected in the checked queries.")

    lines.extend(["", "## Replacement supply", ""])
    if dossier.replacement_supply:
        for row in dossier.replacement_supply:
            lines.append(f"- [{row['title']}]({row['url']}) — {row['publisher']} · relevance {row['signal_score']} · popularity {row['engagement']}")
    else:
        if event.supply_checked_at:
            lines.append("No qualifying replacement supply found in the checked sources.")
        else:
            lines.append("Supply analysis was not run because the event did not survive the demand gate, or because supply is not yet assessed.")

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
        "Generated by GapRadar v0.6. This dossier is an evidence review, not a revenue forecast or instruction to build.",
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
