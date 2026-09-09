from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .detector import event_from_document
from .models import EvidenceTier, MarketEvent, SourceEvidence
from .reaction import ReactionCandidate, dedupe_candidates, hacker_news_queries, score_migration_pain
from .routing import reaction_source_plan
from .supply import SupplyCandidate, score_supply


@dataclass(frozen=True)
class DiscoveryAudit:
    source: str
    query: str
    ok: bool
    candidate_count: int
    error: str | None = None


def _as_dt(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)


def _as_start_dt(day: date) -> datetime:
    return datetime.combine(day, time(0, 0, 0), tzinfo=timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_day(event: MarketEvent) -> date | None:
    return event.event_date.date() if event.event_date else None


def _reaction_query_subset(event: MarketEvent) -> list[str]:
    queries = hacker_news_queries(event)
    vendor = event.vendor.lower()
    change_words = ("deprecated", "sunset", "migration", "alternative", "pricing", "price increase", "api change")
    ranked = sorted(
        enumerate(queries),
        key=lambda row: (
            -int(vendor in row[1].lower()),
            -int(any(word in row[1].lower() for word in change_words)),
            row[0],
        ),
    )
    return [query for _, query in ranked[:6]]


def _window_start(event: MarketEvent, as_of: date, days: int) -> date:
    start = as_of - timedelta(days=days)
    event_day = _event_day(event)
    if event_day and event_day > start:
        return event_day
    return start


def discover_hn(event: MarketEvent, *, as_of: date, days: int = 120, timeout: float = 12.0) -> tuple[list[ReactionCandidate], list[DiscoveryAudit]]:
    end = int(_as_dt(as_of).timestamp())
    start = int(_as_start_dt(_window_start(event, as_of, days)).timestamp())
    rows: list[ReactionCandidate] = []
    audits: list[DiscoveryAudit] = []
    for query in _reaction_query_subset(event):
        try:
            response = httpx.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={
                    "query": query,
                    "tags": "story,comment",
                    "numericFilters": f"created_at_i>={start},created_at_i<={end}",
                    "hitsPerPage": 40,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            found: list[ReactionCandidate] = []
            for hit in response.json().get("hits", []):
                object_id = str(hit.get("objectID") or "").strip()
                if not object_id:
                    continue
                found.append(
                    ReactionCandidate(
                        title=str(hit.get("title") or hit.get("story_title") or "Hacker News discussion"),
                        url=f"https://news.ycombinator.com/item?id={object_id}",
                        publisher="Hacker News",
                        source_kind="hacker_news",
                        published_at=_parse_iso(hit.get("created_at")),
                        excerpt=str(hit.get("comment_text") or hit.get("story_text") or ""),
                        engagement=int(hit.get("points") or 0) + int(hit.get("num_comments") or 0),
                    )
                )
            rows.extend(found)
            audits.append(DiscoveryAudit("hacker_news", query, True, len(found)))
        except Exception as exc:
            audits.append(DiscoveryAudit("hacker_news", query, False, 0, f"{type(exc).__name__}: {exc}"))
    return dedupe_candidates(rows), audits


def discover_github_issues(event: MarketEvent, *, as_of: date, days: int = 120, timeout: float = 12.0) -> tuple[list[ReactionCandidate], list[DiscoveryAudit]]:
    start = _window_start(event, as_of, days).isoformat()
    end = as_of.isoformat()
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    aliases = []
    for q in _reaction_query_subset(event):
        core = q.replace(event.vendor, "").strip()
        if core and core not in aliases:
            aliases.append(core)
    rows: list[ReactionCandidate] = []
    audits: list[DiscoveryAudit] = []
    for alias in aliases[:4]:
        query = f'"{alias}" {event.vendor} created:>={start} created:<={end} is:issue'
        try:
            response = httpx.get(
                "https://api.github.com/search/issues",
                params={"q": query, "sort": "comments", "order": "desc", "per_page": 40},
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            found: list[ReactionCandidate] = []
            for item in response.json().get("items", []):
                url = str(item.get("html_url") or "").strip()
                if not url:
                    continue
                found.append(
                    ReactionCandidate(
                        title=str(item.get("title") or "GitHub issue"),
                        url=url,
                        publisher="GitHub Issues",
                        source_kind="github_issue",
                        published_at=_parse_iso(item.get("created_at")),
                        excerpt=str(item.get("body") or ""),
                        engagement=int(item.get("comments") or 0),
                    )
                )
            rows.extend(found)
            audits.append(DiscoveryAudit("github_issues", query, True, len(found)))
        except Exception as exc:
            audits.append(DiscoveryAudit("github_issues", query, False, 0, f"{type(exc).__name__}: {exc}"))
    return dedupe_candidates(rows), audits


def _candidate_in_event_window(candidate: ReactionCandidate, event: MarketEvent, as_of: date) -> bool:
    if candidate.published_at is None:
        return True
    observed = candidate.published_at.date()
    event_day = _event_day(event)
    if event_day and observed < event_day:
        return False
    return observed <= as_of


def apply_discovered_reaction(event: MarketEvent, candidates: list[ReactionCandidate], audits: list[DiscoveryAudit], *, as_of: date) -> None:
    filtered = [candidate for candidate in dedupe_candidates(candidates) if _candidate_in_event_window(candidate, event, as_of)]
    accepted: list[SourceEvidence] = []
    for candidate in filtered:
        score = score_migration_pain(candidate, event)
        if score < 3:
            continue
        accepted.append(
            SourceEvidence(
                tier=EvidenceTier.TIER_2_REACTION,
                title=candidate.title[:240] or "Reaction",
                url=candidate.url,
                publisher=candidate.publisher,
                published_at=candidate.published_at,
                excerpt=candidate.excerpt[:800],
                is_official=False,
                source_kind=candidate.source_kind,
                signal="migration_pain",
                signal_score=score,
                engagement=candidate.engagement,
            )
        )
    accepted.sort(key=lambda item: (item.signal_score, item.engagement), reverse=True)
    event.reaction_evidence = accepted[:12]
    event.reaction_candidate_count = len(filtered)
    event.reaction_queries = [audit.__dict__ for audit in audits]
    event.reaction_sources_checked = sorted({audit.source for audit in audits if audit.ok})
    event.reaction_checked_at = _as_dt(as_of)
    successes = sum(1 for audit in audits if audit.ok)
    plan = reaction_source_plan(event)
    coverage_missing = [source for source in plan.preferred_sources if source not in event.reaction_sources_checked]
    if successes == 0:
        event.reaction_search_quality = "failed"
    elif successes < len(audits) or coverage_missing:
        event.reaction_search_quality = "degraded"
    else:
        event.reaction_search_quality = "adequate"
    event.notes = [note for note in event.notes if not note.startswith("Reaction coverage gap:")]
    if coverage_missing:
        event.notes.append("Reaction coverage gap: preferred ecosystem sources not checked: " + ", ".join(coverage_missing))
    event.verify()


def _supply_terms(event: MarketEvent) -> str:
    words = [word for word in event.product.replace("/", " ").split() if len(word) >= 3]
    return " ".join(words[:4]) or event.vendor


def discover_github_supply(event: MarketEvent, *, as_of: date, timeout: float = 12.0) -> tuple[list[SupplyCandidate], DiscoveryAudit]:
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GapRadar/0.8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    query = f'{_supply_terms(event)} {event.vendor} created:<={as_of.isoformat()} in:name,description,topics archived:false'
    try:
        response = httpx.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 40},
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        rows: list[SupplyCandidate] = []
        for item in response.json().get("items", []):
            created = _parse_iso(item.get("created_at"))
            if created and created.date() > as_of:
                continue
            rows.append(
                SupplyCandidate(
                    title=str(item.get("full_name") or item.get("name") or "GitHub repository"),
                    url=str(item.get("html_url") or ""),
                    publisher="GitHub Repositories",
                    source_kind="github_repository",
                    description=str(item.get("description") or ""),
                    updated_at=_parse_iso(item.get("pushed_at") or item.get("updated_at")),
                    popularity=0,
                    archived=bool(item.get("archived", False)),
                )
            )
        return rows, DiscoveryAudit("github_supply", query, True, len(rows))
    except Exception as exc:
        return [], DiscoveryAudit("github_supply", query, False, 0, f"{type(exc).__name__}: {exc}")


def apply_discovered_supply(event: MarketEvent, candidates: list[SupplyCandidate], audit: DiscoveryAudit, *, as_of: date) -> None:
    if event.demand_status not in {"early_signal", "repeated_signal"}:
        return
    accepted: list[SourceEvidence] = []
    for candidate in candidates:
        score = score_supply(candidate, event, now=_as_dt(as_of))
        if score < 4:
            continue
        accepted.append(
            SourceEvidence(
                tier=EvidenceTier.TIER_3_SUPPLY,
                title=candidate.title[:240],
                url=candidate.url,
                publisher=candidate.publisher,
                published_at=candidate.updated_at,
                excerpt=candidate.description[:800],
                is_official=False,
                source_kind=candidate.source_kind,
                signal="replacement_supply",
                signal_score=score,
                engagement=0,
            )
        )
    event.supply_evidence = accepted[:12]
    event.supply_candidate_count = len(candidates)
    event.supply_sources_checked = [audit.source] if audit.ok else []
    event.supply_checked_at = _as_dt(as_of) if audit.ok else None
    event.verify()


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    if not case.get("expected_detect", True):
        return {"id": case["id"], "cohort": case.get("cohort", "headline"), "status": "negative_control_skipped"}
    as_of = date.fromisoformat(str(case["replay_as_of"]))
    event = event_from_document(
        vendor=str(case["vendor"]),
        product=str(case["product"]),
        title=str(case.get("title_hint") or ""),
        summary=str(case.get("excerpt_hint") or ""),
        url=str(case["official_url"]),
        published_at=_as_dt(date.fromisoformat(str(case["event_date"]))),
        historical=True,
    )
    if event is None:
        return {"id": case["id"], "cohort": case.get("cohort", "headline"), "status": "event_not_detected"}

    hn, hn_audits = discover_hn(event, as_of=as_of)
    gh, gh_audits = discover_github_issues(event, as_of=as_of)
    audits = hn_audits + gh_audits
    apply_discovered_reaction(event, hn + gh, audits, as_of=as_of)

    supply_audit: DiscoveryAudit | None = None
    if event.demand_status in {"early_signal", "repeated_signal"}:
        supply, supply_audit = discover_github_supply(event, as_of=as_of)
        apply_discovered_supply(event, supply, supply_audit, as_of=as_of)

    plan = reaction_source_plan(event)
    return {
        "id": case["id"],
        "cohort": case.get("cohort", "headline"),
        "vendor": case["vendor"],
        "product": case["product"],
        "as_of": as_of.isoformat(),
        "ground_truth_demand": case.get("ground_truth_demand"),
        "ground_truth_supply": case.get("ground_truth_supply"),
        "reaction_candidate_count": event.reaction_candidate_count,
        "reaction_evidence_count": len(event.reaction_evidence),
        "demand_status": event.demand_status,
        "reaction_search_quality": event.reaction_search_quality,
        "reaction_evidence_urls": [str(item.url) for item in event.reaction_evidence],
        "preferred_reaction_sources": list(plan.preferred_sources),
        "checked_reaction_sources": list(event.reaction_sources_checked),
        "missing_reaction_sources": [source for source in plan.preferred_sources if source not in event.reaction_sources_checked],
        "supply_candidate_count": event.supply_candidate_count,
        "supply_evidence_count": len(event.supply_evidence),
        "supply_status": event.supply_status,
        "gap_status": event.gap_status,
        "supply_audit": supply_audit.__dict__ if supply_audit else None,
        "status": "evaluated",
    }


def _metrics_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [row for row in rows if row.get("status") == "evaluated"]
    demand_labeled = [row for row in evaluated if row.get("ground_truth_demand") in {"yes", "no"}]
    demand_hits = [row for row in demand_labeled if row.get("demand_status") in {"early_signal", "repeated_signal"}]
    true_yes = [row for row in demand_labeled if row.get("ground_truth_demand") == "yes"]
    demand_recall = sum(1 for row in true_yes if row.get("demand_status") in {"early_signal", "repeated_signal"}) / len(true_yes) if true_yes else None
    return {
        "cases_evaluated": len(evaluated),
        "demand_labeled": len(demand_labeled),
        "demand_detected": len(demand_hits),
        "demand_recall": round(demand_recall, 4) if demand_recall is not None else None,
        "search_failed": sum(1 for row in evaluated if row.get("reaction_search_quality") == "failed"),
        "coverage_degraded": sum(1 for row in evaluated if row.get("missing_reaction_sources")),
        "supply_runs": sum(1 for row in evaluated if row.get("supply_audit") is not None),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall = _metrics_for(rows)
    cohorts = sorted({str(row.get("cohort", "headline")) for row in rows})
    overall["by_cohort"] = {cohort: _metrics_for([row for row in rows if row.get("cohort", "headline") == cohort]) for cohort in cohorts}
    return overall


def run(fixture: Path, output: Path, *, as_of: date | None = None) -> dict[str, Any]:
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    if as_of:
        cases = [case for case in cases if date.fromisoformat(str(case["event_date"])) <= as_of]
    rows = [run_case(case) for case in cases]
    report = {
        "mode": "self_discovery",
        "fixture": str(fixture),
        "as_of": as_of.isoformat() if as_of else None,
        "metrics": summarize(rows),
        "results": rows,
        "limitations": [
            "No reaction or supply URLs are supplied to the scout; it must query its implemented sources itself from vendor/product/date context.",
            "The official event document is still fixture-provided; this benchmark isolates downstream discovery rather than Tier-1 event discovery.",
            "Reaction candidates are restricted to the event-to-as-of window to avoid counting unrelated pre-event discussions as displacement evidence.",
            "Preferred ecosystem sources that are not implemented are reported as coverage gaps and downgrade search quality.",
            "GitHub supply candidates are filtered to repositories created by the historical as-of date, but repository metadata is current. Current star counts are deliberately ignored.",
            "No detected signal is not proof of no demand; failed or incomplete source coverage remains visible.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="GapRadar historical self-discovery benchmark")
    parser.add_argument("--fixture", default="data/backtest/events.json")
    parser.add_argument("--output", default="data/backtest/report-discovery.json")
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()
    cutoff = date.fromisoformat(args.as_of) if args.as_of else None
    report = run(Path(args.fixture), Path(args.output), as_of=cutoff)
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
