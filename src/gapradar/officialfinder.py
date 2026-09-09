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
    "www.reddit.com", "x.com", "twitter.com",
}
GOVERNMENT_SUFFIXES = (
    ".gov", ".gov.uk", ".gov.au", ".gov.ca", ".gc.ca", ".gov.in", ".gov.sg",
    ".europa.eu", ".eu", ".int",
)
STOP = {
    "the", "a", "an", "new", "latest", "daily", "news", "wrap", "update", "updates",
    "will", "may", "must", "require", "requires", "required", "rules", "rule", "price",
    "hike", "increase", "shutdown", "service", "platform", "data", "market",
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
    for href, title in re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', response.text, flags=re.I | re.S)[:20]:
        url = _decode_ddg_url(href)
        if url.startswith("http"):
            rows.append({"url": url, "title": _clean_html(title)})
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
            rows.append({"url": match.group(1), "title": _clean_html(match.group(2))})
    return rows


def _subject_tokens(candidate: GapCandidate) -> list[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9.-]{2,}", candidate.headline)
    return [token.lower() for token in raw if token.lower() not in STOP][:8]


def _registrable_hint(host: str) -> str:
    parts = host.lower().split(".")
    if len(parts) < 2:
        return host.lower()
    return parts[-2]


def _looks_first_party(url: str, candidate: GapCandidate) -> bool:
    host = urlparse(url).netloc.lower().split(":")[0]
    if not host or host in NEWS_HOSTS or any(host.endswith("." + noise) for noise in NEWS_HOSTS):
        return False
    if any(host.endswith(suffix) for suffix in GOVERNMENT_SUFFIXES):
        return True
    domain_hint = _registrable_hint(host)
    tokens = _subject_tokens(candidate)
    # Company/product-owned domains are accepted only as source candidates, never as verified facts.
    return len(domain_hint) >= 4 and any(domain_hint == token or domain_hint in token or token in domain_hint for token in tokens[:5])


def find_official_sources(candidate: GapCandidate, *, timeout: float = 10.0) -> OfficialSourceLead:
    query = f'"{candidate.headline}" official announcement'
    rows: list[dict[str, str]] = []
    errors: list[str] = []
    successful = 0
    for name, searcher in (("duckduckgo", _ddg), ("bing", _bing)):
        try:
            found = searcher(query, timeout)
            rows.extend(found)
            successful += 1
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    seen: set[str] = set()
    urls: list[str] = []
    hosts: list[str] = []
    for row in rows:
        url = row["url"].rstrip("/")
        if url in seen or not _looks_first_party(url, candidate):
            continue
        seen.add(url)
        urls.append(url)
        hosts.append(urlparse(url).netloc.lower())
        if len(urls) >= 5:
            break

    coverage = "failed" if successful == 0 else ("partial" if successful == 1 else "adequate")
    status = "first_party_candidates" if urls else ("search_failed" if coverage == "failed" else "not_found")
    return OfficialSourceLead(candidate.id, status, query, urls, hosts, coverage, errors)


def find_for_candidates(candidates: list[GapCandidate]) -> list[OfficialSourceLead]:
    return [find_official_sources(candidate) for candidate in candidates]


def save_leads(path: Path, rows: list[OfficialSourceLead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
