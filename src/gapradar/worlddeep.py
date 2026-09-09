from __future__ import annotations

import os
import re
from dataclasses import replace
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .worldscan import GapCandidate

SOLUTION_WORDS = re.compile(r"\b(alternative|replacement|competitor|migration|migrate|compliance|platform|software|tool|service|solution)\b", re.I)
NOISE_HOSTS = {"news.google.com", "youtube.com", "www.youtube.com", "facebook.com", "www.facebook.com", "x.com", "twitter.com"}


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


def _route(candidate: GapCandidate) -> tuple[str, tuple[str, ...], str]:
    text = f"{candidate.headline} {candidate.summary}".lower()
    if candidate.change_type == "api_terms_change" or re.search(r"\b(api|sdk|developer|cli|github|npm)\b", text):
        return "developer", ("github_repositories", "npm"), "developer alternatives and migration tooling"
    if candidate.change_type == "regulatory_shift":
        return "regulatory", ("web_search",), "compliance software, reporting, evidence and workflow tools"
    if candidate.change_type == "shutdown_eol":
        return "replacement", ("web_search",), "replacement products and migration services"
    return "commercial", ("web_search",), "lower-cost substitutes and competing products"


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


def _web_search(query: str, *, timeout: float = 12.0) -> tuple[list[dict[str, str]], bool, str | None]:
    try:
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 GapRadar/0.9"},
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
        html = response.text
        links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', html, flags=re.I | re.S)
        rows: list[dict[str, str]] = []
        for i, (href, title_html) in enumerate(links[:20]):
            url = _decode_ddg_url(href)
            host = urlparse(url).netloc.lower()
            if not url.startswith("http") or host in NOISE_HOSTS:
                continue
            title = re.sub(r"<[^>]+>", " ", unescape(title_html))
            snippet_html = snippets[i] if i < len(snippets) else ""
            snippet = re.sub(r"<[^>]+>", " ", unescape(snippet_html))
            rows.append({"title": " ".join(title.split())[:240], "url": url, "snippet": " ".join(snippet.split())[:500], "source": host or "web"})
        return rows, True, None
    except Exception as exc:
        return [], False, f"{type(exc).__name__}: {exc}"


def _github_search(query: str, *, timeout: float = 12.0) -> tuple[list[dict[str, str]], bool, str | None]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.9"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = httpx.get("https://api.github.com/search/repositories", params={"q": query + " in:name,description,topics archived:false", "sort": "stars", "per_page": 20}, headers=headers, timeout=timeout)
        response.raise_for_status()
        rows = []
        for item in response.json().get("items", []):
            rows.append({"title": str(item.get("full_name") or item.get("name") or "")[:240], "url": str(item.get("html_url") or ""), "snippet": str(item.get("description") or "")[:500], "source": "github.com"})
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
            if not name:
                continue
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


def analyze_candidate(candidate: GapCandidate) -> GapCandidate:
    ecosystem, planned_sources, intent = _route(candidate)
    subject = _subject(candidate)
    query = f'"{subject}" {intent}'
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
        supply_status = "unassessed"
        assessment = "INSUFFICIENT COVERAGE"
        recommendation = "WATCH"
        summary = "Supply investigation failed across the planned sources; no market-gap conclusion is allowed."
    elif len(evidence) >= 3:
        supply_status = "served"
        assessment = "LIKELY SERVED"
        recommendation = "DISMISS"
        summary = "Several relevant substitutes or solution providers were found in the checked supply sources. A broad gap is not established; only narrower unmet jobs remain worth investigating."
    elif len(evidence) >= 1:
        supply_status = "thin_supply"
        assessment = "POTENTIAL GAP"
        recommendation = "REVIEW"
        summary = "Some relevant supply exists, but the checked market appears thin enough to justify human review of the exact unmet job."
    else:
        supply_status = "no_supply_detected"
        assessment = "POTENTIAL GAP" if coverage == "adequate" else "INSUFFICIENT COVERAGE"
        recommendation = "REVIEW" if coverage == "adequate" else "WATCH"
        summary = "No qualifying replacement supply was detected in the checked sources. This is coverage-bounded and is not proof that no alternatives exist."

    return replace(
        candidate,
        supply_status=supply_status,
        supply_sources_checked=checked,
        supply_sources_missing=missing,
        supply_candidate_count=len(unique),
        supply_evidence=evidence,
        supply_coverage=coverage,
        gap_assessment=assessment,
        final_recommendation=recommendation,
        deep_dive_summary=summary,
        deep_dive_errors=errors,
        ecosystem=ecosystem,
    )


def analyze_candidates(candidates: list[GapCandidate]) -> list[GapCandidate]:
    return [analyze_candidate(candidate) for candidate in candidates]
