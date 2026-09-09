from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .officialfinder import GOVERNMENT_SUFFIXES, OfficialSourceLead, _looks_first_party, _subject_tokens
from .worldscan import GapCandidate, _forced_gate


@dataclass(frozen=True)
class WorldOfficialFact:
    candidate_id: str
    status: str
    official_url: str | None
    official_host: str | None
    official_title: str | None
    excerpt: str | None
    subject_overlap: int
    errors: list[str]


def _clean_page(html_text: str) -> tuple[str, str]:
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    h1_match = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html_text)
    heading = h1_match or title_match
    title = " ".join(re.sub(r"<[^>]+>", " ", unescape(heading.group(1) if heading else "")).split())
    body = re.sub(r"(?is)<script\b.*?</script>", " ", html_text)
    body = re.sub(r"(?is)<style\b.*?</style>", " ", body)
    body = " ".join(re.sub(r"<[^>]+>", " ", unescape(body)).split())
    return title[:500], body[:24000]


def _host_is_government(host: str) -> bool:
    return any(host.endswith(suffix) for suffix in GOVERNMENT_SUFFIXES)


def _overlap(candidate: GapCandidate, text: str) -> int:
    lowered = text.lower()
    return sum(1 for token in _subject_tokens(candidate)[:10] if len(token) >= 4 and token in lowered)


def _meaningful_tokens(value: str) -> set[str]:
    stop = {
        "will", "new", "the", "and", "for", "with", "from", "into", "that", "this", "use", "using",
        "require", "requires", "required", "must", "mandatory", "mandate", "rule", "rules", "regulation",
        "massachusetts", "india", "united", "kingdom", "britain", "british", "european", "union", "australia",
        "canada", "singapore", "clean", "energy",
    }
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9+-]{2,}", value.lower())
        if token not in stop and len(token) >= 4
    }


def _claim_target_alignment(candidate: GapCandidate, text: str) -> bool:
    """Require the official page to discuss the actual object of the claimed change.

    Generic regulator pages can contain words like `require`, `clean`, and `energy` and
    otherwise look relevant. For a headline of the form `will require X to Y`, both the
    regulated target (X) and the required outcome (Y) must be represented on the page.
    """
    if candidate.change_type != "regulatory_shift":
        return True
    lowered = text.lower()
    match = re.search(r"\bwill\s+require\s+(.{3,90}?)\s+to\s+(.{3,110})$", candidate.headline, re.I)
    if match:
        target = _meaningful_tokens(match.group(1))
        outcome = _meaningful_tokens(match.group(2))
        target_hit = not target or any(token in lowered for token in target)
        outcome_hit = not outcome or any(token in lowered for token in outcome)
        return target_hit and outcome_hit

    # For other regulatory headlines, at least one distinctive non-generic headline
    # token must occur on the page in addition to the broad overlap check.
    distinctive = _meaningful_tokens(candidate.headline)
    return not distinctive or any(token in lowered for token in distinctive)


def _explicit_change_confirmation(candidate: GapCandidate, text: str) -> bool:
    """Tier-1 verification is intentionally stricter than discovery classification."""
    t = " ".join(text.lower().split())
    if candidate.change_type == "price_shock":
        delta = re.search(
            r"\b(price|pricing|fee|subscription|plan)\b.{0,140}\b(increase|increased|hike|raised|rises?|higher|changing|changes?|new price|from\s+[$€£]?\d)\b"
            r"|\b(increase|increased|hike|raised|rises?|higher|changing|changes?)\b.{0,140}\b(price|pricing|fee|subscription|plan)\b",
            t,
        )
        return bool(delta)
    if candidate.change_type == "regulatory_shift":
        hard = re.search(
            r"\b(will require|requires?|required|must\b|mandatory|mandate|shall\b|takes? effect|effective from|compliance deadline|new rule|new rules|regulation)\b",
            t,
        )
        return bool(hard)
    return _forced_gate(candidate.change_type, t)


def verify_official_lead(candidate: GapCandidate, lead: OfficialSourceLead, *, timeout: float = 12.0) -> WorldOfficialFact:
    if not lead.candidate_urls:
        return WorldOfficialFact(candidate.id, "unverified", None, None, None, None, 0, list(lead.errors))

    errors = list(lead.errors)
    for url in lead.candidate_urls[:5]:
        if not _looks_first_party(url, candidate):
            continue
        try:
            response = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 GapRadar/0.8 first-party-verifier"}, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            final_url = str(response.url)
            if not _looks_first_party(final_url, candidate):
                errors.append(f"redirected away from accepted first-party host: {final_url}")
                continue
            title, body = _clean_page(response.text)
            text = f"{title} {body}"
            overlap = _overlap(candidate, text)
            host = (urlparse(final_url).hostname or "").lower()
            min_overlap = 2
            if overlap < min_overlap:
                errors.append(f"subject overlap too weak for {host}: {overlap} < {min_overlap}")
                continue
            if not _claim_target_alignment(candidate, text):
                errors.append(f"first-party page did not align with the claimed target/outcome: {host}")
                continue
            if not _explicit_change_confirmation(candidate, text):
                errors.append(f"first-party page did not explicitly confirm {candidate.change_type}: {host}")
                continue
            return WorldOfficialFact(
                candidate_id=candidate.id,
                status="tier1_verified",
                official_url=final_url,
                official_host=host,
                official_title=title or candidate.headline,
                excerpt=body[:1200],
                subject_overlap=overlap,
                errors=errors,
            )
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    return WorldOfficialFact(candidate.id, "unverified", None, None, None, None, 0, errors)


def verify_official_leads(candidates: list[GapCandidate], leads: list[OfficialSourceLead]) -> list[WorldOfficialFact]:
    by_candidate = {row.candidate_id: row for row in leads}
    return [
        verify_official_lead(candidate, by_candidate.get(candidate.id, OfficialSourceLead(candidate.id, "not_found", "", [], [], "failed", [], [])))
        for candidate in candidates
    ]


def save_facts(path: Path, rows: list[WorldOfficialFact]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_facts(path: Path) -> dict[str, WorldOfficialFact]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["candidate_id"]: WorldOfficialFact(**row) for row in payload}
