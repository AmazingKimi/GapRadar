from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import quote_plus

import feedparser
import httpx

from .worlddeep import WorldLeadAssessment, _relevance, _route, _subject
from .worldscan import GapCandidate

PRODUCT_SIGNAL = re.compile(
    r"\b(software|tool|platform|solution|suite|service|provider|vendor|startup|product|automation|alternative|replacement|competitor|migration tool|grc)\b",
    re.I,
)
POLICY_ONLY = re.compile(
    r"\b(guidance|law|act|regulation|rule|rules|requirement|requirements|proposal|proposed|agenda|policy|obligation|obligations|deadline)\b",
    re.I,
)


def _google_news_supply(candidate: GapCandidate, *, timeout: float = 12.0) -> tuple[list[dict[str, str]], str | None]:
    _, _, intent = _route(candidate)
    query = f"{_subject(candidate)} {intent}"
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        response = httpx.get(url, timeout=timeout, headers={"User-Agent": "GapRadar/0.9 news-supply"}, follow_redirects=True)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        rows: list[dict[str, str]] = []
        for entry in list(parsed.entries)[:30]:
            title = str(getattr(entry, "title", "") or "").strip()
            link = str(getattr(entry, "link", "") or "").strip()
            if not title or not link:
                continue
            source_obj = getattr(entry, "source", None)
            publisher = str(getattr(source_obj, "title", "") or "Google News") if source_obj else "Google News"
            summary = str(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
            rows.append({"title": title[:240], "url": link, "snippet": summary[:500], "source": publisher[:120]})
        return rows, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _looks_like_supply(row: dict[str, str], candidate: GapCandidate) -> bool:
    title = str(row.get("title") or "")
    text = f"{title} {row.get('snippet','')}"
    subject = _subject(candidate).lower()
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    normalized_subject = re.sub(r"[^a-z0-9]+", " ", subject).strip()
    if normalized_subject and (normalized_subject in normalized_title or normalized_title in normalized_subject):
        return False
    if not PRODUCT_SIGNAL.search(text):
        return False
    if candidate.change_type == "regulatory_shift":
        if not PRODUCT_SIGNAL.search(title):
            return False
        if POLICY_ONLY.search(title) and not re.search(r"\b(tool|software|platform|solution|suite|service|provider|vendor|startup|product|automation|grc)\b", title, re.I):
            return False
    return True


def enrich_failed_assessment(candidate: GapCandidate, assessment: WorldLeadAssessment) -> WorldLeadAssessment:
    if assessment.supply_coverage != "failed":
        return assessment
    rows, error = _google_news_supply(candidate)
    if error or not rows:
        errors = list(assessment.errors)
        errors.append(f"google_news_supply: {error or 'no results'}")
        return replace(assessment, errors=errors)

    supply_like = [row for row in rows if _looks_like_supply(row, candidate)]
    scored = [(row, _relevance(row, candidate)) for row in supply_like]
    # News-index results are noisy. Only high-relevance rows can count as supply
    # evidence; generic policy/editorial items must never dismiss a gap.
    evidence = [dict(row, relevance=score) for row, score in sorted(scored, key=lambda pair: pair[1], reverse=True) if score >= 5][:8]
    publishers = {str(row.get("source") or "") for row in evidence}

    if len(evidence) >= 3 and len(publishers) >= 3:
        supply_status = "served_signal"
        gap_assessment = "LIKELY SERVED"
        recommendation = "DISMISS"
        summary = "Fallback market search found at least three strongly relevant product-like supply signals across independent publishers. Broad supply appears present, but the primary web-search lane is still missing."
    elif evidence:
        supply_status = "thin_supply_signal"
        gap_assessment = "INSUFFICIENT COVERAGE"
        recommendation = "WATCH"
        summary = "Fallback market search found strong product-like supply signals, but news-index coverage alone is not sufficient to conclude that the market is served or underserved."
    else:
        supply_status = "no_supply_detected"
        gap_assessment = "INSUFFICIENT COVERAGE"
        recommendation = "WATCH"
        summary = "Fallback news-index search returned results but no strongly relevant product-like supply evidence. News coverage alone is insufficient to promote this to a market gap."

    return replace(
        assessment,
        supply_status=supply_status,
        supply_sources_checked=["google_news_supply"],
        supply_sources_missing=["web_search"],
        supply_candidate_count=len(rows),
        supply_evidence=evidence,
        supply_coverage="partial",
        gap_assessment=gap_assessment,
        final_recommendation=recommendation,
        summary=summary,
        errors=list(assessment.errors),
    )


def enrich_failed_assessments(candidates: list[GapCandidate], assessments: list[WorldLeadAssessment]) -> list[WorldLeadAssessment]:
    by_candidate = {candidate.id: candidate for candidate in candidates}
    return [enrich_failed_assessment(by_candidate[item.candidate_id], item) if item.candidate_id in by_candidate else item for item in assessments]
