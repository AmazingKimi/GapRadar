from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Literal

import httpx

from .detector import classify_entry, event_from_document
from .reaction import archived_reaction_evidence
from .supply import archived_supply_evidence


@dataclass(frozen=True)
class ArchiveSnapshot:
    requested_url: str
    timestamp: str
    original_url: str
    archive_url: str
    html: str


class WaybackClient:
    """Small, auditable Internet Archive client used only by historical replay."""

    cdx_url = "https://web.archive.org/cdx/search/cdx"

    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout
        self.headers = {"User-Agent": "GapRadar/0.7 (+https://github.com/AmazingKimi/GapRadar)"}

    def closest_before(self, url: str, as_of: datetime) -> ArchiveSnapshot | None:
        stamp = as_of.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        params = {
            "url": url,
            "output": "json",
            "fl": "timestamp,original,statuscode,mimetype,digest",
            "filter": ["statuscode:200", "mimetype:text/html"],
            "to": stamp,
            "limit": "1",
            "sort": "reverse",
            "collapse": "digest",
        }
        response = httpx.get(self.cdx_url, params=params, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        rows = response.json()
        if len(rows) < 2:
            return None
        timestamp, original, *_ = rows[1]
        archive_url = f"https://web.archive.org/web/{timestamp}id_/{original}"
        page = httpx.get(archive_url, headers=self.headers, timeout=self.timeout, follow_redirects=True)
        page.raise_for_status()
        return ArchiveSnapshot(url, timestamp, original, archive_url, page.text)


def _strip_html(value: str) -> str:
    value = re.sub(r"(?is)<script\b.*?</script>", " ", value)
    value = re.sub(r"(?is)<style\b.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def extract_page(html_text: str) -> tuple[str, str]:
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
    h1_match = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html_text)
    title = _strip_html((h1_match or title_match).group(1)) if (h1_match or title_match) else ""
    body = _strip_html(html_text)
    return title[:500], body[:12000]


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _as_datetime(value: date) -> datetime:
    return datetime.combine(value, time(23, 59, 59), tzinfo=timezone.utc)


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("backtest fixture must be a JSON list")
    return payload


def load_downstream(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("downstream benchmark must be a JSON object keyed by event id")
    return payload


def _classify_case(title: str, body: str) -> tuple[bool, str | None]:
    detected = classify_entry(title, body, allow_strong_body=True)
    return detected is not None, detected.value if detected else None


def _page_content(
    spec: dict[str, Any],
    *,
    mode: Literal["fixture", "wayback"],
    target: date,
    wayback: WaybackClient | None,
) -> tuple[str, str, str | None, str]:
    url = str(spec["url"])
    if mode == "fixture":
        return str(spec.get("title_hint") or ""), str(spec.get("excerpt_hint") or ""), None, "evaluated"
    assert wayback is not None
    try:
        snapshot = wayback.closest_before(url, _as_datetime(target))
    except Exception as exc:
        return "", "", f"{type(exc).__name__}: {exc}", "archive_error"
    if snapshot is None:
        return "", "", None, "archive_missing"
    title, body = extract_page(snapshot.html)
    return title, body, snapshot.archive_url, "evaluated"


def _replay_downstream(event, downstream: dict[str, Any], *, mode: Literal["fixture", "wayback"], target: date, wayback: WaybackClient | None) -> dict[str, Any]:
    reaction_specs = list(downstream.get("reaction_pages") or [])
    supply_specs = list(downstream.get("supply_pages") or [])
    reaction_rows: list[dict[str, Any]] = []
    supply_rows: list[dict[str, Any]] = []

    for spec in reaction_specs:
        title, body, archive_or_error, status = _page_content(spec, mode=mode, target=target, wayback=wayback)
        evidence = None
        if status == "evaluated":
            evidence = archived_reaction_evidence(
                event, title=title, body=body, url=str(spec["url"]),
                publisher=str(spec.get("publisher") or "Archived community"),
                published_at=_as_datetime(target), engagement=int(spec.get("engagement") or 0),
            )
            if evidence is not None:
                event.reaction_evidence.append(evidence)
        reaction_rows.append({"url": spec["url"], "status": status, "qualified": evidence is not None, "archive_url": archive_or_error if status == "evaluated" and mode == "wayback" else None, "error": archive_or_error if status == "archive_error" else None})

    if reaction_specs:
        event.reaction_checked_at = _as_datetime(target)
        event.reaction_sources_checked = ["historical_fixture" if mode == "fixture" else "wayback_reaction"]
        event.reaction_candidate_count = sum(1 for row in reaction_rows if row["status"] == "evaluated")
        event.reaction_search_quality = "adequate" if all(row["status"] == "evaluated" for row in reaction_rows) else "degraded"
        event.verify()

    for spec in supply_specs:
        title, body, archive_or_error, status = _page_content(spec, mode=mode, target=target, wayback=wayback)
        evidence = None
        if status == "evaluated":
            evidence = archived_supply_evidence(
                event, title=title, body=body, url=str(spec["url"]),
                publisher=str(spec.get("publisher") or "Archived supply"), observed_at=_as_datetime(target),
                popularity=int(spec.get("popularity") or 0), archived=bool(spec.get("archived", False)),
                quality_hint=float(spec.get("quality_hint") or 0.0),
            )
            if evidence is not None:
                event.supply_evidence.append(evidence)
        supply_rows.append({"url": spec["url"], "status": status, "qualified": evidence is not None, "archive_url": archive_or_error if status == "evaluated" and mode == "wayback" else None, "error": archive_or_error if status == "archive_error" else None})

    if supply_specs:
        event.supply_checked_at = _as_datetime(target)
        event.supply_sources_checked = ["historical_fixture" if mode == "fixture" else "wayback_supply"]
        event.supply_candidate_count = sum(1 for row in supply_rows if row["status"] == "evaluated")
        event.verify()

    return {
        "reaction_pages": reaction_rows,
        "reaction_pages_total": len(reaction_rows),
        "reaction_pages_evaluated": sum(1 for row in reaction_rows if row["status"] == "evaluated"),
        "reaction_qualified": len(event.reaction_evidence),
        "observed_demand_status": event.demand_status if reaction_specs else None,
        "supply_pages": supply_rows,
        "supply_pages_total": len(supply_rows),
        "supply_pages_evaluated": sum(1 for row in supply_rows if row["status"] == "evaluated"),
        "supply_qualified": len(event.supply_evidence),
        "observed_supply_status": event.supply_status if supply_specs else None,
        "observed_gap_status": event.gap_status if reaction_specs and supply_specs else None,
    }


def replay_case(case: dict[str, Any], *, mode: Literal["fixture", "wayback"], wayback: WaybackClient | None = None, downstream: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = bool(case.get("expected_detect", True))
    target = _parse_day(str(case["replay_as_of"]))
    snapshot_meta: dict[str, Any] = {}

    if mode == "wayback":
        if wayback is None:
            wayback = WaybackClient()
        try:
            snapshot = wayback.closest_before(str(case["official_url"]), _as_datetime(target))
        except Exception as exc:
            return {"id": case["id"], "expected_detect": expected, "status": "archive_error", "error": f"{type(exc).__name__}: {exc}"}
        if snapshot is None:
            return {"id": case["id"], "expected_detect": expected, "status": "archive_missing"}
        title, body = extract_page(snapshot.html)
        snapshot_meta = {"snapshot_timestamp": snapshot.timestamp, "snapshot_url": snapshot.archive_url, "observed_title": title}
    else:
        title = str(case.get("title_hint") or "")
        body = str(case.get("excerpt_hint") or "")

    detected, observed_type = _classify_case(title, body)
    expected_type = case.get("event_type") if expected else None
    type_match = (observed_type == expected_type) if expected and detected else None
    outcome = "tp" if expected and detected else "fn" if expected else "fp" if detected else "tn"

    downstream_result: dict[str, Any] = {}
    if detected and downstream:
        event = event_from_document(
            vendor=str(case.get("vendor") or "Unknown"), product=str(case.get("product") or "Unknown"),
            title=title, summary=body, url=str(case["official_url"]),
            published_at=_as_datetime(_parse_day(str(case["event_date"]))), historical=True,
        )
        if event is not None:
            downstream_result = _replay_downstream(event, downstream, mode=mode, target=target, wayback=wayback)

    return {
        "id": case["id"], "vendor": case.get("vendor"), "product": case.get("product"),
        "event_date": case.get("event_date"), "replay_as_of": case.get("replay_as_of"),
        "official_url": case.get("official_url"), "expected_detect": expected, "expected_type": expected_type,
        "observed_detect": detected, "observed_type": observed_type, "type_match": type_match, "outcome": outcome,
        "ground_truth_demand": case.get("ground_truth_demand", "unknown"), "ground_truth_supply": case.get("ground_truth_supply", "unknown"),
        "retracted": bool(case.get("retracted", False)), "status": "evaluated", **snapshot_meta, **downstream_result,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [row for row in results if row.get("status") == "evaluated"]
    counts = {key: sum(1 for row in evaluated if row.get("outcome") == key) for key in ("tp", "fp", "tn", "fn")}
    precision_den = counts["tp"] + counts["fp"]
    recall_den = counts["tp"] + counts["fn"]
    positives_with_type = [row for row in evaluated if row.get("expected_detect") and row.get("observed_detect")]
    type_correct = sum(1 for row in positives_with_type if row.get("type_match"))
    unavailable = [row for row in results if row.get("status") != "evaluated"]

    demand_rows = [row for row in evaluated if row.get("reaction_pages_total", 0) > 0 and row.get("reaction_pages_evaluated", 0) > 0]
    demand_correct = sum(1 for row in demand_rows if (row.get("ground_truth_demand") == "yes") == (row.get("observed_demand_status") in {"early_signal", "repeated_signal"}))
    supply_rows = [row for row in evaluated if row.get("supply_pages_total", 0) > 0 and row.get("supply_pages_evaluated", 0) > 0]
    supply_correct = sum(1 for row in supply_rows if (row.get("ground_truth_supply") == "served") == (row.get("observed_supply_status") == "served"))

    return {
        "cases_total": len(results), "cases_evaluated": len(evaluated), "archive_unavailable": len(unavailable),
        "tp": counts["tp"], "fp": counts["fp"], "tn": counts["tn"], "fn": counts["fn"],
        "precision": round(counts["tp"] / precision_den, 4) if precision_den else None,
        "recall": round(counts["tp"] / recall_den, 4) if recall_den else None,
        "event_type_accuracy": round(type_correct / len(positives_with_type), 4) if positives_with_type else None,
        "archive_coverage": round(len(evaluated) / len(results), 4) if results else None,
        "demand_cases_evaluated": len(demand_rows), "demand_accuracy": round(demand_correct / len(demand_rows), 4) if demand_rows else None,
        "supply_cases_evaluated": len(supply_rows), "supply_accuracy": round(supply_correct / len(supply_rows), 4) if supply_rows else None,
    }


def run_backtest(fixture_path: Path, *, as_of: date | None = None, mode: Literal["fixture", "wayback"] = "fixture") -> dict[str, Any]:
    cases = load_cases(fixture_path)
    if as_of is not None:
        cases = [case for case in cases if _parse_day(str(case["event_date"])) <= as_of]
    downstream_path = fixture_path.with_name("downstream.json")
    downstream = load_downstream(downstream_path)

    if mode == "wayback":
        def run_one(case: dict[str, Any]) -> dict[str, Any]:
            return replay_case(case, mode=mode, wayback=WaybackClient(), downstream=downstream.get(str(case["id"])))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(run_one, cases))
    else:
        results = [replay_case(case, mode=mode, downstream=downstream.get(str(case["id"]))) for case in cases]

    return {
        "mode": mode, "as_of": as_of.isoformat() if as_of else None, "fixture": str(fixture_path),
        "downstream_fixture": str(downstream_path) if downstream_path.exists() else None,
        "metrics": summarize(results), "results": results,
        "limitations": [
            "Fixture mode is a hand-curated benchmark, not a universal accuracy estimate.",
            "Wayback mode scores only retrievable archived documents; archive misses/errors are reported separately and never converted into detector misses.",
            "Demand/supply accuracy is calculated only for cases with explicit benchmark evidence pages that were actually evaluated; its coverage is intentionally shown alongside the metric.",
        ],
    }
