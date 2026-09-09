from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .worldscan import GapCandidate
from .worldverify import WorldVerification

SOLUTION_WORDS = re.compile(r"\b(alternative|replacement|competitor|migration|migrate|compliance|platform|software|tool|service|solution)\b", re.I)
NOISE_HOSTS = {"news.google.com", "youtube.com", "www.youtube.com", "facebook.com", "www.facebook.com", "x.com", "twitter.com"}


@dataclass(frozen=True)
class WorldLeadAssessment:
    candidate_id: str
    ecosystem: str
    supply_status: str
    supply_sources_checked: list[str]
    supply_sources_missing: list[str]
    supply_candidate_count: int
    supply_evidence: list[dict[str, object]]
    supply_coverage: str
    gap_assessment: str
    final_recommendation: str
    summary: str
    errors: list[str]
    tier1_status: str = "unverified"
    official_url: str | None = None
    demand_hypothesis: dict[str, object] | None = None


def _tokens(text: str) -> list[str]:
    stop = {"the","and","for","with","from","into","will","new","after","before","more","late","latest","watch","price","hike","shutdown","shutting","down","require","requires","required","rules","regulation","policy","service"}
    values = [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9+.-]{2,}", text)]
    return [t for t in values if t not in stop][:10]


def _subject(candidate: GapCandidate) -> str:
    headline = re.sub(r"^(WATCH|REVIEW):\s*", "", candidate.headline, flags=re.I)
    headline = re.sub(r"\s+-\s+[^-]{2,80}$", "", headline)
    if candidate.change_type == "price_shock":
        headline = re.sub(r"\b(the latest )?price (hike|increase|change)s?\b[: ]*", "", headline, flags=re.I)
    return headline.strip()[:180]


def _demand_hypothesis(candidate: GapCandidate, verification: WorldVerification) -> dict[str, object]:
    subject = _subject(candidate)
    if candidate.change_type == "shutdown_eol":
        affected = f"Users and organizations still dependent on the product or workflow described by: {subject}."
        job = "Preserve the abandoned job with acceptable migration cost, compatibility and continuity."
        disruption = "A product, service or supported capability is being removed or ended."
        unknowns = ["Active affected-user count", "Migration urgency by segment", "Quality of official migration path"]
    elif candidate.change_type == "price_shock":
        affected = f"Price-sensitive customers affected by the pricing change described by: {subject}."
        job = "Keep the core outcome while reducing the new cost burden or changing the pricing model."
        disruption = "A material price, fee or free-tier change may release previously locked-in demand."
        unknowns = ["Share of customers materially affected", "Switching costs", "Whether lower-cost substitutes already serve the core job"]
    elif candidate.change_type == "api_terms_change":
        affected = f"Developers and businesses dependent on the API, platform, license or terms described by: {subject}."
        job = "Keep integrations and dependent workflows functioning under the changed platform constraints."
        disruption = "An API, licensing, access or terms change may force migration, rewrites or dependency replacement."
        unknowns = ["Number of affected integrations", "Migration complexity", "Availability of compatible alternatives"]
    else:
        affected = f"Organizations obligated by the new requirement described by: {subject}."
        job = "Comply with the new requirement with the least operational burden, evidence-collection cost and implementation risk."
        disruption = "A regulatory or policy shift creates mandatory work, controls, reporting or migration."
        unknowns = ["Exact obligated segments", "Effective date and enforcement intensity", "Existing compliance-tool coverage"]

    return {
        "affected_users": affected,
        "job_to_be_done": job,
        "disruption": disruption,
        "official_successor": "unknown",
        "basis": [verification.official_url] if verification.official_url else [],
        "confidence": "low",
        "unknowns": unknowns,
    }


def _route(candidate: GapCandidate) -> tuple[str, tuple[str, ...], str]:
    text = f"{candidate.headline} {candidate.summary}".lower()
    if candidate.change_type == "api_terms_change" or re.search(r"\b(api|sdk|developer|cli|github|npm)\b", text):
        return "developer", ("github_repositories", "npm"), "developer alternatives migration tooling"
    if candidate.change_type == "regulatory_shift":
        return "regulatory", ("web_search",), "compliance software reporting governance tools"
    if candidate.change_type == "shutdown_eol":
        return "replacement", ("web_search",), "replacement products migration alternatives"
    return "commercial", ("web_search",), "lower cost substitutes competitors alternatives"


def _decode_ddg_url(value: str) -> str:
    value = unescape(value)
    if value.startswith("//"):
        value = "https:" + value
    try:
        parsed = urlparse(value)
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        if target:
            return unquote(target)
    except Exception:
        pass
    return value


def _clean_html(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", unescape(value or "")).split())


def _ddg_search(query: str, *, timeout: float) -> list[dict[str, str]]:
    response = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 GapRadar/0.9"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', response.text, flags=re.I | re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', response.text, flags=re.I | re.S)
    rows: list[dict[str, str]] = []
    for i, (href, title_html) in enumerate(links[:20]):
        url = _decode_ddg_url(href)
        host = urlparse(url).netloc.lower()
        if not url.startswith("http") or host in NOISE_HOSTS:
            continue
        rows.append({"title": _clean_html(title_html)[:240], "url": url, "snippet": _clean_html(snippets[i] if i < len(snippets) else "")[:500], "source": host or "web"})
    return rows


def _bing_search(query: str, *, timeout: float) -> list[dict[str, str]]:
    response = httpx.get("https://www.bing.com/search", params={"q": query, "count": 20}, headers={"User-Agent": "Mozilla/5.0 GapRadar/0.9"}, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    blocks = re.findall(r'<li class="b_algo".*?</li>', response.text, flags=re.I | re.S)
    rows: list[dict[str, str]] = []
    for block in blocks[:20]:
        match = re.search(r'<h2>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if not match:
            continue
        url, title_html = match.groups()
        host = urlparse(url).netloc.lower()
        if not url.startswith("http") or host in NOISE_HOSTS:
            continue
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
        rows.append({"title": _clean_html(title_html)[:240], "url": url, "snippet": _clean_html(snippet_match.group(1) if snippet_match else "")[:500], "source": host or "web"})
    return rows


def _web_search(query: str, *, timeout: float = 12.0) -> tuple[list[dict[str, str]], bool, str | None]:
    errors: list[str] = []
    for name, searcher in (("duckduckgo", _ddg_search), ("bing", _bing_search)):
        try:
            rows = searcher(query, timeout=timeout)
            if rows:
                return rows, True, None
            errors.append(f"{name}: no parsable results")
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    return [], False, "; ".join(errors)


def _github_search(query: str, *, timeout: float = 12.0) -> tuple[list[dict[str, str]], bool, str | None]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.9"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = httpx.get("https://api.github.com/search/repositories", params={"q": query + " in:name,description,topics archived:false", "sort": "stars", "per_page": 20}, headers=headers, timeout=timeout)
        response.raise_for_status()
        rows = [{"title": str(item.get("full_name") or item.get("name") or "")[:240], "url": str(item.get("html_url") or ""), "snippet": str(item.get("description") or "")[:500], "source": "github.com"} for item in response.json().get("items", [])]
        return rows, True, None
    except Exception as exc:
        return [], False, f"{type(exc).__name__}: {exc}"


def _npm_search(query: str, *, timeout: float = 12.0) -> tuple[list[dict[str, str]], bool, str | None]:
    try:
        response = httpx.get("https://registry.npmjs.org/-/v1/search", params={"text": query, "size": 20}, headers={"User-Agent": "GapRadar/0.9"}, timeout=timeout)
        response.raise_for_status()
        rows = []
        for obj in response.json().get("objects", []):
            package = obj.get("package") or {}
            name = str(package.get("name") or "").strip()
            if name:
                rows.append({"title": name[:240], "url": str((package.get("links") or {}).get("npm") or f"https://www.npmjs.com/package/{name}"), "snippet": str(package.get("description") or "")[:500], "source": "npmjs.com"})
        return rows, True, None
    except Exception as exc:
        return [], False, f"{type(exc).__name__}: {exc}"


def _relevance(row: dict[str, str], candidate: GapCandidate) -> int:
    text = f"{row.get('title','')} {row.get('snippet','')}".lower()
    tokens = _tokens(_subject(candidate))
    hits = sum(1 for token in tokens if token in text)
    score = min(hits, 4)
    if SOLUTION_WORDS.search(text):
        score += 2
    if candidate.change_type == "regulatory_shift" and re.search(r"\b(compliance|regulatory|reporting|audit|governance)\b", text):
        score += 2
    return score


def _unverified_assessment(candidate: GapCandidate) -> WorldLeadAssessment:
    return WorldLeadAssessment(
        candidate_id=candidate.id,
        ecosystem=_route(candidate)[0],
        supply_status="unassessed",
        supply_sources_checked=[],
        supply_sources_missing=list(_route(candidate)[1]),
        supply_candidate_count=0,
        supply_evidence=[],
        supply_coverage="blocked_unverified",
        gap_assessment="UNVERIFIED",
        final_recommendation="WATCH",
        summary="This world-change lead has no Tier-1 verification. Supply/gap analysis is blocked so a news signal cannot become an opportunity claim.",
        errors=[],
    )


def analyze_candidate(candidate: GapCandidate, verification: WorldVerification | None = None) -> WorldLeadAssessment:
    if verification is None or verification.status != "tier1_verified" or not verification.official_url:
        return _unverified_assessment(candidate)

    hypothesis = _demand_hypothesis(candidate, verification)
    ecosystem, planned_sources, intent = _route(candidate)
    subject = _subject(candidate)
    query = f"{subject} {intent}"
    rows: list[dict[str, str]] = []
    checked: list[str] = []
    errors: list[str] = []

    for source in planned_sources:
        if source == "github_repositories":
            found, ok, error = _github_search(subject)
        elif source == "npm":
            found, ok, error = _npm_search(subject)
        else:
            found, ok, error = _web_search(query)
        if ok:
            checked.append(source)
            rows.extend(found)
        elif error:
            errors.append(f"{source}: {error}")

    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        url = row.get("url", "").rstrip("/").lower()
        if url:
            unique[url] = row
    scored = [(row, _relevance(row, candidate)) for row in unique.values()]
    evidence = [dict(row, relevance=score) for row, score in sorted(scored, key=lambda pair: pair[1], reverse=True) if score >= 3][:8]
    missing = [source for source in planned_sources if source not in checked]
    coverage = "failed" if not checked else ("partial" if missing else "adequate")

    if coverage == "failed":
        supply_status, assessment, recommendation = "unassessed", "INSUFFICIENT COVERAGE", "WATCH"
        summary = "Supply investigation did not return a usable result set from the planned sources; no market-gap conclusion is allowed."
    elif len(evidence) >= 3:
        supply_status, assessment, recommendation = "served", "LIKELY SERVED", "DISMISS"
        summary = "Several relevant substitutes or solution providers were found in the checked supply sources. A broad gap is not established; only narrower unmet jobs remain worth investigating."
    elif len(evidence) >= 1:
        supply_status, assessment, recommendation = "thin_supply", "POTENTIAL GAP", "REVIEW"
        summary = "Some relevant supply exists, but the checked market appears thin enough to justify human review of the explicit unmet job."
    else:
        supply_status = "no_supply_detected"
        assessment = "POTENTIAL GAP" if coverage == "adequate" and len(unique) >= 5 else "INSUFFICIENT COVERAGE"
        recommendation = "REVIEW" if assessment == "POTENTIAL GAP" else "WATCH"
        summary = "No qualifying replacement supply was detected among the returned candidates. This remains coverage-bounded and is not proof that no alternatives exist."

    return WorldLeadAssessment(
        candidate_id=candidate.id,
        ecosystem=ecosystem,
        supply_status=supply_status,
        supply_sources_checked=checked,
        supply_sources_missing=missing,
        supply_candidate_count=len(unique),
        supply_evidence=evidence,
        supply_coverage=coverage,
        gap_assessment=assessment,
        final_recommendation=recommendation,
        summary=summary,
        errors=errors,
        tier1_status="tier1_verified",
        official_url=verification.official_url,
        demand_hypothesis=hypothesis,
    )


def analyze_candidates(candidates: list[GapCandidate], verifications: dict[str, WorldVerification] | None = None) -> list[WorldLeadAssessment]:
    verification_map = verifications or {}
    return [analyze_candidate(candidate, verification_map.get(candidate.id)) for candidate in candidates]


def save_assessments(path: Path, assessments: list[WorldLeadAssessment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(item) for item in assessments], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_assessments(path: Path) -> list[WorldLeadAssessment]:
    if not path.exists():
        return []
    return [WorldLeadAssessment(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
