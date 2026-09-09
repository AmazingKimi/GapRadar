from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from .officialfinder import OfficialSourceLead
from .worlddeep import WorldLeadAssessment
from .worldscan import GapCandidate
from .worldverify import WorldVerification


@dataclass(frozen=True)
class PriorityLead:
    candidate_id: str
    status: str
    priority_score: int
    evidence_state: str
    evidence_label: str
    reason: str
    next_check: str


CHANGE_LABELS = {
    "shutdown_eol": "shutdown / end-of-life",
    "price_shock": "price shock",
    "api_terms_change": "API / terms change",
    "regulatory_shift": "regulatory requirement",
}

IMPACT = {
    "shutdown_eol": "migration or replacement demand before the affected product disappears",
    "price_shock": "switching demand from customers exposed to the new cost",
    "api_terms_change": "integration, compatibility or dependency-replacement work",
    "regulatory_shift": "new compliance, testing, reporting or implementation work",
}

MAJOR_ENTITY = re.compile(
    r"\b(apple|google|microsoft|amazon|aws|meta|adobe|salesforce|shopify|slack|cloudflare|samsung|netflix|spotify|openai|anthropic|oracle|sap|tesla|uber|stripe)\b",
    re.I,
)
CONCRETE_CHANGE = re.compile(
    r"\b(mandatory|must\b|will require|required|shutdown|shut down|sunset|retire|deprecated|deprecation|price hike|price increase|raises? prices?|fee|no longer supported|end of support)\b",
    re.I,
)
FORCED_ACTION = re.compile(
    r"\b(mandatory|must\b|will require|required|no longer supported|end of support|sunset|retire|deprecated|deprecation|shut down|shutdown)\b",
    re.I,
)
BUSINESS_TARGET = re.compile(
    r"\b(data centers?|developers?|businesses?|enterprises?|manufacturers?|operators?|customers?|users?|apps?|services?|platforms?|vehicles?|bms|api|software|saas|integrations?|workflows?)\b",
    re.I,
)
WEAK_OR_SPECULATIVE = re.compile(
    r"\b(may|might|could|considering|reportedly|rumou?r|expected to|plans? to|proposal|proposed)\b",
    re.I,
)
CONSUMER_ONLY = re.compile(
    r"\b(streaming|music subscription|tv subscription|consumer subscription|individual plan|family plan)\b",
    re.I,
)
NUMBER = re.compile(r"(?:[$€£]\s?\d|\b\d+(?:\.\d+)?%|\b20\d{2}\b)")


def _host(url: str | None) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.")


def _publisher(candidate: GapCandidate) -> str:
    summary = unescape(candidate.summary or "").replace("\xa0", " ")
    tail = re.split(r"\s{2,}", summary.strip())
    if len(tail) > 1 and 2 <= len(tail[-1]) <= 80:
        return tail[-1].strip()
    source = (candidate.source or "").replace("Google News · ", "").strip()
    return source or "news discovery"


def _assessment_map(rows: list[WorldLeadAssessment]) -> dict[str, WorldLeadAssessment]:
    return {row.candidate_id: row for row in rows}


def _lead_map(rows: list[OfficialSourceLead]) -> dict[str, OfficialSourceLead]:
    return {row.candidate_id: row for row in rows}


def _verification_map(rows: dict[str, WorldVerification] | list[WorldVerification]) -> dict[str, WorldVerification]:
    return rows if isinstance(rows, dict) else {row.candidate_id: row for row in rows}


def score_candidate(
    candidate: GapCandidate,
    verification: WorldVerification | None,
    assessment: WorldLeadAssessment | None,
    official_lead: OfficialSourceLead | None,
) -> int:
    """Rank scarce research attention; this is deliberately not an opportunity score."""
    text = f"{candidate.headline} {candidate.summary}"
    concrete = bool(CONCRETE_CHANGE.search(text))
    forced = bool(FORCED_ACTION.search(text))
    business_target = bool(BUSINESS_TARGET.search(text))

    # Structural actionability. Shutdown/API changes are often more immediately
    # actionable than generic pricing or regulatory headlines.
    score = {"shutdown_eol": 3, "api_terms_change": 3, "regulatory_shift": 2, "price_shock": 1}.get(candidate.change_type, 0)

    # Evidence is the strongest ranking input. A famous company name must never
    # outrank a less-famous event with better first-party support.
    if verification and verification.status == "tier1_verified" and verification.official_url:
        score += 5
    elif official_lead and official_lead.candidate_urls:
        score += 2

    if concrete:
        score += 1
    if forced:
        score += 2
    if business_target:
        score += 2
    if NUMBER.search(text) and (forced or business_target):
        score += 1

    # Brand prominence is only a weak tie-breaker after there is an actionable
    # business target. It is not evidence of a market gap.
    if MAJOR_ENTITY.search(text) and business_target and concrete:
        score += 1

    # Penalize headlines that are still hypothetical, and consumer-only price
    # changes that have no clear business workflow or switching surface.
    if WEAK_OR_SPECULATIVE.search(candidate.headline) and not (verification and verification.status == "tier1_verified"):
        score -= 2
    if candidate.change_type == "price_shock" and CONSUMER_ONLY.search(text) and not business_target:
        score -= 2

    if assessment:
        if assessment.final_recommendation == "REVIEW":
            score += 4
        elif assessment.final_recommendation == "DISMISS":
            score -= 6
        elif assessment.supply_coverage == "adequate" and assessment.supply_evidence:
            score -= 1

    return max(score, 0)


def _reason(
    candidate: GapCandidate,
    verification: WorldVerification | None,
    assessment: WorldLeadAssessment | None,
    official_lead: OfficialSourceLead | None,
) -> tuple[str, str, str, str]:
    label = CHANGE_LABELS.get(candidate.change_type, "structural change")
    impact = IMPACT.get(candidate.change_type, "follow-on operational work")
    signal = (candidate.matched_signal or label).strip().rstrip(".")
    publisher = _publisher(candidate)
    headline = candidate.headline.strip().rstrip(".")

    if verification and verification.status == "tier1_verified" and verification.official_url:
        host = _host(verification.official_url) or "first-party source"
        if assessment:
            strong = len(assessment.supply_evidence)
            reason = (
                f"{host} confirms the underlying change behind “{headline}”. "
                f"The event is an actionable {label} affecting the demand surface “{impact}”. "
                f"Supply research checked {assessment.supply_candidate_count} candidate(s), found {strong} strong match(es), "
                f"with {assessment.supply_coverage} coverage."
            )
            next_check = "Close remaining supply-coverage gaps and test the explicit demand hypothesis with affected users before promoting this to REVIEW."
        else:
            reason = (
                f"{host} confirms the underlying change behind “{headline}”. "
                f"Because the matched signal is “{signal[:70]}”, the immediate research question is whether it creates material {impact}."
            )
            next_check = "Run demand and replacement-supply analysis before making a market-gap claim."
        return "tier1_verified", f"Tier-1 · {host}", reason, next_check

    if official_lead and official_lead.candidate_urls:
        host = _host(official_lead.candidate_urls[0]) or "official candidate"
        reason = (
            f"{publisher} reports “{headline}”. GapRadar found a plausible authority page on {host}, "
            f"but that page has not yet confirmed the exact “{signal[:70]}” claim. "
            f"If confirmed, investigate {impact}."
        )
        next_check = "Verify the exact claim on the authority page; then decide whether demand/supply research deserves deeper compute and analyst time."
        return "official_candidate", f"Official lead · {host}", reason, next_check

    reason = (
        f"{publisher} reports “{headline}” and the detector matched “{signal[:70]}” as a {label} signal. "
        f"No acceptable first-party source is linked yet, so this remains a research lead rather than an opportunity claim. "
        f"If verified, inspect {impact}."
    )
    next_check = "Locate the responsible company, regulator or filing and verify the exact change; drop the lead if no authoritative confirmation exists."
    return "news_only", "Tier-1 pending", reason, next_check


def build_priority_leads(
    candidates: list[GapCandidate],
    verifications: dict[str, WorldVerification] | list[WorldVerification],
    assessments: list[WorldLeadAssessment],
    official_leads: list[OfficialSourceLead],
) -> list[PriorityLead]:
    vmap = _verification_map(verifications)
    amap = _assessment_map(assessments)
    lmap = _lead_map(official_leads)
    rows: list[PriorityLead] = []
    for candidate in candidates:
        verification = vmap.get(candidate.id)
        assessment = amap.get(candidate.id)
        official_lead = lmap.get(candidate.id)
        score = score_candidate(candidate, verification, assessment, official_lead)
        evidence_state, evidence_label, reason, next_check = _reason(candidate, verification, assessment, official_lead)

        if assessment and assessment.final_recommendation == "REVIEW":
            status = "REVIEW"
        elif assessment and assessment.final_recommendation == "DISMISS":
            status = "DISMISS"
        elif score >= 7:
            # INVESTIGATE = spend scarce research attention now. It is not a
            # statement that an underserved market gap has been proven.
            status = "INVESTIGATE"
        else:
            status = "WATCH"
        rows.append(PriorityLead(candidate.id, status, score, evidence_state, evidence_label, reason, next_check))

    rank = {"REVIEW": 0, "INVESTIGATE": 1, "WATCH": 2, "DISMISS": 3}
    evidence_rank = {"tier1_verified": 0, "official_candidate": 1, "news_only": 2}
    rows.sort(key=lambda row: (rank[row.status], evidence_rank.get(row.evidence_state, 9), -row.priority_score, row.candidate_id))
    return rows


def save_priority_leads(path: Path, rows: list[PriorityLead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_priority_leads(path: Path) -> list[PriorityLead]:
    if not path.exists():
        return []
    return [PriorityLead(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
