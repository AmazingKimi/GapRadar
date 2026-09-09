from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
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
BUSINESS_TARGET = re.compile(
    r"\b(data centers?|developers?|businesses?|enterprises?|manufacturers?|operators?|customers?|users?|apps?|services?|platforms?|vehicles?|bms|api|software|saas)\b",
    re.I,
)
NUMBER = re.compile(r"(?:[$€£]\s?\d|\b\d+(?:\.\d+)?%|\b20\d{2}\b)")


def _host(url: str | None) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.")


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
    score = {"shutdown_eol": 3, "api_terms_change": 3, "price_shock": 2, "regulatory_shift": 2}.get(candidate.change_type, 1)
    text = f"{candidate.headline} {candidate.summary}"
    if verification and verification.status == "tier1_verified" and verification.official_url:
        score += 3
    elif official_lead and official_lead.candidate_urls:
        score += 1
    if CONCRETE_CHANGE.search(text):
        score += 1
    if BUSINESS_TARGET.search(text):
        score += 1
    if NUMBER.search(text):
        score += 1
    if MAJOR_ENTITY.search(text):
        score += 1
    if assessment:
        if assessment.final_recommendation == "REVIEW":
            score += 3
        elif assessment.final_recommendation == "DISMISS":
            score -= 4
    return max(score, 0)


def _reason(
    candidate: GapCandidate,
    verification: WorldVerification | None,
    assessment: WorldLeadAssessment | None,
    official_lead: OfficialSourceLead | None,
) -> tuple[str, str, str]:
    label = CHANGE_LABELS.get(candidate.change_type, "structural change")
    impact = IMPACT.get(candidate.change_type, "follow-on operational work")
    signal = (candidate.matched_signal or label).strip().rstrip(".")

    if verification and verification.status == "tier1_verified" and verification.official_url:
        host = _host(verification.official_url) or "first-party source"
        if assessment:
            strong = len(assessment.supply_evidence)
            reason = (
                f"Tier-1 confirmed on {host}. The event creates a plausible surface for {impact}. "
                f"Supply check searched {assessment.supply_candidate_count} candidates and found {strong} strong match(es); "
                f"coverage is {assessment.supply_coverage}."
            )
            next_check = "Resolve the remaining supply-coverage gaps and test the demand hypothesis with affected users."
        else:
            reason = f"Tier-1 confirmed on {host}. The reported {label} creates a plausible surface for {impact}."
            next_check = "Run demand and replacement-supply analysis before making a market-gap claim."
        return "tier1_verified", f"Tier-1 · {host}", reason, next_check

    if official_lead and official_lead.candidate_urls:
        host = _host(official_lead.candidate_urls[0]) or "official candidate"
        reason = (
            f"An official-source candidate was found on {host}, but the exact claim is not confirmed yet. "
            f"This lead is prioritized because it contains a concrete {label} signal — “{signal[:90]}” — with potential for {impact}."
        )
        next_check = "Confirm the exact claim on the first-party page; do not treat it as a verified event until then."
        return "official_candidate", f"Official lead · {host}", reason, next_check

    reason = (
        f"The report contains a concrete {label} signal — “{signal[:90]}” — and points to potential {impact}. "
        "No acceptable first-party source has been located yet."
    )
    next_check = "Locate the responsible company, regulator or filing and verify the underlying change before deeper market analysis."
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
        elif score >= 5:
            # INVESTIGATE is a recommendation to spend research attention now.
            # It is deliberately not a claim that a market gap is verified.
            status = "INVESTIGATE"
        else:
            status = "WATCH"
        rows.append(PriorityLead(candidate.id, status, score, evidence_state, evidence_label, reason, next_check))

    rank = {"REVIEW": 0, "INVESTIGATE": 1, "WATCH": 2, "DISMISS": 3}
    rows.sort(key=lambda row: (rank[row.status], -row.priority_score, row.candidate_id))
    return rows


def save_priority_leads(path: Path, rows: list[PriorityLead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_priority_leads(path: Path) -> list[PriorityLead]:
    if not path.exists():
        return []
    return [PriorityLead(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
