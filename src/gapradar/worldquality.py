from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from .worldscan import GapCandidate, load_candidates, save_candidates

PROVISIONAL_WHY = (
    "Automatically discovered structural-change lead; event type remains provisional until the evidence chain confirms context."
)
PROVISIONAL_GAP = (
    "No market-opportunity conclusion is allowed before Tier-1 first-party verification and downstream demand/supply analysis."
)

DIGITAL_TARGET = re.compile(
    r"\b(software|saas|app|apps|application|platform|api|sdk|integration|extension|cloud|developer|service|tool|subscription|streaming|product|feature|model|device|devices|podcast|whiteboard)\b",
    re.I,
)
PHYSICAL_SHUTDOWN = re.compile(
    r"\b(power|power station|plant|factory|mine|refinery|reactor|nuclear plant|airport|road|school|store|restaurant|facility|operations?)\b.{0,40}\bshutdown\b|\bshutdown\b.{0,40}\b(power|plant|factory|mine|refinery|reactor|nuclear|facility|operations?)\b",
    re.I,
)
RHETORICAL_SHUTDOWN = re.compile(
    r"\bfrom\s+(?:the\s+)?shutdown\s+to\b|\bafter\s+(?:the\s+)?shutdown\b.{0,80}\b(reopen|restart|reviv|return|showcase|ipo)\b",
    re.I,
)
NEGATED_MANDATE = re.compile(
    r"\b(?:isn['’]?t|is not|not|no)\s+(?:an?\s+)?(?:ev\s+|government\s+|legal\s+)?mandate\b|\bmandate\b.{0,20}\b(?:isn['’]?t|is not|not required)\b",
    re.I,
)
BUSINESS_MANDATE = re.compile(
    r"\b(wins?|won|selected|awarded|secures?|lands?|gets?)\b.{0,80}\bmandate\b|\b(investment|asset management|fund|pension|portfolio)\s+mandate\b|\bmandate\s+from\b.{0,80}\b(fund|pension|client|investor)\b",
    re.I,
)


def rejection_reason(candidate: GapCandidate) -> str | None:
    text = f"{candidate.headline} {candidate.summary}".strip()

    if candidate.change_type == "shutdown_eol":
        if RHETORICAL_SHUTDOWN.search(text):
            return "rhetorical_shutdown_context"
        if PHYSICAL_SHUTDOWN.search(text) and not DIGITAL_TARGET.search(text):
            return "physical_shutdown_not_product_eol"

    if candidate.change_type == "regulatory_shift":
        if NEGATED_MANDATE.search(text):
            return "negated_mandate"
        if BUSINESS_MANDATE.search(text):
            return "commercial_mandate_not_regulation"

    return None


def refine_candidate(candidate: GapCandidate) -> GapCandidate | None:
    reason = rejection_reason(candidate)
    if reason:
        return None
    return replace(
        candidate,
        recommendation="WATCH",
        why_now=PROVISIONAL_WHY,
        gap_hypothesis=PROVISIONAL_GAP,
        validation_summary=(
            f"{candidate.validation_summary} Context quality guard passed. "
            "This remains a discovery lead until Tier-1 first-party evidence verifies the underlying event."
        ),
    )


def refine_candidates(candidates: list[GapCandidate]) -> tuple[list[GapCandidate], list[tuple[str, str]]]:
    kept: list[GapCandidate] = []
    rejected: list[tuple[str, str]] = []
    for candidate in candidates:
        refined = refine_candidate(candidate)
        if refined is None:
            rejected.append((candidate.id, rejection_reason(candidate) or "context_rejected"))
        else:
            kept.append(refined)
    return kept, rejected


def run(path: Path = Path("data/world-gaps.json")) -> tuple[int, int]:
    candidates = load_candidates(path)
    kept, rejected = refine_candidates(candidates)
    save_candidates(path, kept)
    print(f"World quality guard: kept {len(kept)}/{len(candidates)} candidate(s); rejected {len(rejected)} contextual false positive(s).")
    for candidate_id, reason in rejected[:20]:
        print(f"  - {candidate_id}: {reason}")
    return len(kept), len(rejected)


if __name__ == "__main__":
    run()
