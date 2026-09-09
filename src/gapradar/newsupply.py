from __future__ import annotations

from dataclasses import replace
from urllib.parse import quote_plus

import feedparser
import httpx

from .worlddeep import WorldLeadAssessment, _relevance, _route, _subject
from .worldscan import GapCandidate


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


def enrich_failed_assessment(candidate: GapCandidate, assessment: WorldLeadAssessment) -> WorldLeadAssessment:
    if assessment.supply_coverage != "failed":
        return assessment
    rows, error = _google_news_supply(candidate)
    if error or not rows:
        errors = list(assessment.errors)
        errors.append(f"google_news_supply: {error or 'no results'}")
        return replace(assessment, errors=errors)

    scored = [(row, _relevance(row, candidate)) for row in rows]
    evidence = [dict(row, relevance=score) for row, score in sorted(scored, key=lambda pair: pair[1], reverse=True) if score >= 3][:8]
    publishers = {str(row.get("source") or "") for row in evidence}

    if len(evidence) >= 3 and len(publishers) >= 2:
        supply_status = "served_signal"
        gap_assessment = "LIKELY SERVED"
        recommendation = "DISMISS"
        summary = "Fallback market search found several relevant substitute/compliance-solution signals across multiple publishers. Broad supply appears present; a narrower unmet job would be required before treating this as a gap."
    elif evidence:
        supply_status = "thin_supply_signal"
        gap_assessment = "INSUFFICIENT COVERAGE"
        recommendation = "WATCH"
        summary = "Fallback market search found some relevant supply signals, but news-index coverage is not sufficient to conclude that the market is served or underserved."
    else:
        supply_status = "no_supply_detected"
        gap_assessment = "INSUFFICIENT COVERAGE"
        recommendation = "WATCH"
        summary = "Fallback news-index search returned a usable result set but no qualifying supply evidence. News coverage alone is insufficient to promote this to a market gap."

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
