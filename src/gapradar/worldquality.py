from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
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
    r"\b(power|power station|plant|factory|mine|refinery|reactor|nuclear plant|airport|road|school|store|restaurant|facility|operations?|station|stations|rail|line)\b.{0,60}\bshutdown\b|\bshutdown\b.{0,60}\b(power|plant|factory|mine|refinery|reactor|nuclear|facility|operations?|station|stations|rail|line)\b",
    re.I,
)
RHETORICAL_SHUTDOWN = re.compile(
    r"\bfrom\s+(?:the\s+)?shutdown\s+to\b|\bafter\s+(?:the\s+)?shutdown\b.{0,80}\b(reopen|restart|reviv|return|showcase|ipo)\b|\b(reopen|reopens?|reopened|restart|restarts?|resumes?)\b.{0,100}\bshutdown\b",
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
SPECULATIVE_REGULATION = re.compile(
    r"\b(may|might|could|would)\s+(?:soon\s+)?(?:require|mandate|ban|force|introduce)\b"
    r"|\b(promises?|pledges?|proposes?|proposal|seeks?|calls? for|urges?|pushes? for)\b.{0,80}\b(rule|rules|regulation|mandate|requirement|ban)\b"
    r"|\b(bid|attempt|plan)\s+to\s+(?:revoke|change|introduce|impose)\b"
    r"|\bmandate\s+(?:looms?|possible|proposed|planned)\b"
    r"|\bneared\b.{0,50}\bmandate\b.{0,50}\b(fell short|missed)\b"
    r"|\bchallenges?\b.{0,80}\b(price increase|rule|regulation|mandate)\b"
    r"|\b(trade war|trade tactics?)\b.{0,100}\bmandate\b",
    re.I,
)
TOKEN_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at", "by", "from", "with",
    "new", "latest", "today", "says", "say", "will", "may", "could", "after", "before", "amid",
}


@dataclass(frozen=True)
class WorldQualityReport:
    input_candidates: int
    context_rejected: int
    duplicate_collapsed: int
    kept_candidates: int
    rejection_reasons: dict[str, int]


def rejection_reason(candidate: GapCandidate) -> str | None:
    text = f"{candidate.headline} {candidate.summary}".strip()

    if candidate.change_type == "shutdown_eol":
        if RHETORICAL_SHUTDOWN.search(text):
            return "rhetorical_or_completed_shutdown_context"
        if PHYSICAL_SHUTDOWN.search(text) and not DIGITAL_TARGET.search(text):
            return "physical_shutdown_not_product_eol"

    if candidate.change_type == "regulatory_shift":
        if NEGATED_MANDATE.search(text):
            return "negated_mandate"
        if BUSINESS_MANDATE.search(text):
            return "commercial_mandate_not_regulation"
        if SPECULATIVE_REGULATION.search(text):
            return "speculative_or_proposed_regulation"

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


def _event_tokens(candidate: GapCandidate) -> set[str]:
    text = candidate.headline.lower().replace("’", "'")
    words = re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", text)
    return {word for word in words if word not in TOKEN_STOP}


def _event_similarity(left: GapCandidate, right: GapCandidate) -> float:
    if left.change_type != right.change_type:
        return 0.0
    a, b = _event_tokens(left), _event_tokens(right)
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    jaccard = overlap / len(a | b)
    containment = overlap / min(len(a), len(b))
    return max(jaccard, containment * 0.92)


def _prefer(left: GapCandidate, right: GapCandidate) -> GapCandidate:
    left_score = (len(left.summary or ""), left.published_at or "", len(left.headline))
    right_score = (len(right.summary or ""), right.published_at or "", len(right.headline))
    return left if left_score >= right_score else right


def collapse_duplicate_events(candidates: list[GapCandidate], threshold: float = 0.78) -> tuple[list[GapCandidate], int]:
    clusters: list[GapCandidate] = []
    collapsed = 0
    for candidate in sorted(candidates, key=lambda row: row.published_at or row.discovered_at, reverse=True):
        match_index = None
        for index, existing in enumerate(clusters):
            if _event_similarity(candidate, existing) >= threshold:
                match_index = index
                break
        if match_index is None:
            clusters.append(candidate)
        else:
            clusters[match_index] = _prefer(clusters[match_index], candidate)
            collapsed += 1
    clusters.sort(key=lambda row: row.published_at or row.discovered_at, reverse=True)
    return clusters, collapsed


def refine_candidates(candidates: list[GapCandidate]) -> tuple[list[GapCandidate], list[tuple[str, str]], int]:
    kept: list[GapCandidate] = []
    rejected: list[tuple[str, str]] = []
    for candidate in candidates:
        refined = refine_candidate(candidate)
        if refined is None:
            rejected.append((candidate.id, rejection_reason(candidate) or "context_rejected"))
        else:
            kept.append(refined)
    deduped, collapsed = collapse_duplicate_events(kept)
    return deduped, rejected, collapsed


def save_report(path: Path, report: WorldQualityReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(path: Path = Path("data/world-gaps.json"), report_path: Path = Path("data/world-quality-report.json")) -> tuple[int, int, int]:
    candidates = load_candidates(path)
    kept, rejected, collapsed = refine_candidates(candidates)
    save_candidates(path, kept)
    reasons: dict[str, int] = {}
    for _, reason in rejected:
        reasons[reason] = reasons.get(reason, 0) + 1
    save_report(report_path, WorldQualityReport(len(candidates), len(rejected), collapsed, len(kept), reasons))
    print(
        f"World quality guard: {len(candidates)} input → {len(kept)} kept; "
        f"rejected {len(rejected)} contextual false positive(s), collapsed {collapsed} duplicate event(s)."
    )
    for candidate_id, reason in rejected[:20]:
        print(f"  - {candidate_id}: {reason}")
    return len(kept), len(rejected), collapsed


if __name__ == "__main__":
    run()
