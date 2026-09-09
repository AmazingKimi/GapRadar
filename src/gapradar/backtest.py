from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Literal

import httpx

from .detector import classify_entry
from .models import EventType


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

    def __init__(self, timeout: float = 25.0) -> None:
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


def _classify_case(case: dict[str, Any], title: str, body: str) -> tuple[bool, str | None]:
    detected = classify_entry(title, body)
    return detected is not None, detected.value if detected else None


def replay_case(
    case: dict[str, Any],
    *,
    mode: Literal["fixture", "wayback"],
    wayback: WaybackClient | None = None,
) -> dict[str, Any]:
    expected = bool(case.get("expected_detect", True))
    target = _parse_day(str(case["replay_as_of"]))
    snapshot_meta: dict[str, Any] = {}

    if mode == "wayback":
        if wayback is None:
            wayback = WaybackClient()
        try:
            snapshot = wayback.closest_before(str(case["official_url"]), _as_datetime(target))
        except Exception as exc:
            return {
                "id": case["id"],
                "expected_detect": expected,
                "status": "archive_error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if snapshot is None:
            return {"id": case["id"], "expected_detect": expected, "status": "archive_missing"}
        title, body = extract_page(snapshot.html)
        snapshot_meta = {
            "snapshot_timestamp": snapshot.timestamp,
            "snapshot_url": snapshot.archive_url,
            "observed_title": title,
        }
    else:
        title = str(case.get("title_hint") or "")
        body = str(case.get("excerpt_hint") or "")

    detected, observed_type = _classify_case(case, title, body)
    expected_type = case.get("event_type") if expected else None
    type_match = (observed_type == expected_type) if expected and detected else None

    if expected and detected:
        outcome = "tp"
    elif expected and not detected:
        outcome = "fn"
    elif not expected and detected:
        outcome = "fp"
    else:
        outcome = "tn"

    return {
        "id": case["id"],
        "vendor": case.get("vendor"),
        "product": case.get("product"),
        "event_date": case.get("event_date"),
        "replay_as_of": case.get("replay_as_of"),
        "official_url": case.get("official_url"),
        "expected_detect": expected,
        "expected_type": expected_type,
        "observed_detect": detected,
        "observed_type": observed_type,
        "type_match": type_match,
        "outcome": outcome,
        "ground_truth_demand": case.get("ground_truth_demand", "unknown"),
        "ground_truth_supply": case.get("ground_truth_supply", "unknown"),
        "retracted": bool(case.get("retracted", False)),
        "status": "evaluated",
        **snapshot_meta,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [row for row in results if row.get("status") == "evaluated"]
    counts = {key: sum(1 for row in evaluated if row.get("outcome") == key) for key in ("tp", "fp", "tn", "fn")}
    precision_den = counts["tp"] + counts["fp"]
    recall_den = counts["tp"] + counts["fn"]
    positives_with_type = [row for row in evaluated if row.get("expected_detect") and row.get("observed_detect")]
    type_correct = sum(1 for row in positives_with_type if row.get("type_match"))
    unavailable = [row for row in results if row.get("status") != "evaluated"]
    return {
        "cases_total": len(results),
        "cases_evaluated": len(evaluated),
        "archive_unavailable": len(unavailable),
        "tp": counts["tp"],
        "fp": counts["fp"],
        "tn": counts["tn"],
        "fn": counts["fn"],
        "precision": round(counts["tp"] / precision_den, 4) if precision_den else None,
        "recall": round(counts["tp"] / recall_den, 4) if recall_den else None,
        "event_type_accuracy": round(type_correct / len(positives_with_type), 4) if positives_with_type else None,
        "archive_coverage": round(len(evaluated) / len(results), 4) if results else None,
    }


def run_backtest(
    fixture_path: Path,
    *,
    as_of: date | None = None,
    mode: Literal["fixture", "wayback"] = "fixture",
) -> dict[str, Any]:
    cases = load_cases(fixture_path)
    if as_of is not None:
        cases = [case for case in cases if _parse_day(str(case["event_date"])) <= as_of]
    client = WaybackClient() if mode == "wayback" else None
    results = [replay_case(case, mode=mode, wayback=client) for case in cases]
    return {
        "mode": mode,
        "as_of": as_of.isoformat() if as_of else None,
        "fixture": str(fixture_path),
        "metrics": summarize(results),
        "results": results,
        "limitations": [
            "Fixture mode validates deterministic detector behavior against manually curated historical ground truth.",
            "Wayback mode measures only cases with retrievable archived snapshots; archive misses are reported separately and are never counted as detector misses.",
            "Demand and supply labels are preserved as ground truth metadata but are not scored until archived reaction/supply evidence is attached to a case.",
        ],
    }
