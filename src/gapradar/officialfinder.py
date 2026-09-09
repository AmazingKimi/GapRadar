from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .worldscan import GapCandidate

NEWS_HOSTS = {
    "news.google.com", "techcrunch.com", "www.techcrunch.com", "arstechnica.com",
    "www.arstechnica.com", "reuters.com", "www.reuters.com", "bloomberg.com",
    "www.bloomberg.com", "forbes.com", "www.forbes.com", "businessinsider.com",
    "www.businessinsider.com", "youtube.com", "www.youtube.com", "reddit.com",
    "www.reddit.com", "x.com", "twitter.com", "linkedin.com", "www.linkedin.com",
}
GOVERNMENT_SUFFIXES = (
    ".gov", ".gov.uk", ".gov.au", ".gov.ca", ".gc.ca", ".gov.in", ".gov.sg",
    ".europa.eu", ".eu", ".int",
)
STOP = {
    "the", "a", "an", "new", "latest", "daily", "news", "wrap", "update", "updates",
    "will", "may", "must", "require", "requires", "required", "rules", "rule", "price",
    "hike", "increase", "shutdown", "service", "platform", "data", "market", "official",
    "announcement", "government", "today", "more", "from", "with", "into", "about",
}
CHANGE_TERMS = {
    "shutdown_eol": "shutdown sunset discontinued end support official",
    "price_shock": "pricing price fee subscription official",
    "api_terms_change": "API terms licensing developer official",
    "regulatory_shift": "rule regulation requirement mandate official",
}


@dataclass(frozen=True)
class OfficialSourceLead:
    candidate_id: str
    status: str
    query: str
    candidate_urls: list[str]
    candidate_hosts: list[str]
    search_coverage: str
    errors: list[str]
    queries: list[str] | None = None


def _clean_html(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", unescape(value or "")).split())


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


def _ddg(query: str, timeout: float) -> list[dict[str, str]]:
    response = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 GapRadar/0.8"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    rows: list[dict[str, str]] = []
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', response.text, flags=re.I | re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', response.text, flags=re.I | re.S)
    for index, (href, title) in enumerate(links[:20]):
        url = _decode_ddg_url(href)
        if url.startswith("http"):
            rows.append({
                "url": url,
                "title": _clean_html(title),
                "snippet": _clean_html(snippets[index] if index < len(snippets) else ""),
            })
    return rows


def _bing(query: str, timeout: float) -> list[dict[str, str]]:
    response = httpx.get(
        "https://www.bing.com/search",
        params={"q": query, "count": 20},
        headers={"User-Agent": "Mozilla/5.0 GapRadar/0.8"},
        timeout=timeout,
        follow_redirects=True,
    )
    response.raise_for_status()
    rows: list[dict[str, str]] = []
    for block in re.findall(r'<li class="b_algo".*?</li>', response.text, flags=re.I | re.S)[:20]:
        match = re.search(r'<h2>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if match:
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, flags=re.I | re.S)
            rows.append({
                "url": match.group(1),
                "title": _clean_html(match.group(2)),
                "snippet": _clean_html(snippet_match.group(1) if snippet_match else ""),
            })
    return rows


def _subject_tokens(candidate: GapCandidate) -> list[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9.-]{2,}", f"{candidate.headline} {candidate.summary}")
    values: list[str] = []
    for token in raw:
        lowered = token.lower().strip(".-")
        if lowered in STOP or len(lowered) < 3 or lowered in values:
            continue
        values.append(lowered)
    return values[:14]


def _registrable_hint(host: str) -> str:
    parts = [part for part in host.lower().split(".") if part and part != "www"]
    if len(parts) < 2:
        return parts[0] if parts else host.lower()
    common_second_level = {"co", "com", "org", "gov", "ac"}
    if len(parts) >= 3 and parts[-2] in common_second_level:
        return parts[-3]
    return parts[-2]


def _looks_first_party(url: str, candidate: GapCandidate) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    if not host or host in NEWS_HOSTS or any(host.endswith("." + noise) for noise in NEWS_HOSTS):
        return False
    if any(host.endswith(suffix) for suffix in GOVERNMENT_SUFFIXES):
        return True
    domain_hint = _registrable_hint(host)
    tokens = _subject_tokens(candidate)
    # Company/product-owned domains are SOURCE CANDIDATES only. Tier-1 verification
    # still requires fetching the page and confirming the hard change statement.
    return len(domain_hint) >= 4 and any(
        domain_hint == token or domain_hint in token or token in domain_hint
        for token in tokens[:8]
        if len(token) >= 4
    )


def _query_variants(candidate: GapCandidate) -> list[str]:
    headline = re.sub(r"\s+-\s+[^-]{2,80}$", "", candidate.headline).strip()
    tokens = _subject_tokens(candidate)
    subject = " ".join(tokens[:6])
    core = " ".join(tokens[:4])
    change = CHANGE_TERMS.get(candidate.change_type, "official announcement")
    variants = [
        f'"{headline}" official',
        f"{subject} {change}",
        f"{core} {change}",
    ]
    if candidate.change_type == "regulatory_shift":
        variants.append(f"{subject} government regulator requirement")
    unique: list[str] = []
    for query in variants:
        query = " ".join(query.split())
        if query and query not in unique:
            unique.append(query)
    return unique[:4]


def _result_relevance(row: dict[str, str], candidate: GapCandidate) -> int:
    text = f"{row.get('title', '')} {row.get('snippet', '')}".lower()
    tokens = _subject_tokens(candidate)
    hits = sum(token in text for token in tokens[:8])
    score = min(hits, 5)
    if re.search(r"\b(deprecat|sunset|discontinu|shutdown|pricing|price|fee|license|licensing|terms|mandate|required|regulation|rule)\b", text):
        score += 1
    return score


def find_official_sources(candidate: GapCandidate, *, timeout: float = 10.0) -> OfficialSourceLead:
    queries = _query_variants(candidate)
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    successful_searches = 0
    attempted_searches = 0

    for query in queries:
        for name, searcher in (("duckduckgo", _ddg), ("bing", _bing)):
            attempted_searches += 1
            try:
                found = searcher(query, timeout)
                successful_searches += 1
                for row in found:
                    rows.append(dict(row, query=query, engine=name))
            except Exception as exc:
                errors.append(f"{name} [{query[:80]}]: {type(exc).__name__}: {exc}")

    ranked: list[tuple[int, dict[str, str]]] = []
    seen: set[str] = set()
    for row in rows:
        url = row["url"].rstrip("/")
        if url in seen or not _looks_first_party(url, candidate):
            continue
        seen.add(url)
        ranked.append((_result_relevance(row, candidate), dict(row, url=url)))
    ranked.sort(key=lambda item: item[0], reverse=True)

    urls: list[str] = []
    hosts: list[str] = []
    for score, row in ranked:
        # A government/regulator host can survive with weaker title overlap. Company
        # domains need at least one additional subject/change signal in the result text.
        host = urlparse(row["url"]).netloc.lower()
        government = any(host.endswith(suffix) for suffix in GOVERNMENT_SUFFIXES)
        if score < (1 if government else 2):
            continue
        urls.append(row["url"])
        hosts.append(host)
        if len(urls) >= 5:
            break

    if successful_searches == 0:
        coverage = "failed"
    elif successful_searches < attempted_searches:
        coverage = "partial"
    else:
        coverage = "adequate"
    status = "first_party_candidates" if urls else ("search_failed" if coverage == "failed" else "not_found")
    return OfficialSourceLead(
        candidate_id=candidate.id,
        status=status,
        query=queries[0] if queries else "",
        candidate_urls=urls,
        candidate_hosts=hosts,
        search_coverage=coverage,
        errors=errors,
        queries=queries,
    )


def find_for_candidates(candidates: list[GapCandidate]) -> list[OfficialSourceLead]:
    return [find_official_sources(candidate) for candidate in candidates]


def save_leads(path: Path, rows: list[OfficialSourceLead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
