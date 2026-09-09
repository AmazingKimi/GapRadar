from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import feedparser
import httpx
import yaml


CHANGE_PATTERNS: dict[str, tuple[str, ...]] = {
    "shutdown_eol": (
        r"\bshut(?:ting)? down\b", r"\bshutdown\b", r"\bsunset(?:ting)?\b", r"\bdiscontinu(?:e|ed|ing|ation)\b",
        r"\bretir(?:e|ed|ing|ement)\b", r"\bend[- ]of[- ]life\b", r"\bend of support\b", r"\bending support\b",
        r"\bwill close\b", r"\bis closing\b", r"\bcloses?\b", r"\bkills?\b", r"\bgoes away\b",
    ),
    "price_shock": (
        r"\bprice increase\b", r"\bprice hike\b", r"\braises? prices?\b", r"\bpricing changes?\b",
        r"\bprices? (?:are )?going up\b", r"\bfree tier\b.{0,70}\bend", r"\bcharging for\b", r"\bsubscription price\b",
    ),
    "api_terms_change": (
        r"\bapi\b.{0,80}\bdeprecat", r"\bapi\b.{0,80}\bpricing\b", r"\bapi access\b.{0,80}\bchange",
        r"\bdeveloper policy\b", r"\bterms of service\b.{0,60}\bchange", r"\blicen[cs](?:e|ing) change\b",
        r"\brate limits?\b.{0,50}\bchange", r"\bdeprecat(?:e|ed|ing|ion)\b.{0,80}\bapi\b",
    ),
    "regulatory_shift": (
        r"\bnew regulation\b", r"\bnew rules?\b", r"\bcompliance deadline\b",
        r"\bmandat(?:e|ed|ory)\b", r"\blaw takes effect\b", r"\bregulator\b.{0,80}\brequir",
    ),
}

TECH_TERMS = re.compile(
    r"\b(software|saas|app|platform|api|cloud|developer|ai|ecommerce|e-commerce|payment|cyber|security|data|hosting|crm|automation|browser|mobile|marketplace|fintech|subscription|service|tool)\b",
    re.IGNORECASE,
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "from", "after", "before",
    "will", "is", "are", "its", "new", "this", "that", "as", "at", "by", "up", "down", "service", "platform",
}


@dataclass(frozen=True)
class GapCandidate:
    id: str
    discovered_at: str
    published_at: str | None
    source: str
    headline: str
    url: str
    summary: str
    change_type: str
    matched_signal: str
    recommendation: str
    why_now: str
    gap_hypothesis: str
    validation_status: str
    validation_summary: str


def _clean(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value or "").split())


def _published(entry: object) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def classify_change(text: str) -> tuple[str, str] | None:
    for change_type, patterns in CHANGE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return change_type, _clean(match.group(0))[:120]
    return None


def _gap_hypothesis(change_type: str) -> tuple[str, str, str]:
    if change_type == "shutdown_eol":
        return (
            "REVIEW",
            "Users, workflows or integrations must move before the old product disappears.",
            "Look for a replacement that preserves the abandoned workflow with lower migration cost, better compatibility, or a narrower vertical focus.",
        )
    if change_type == "price_shock":
        return (
            "REVIEW",
            "A pricing discontinuity can release budget-sensitive users who were previously locked into the incumbent.",
            "Look for a simpler lower-cost substitute, usage-based alternative, migration service, or vertical product that removes features customers no longer want to pay for.",
        )
    if change_type == "api_terms_change":
        return (
            "REVIEW",
            "Developers and businesses may need to rewrite integrations, replace data access, or absorb new platform constraints.",
            "Look for compatibility layers, migration tooling, alternative data/API providers, or workflow products that reduce dependence on the changed platform.",
        )
    return (
        "WATCH",
        "A rule or compliance change can create new mandatory work that did not exist before.",
        "Look for compliance automation, evidence collection, reporting, migration, or vertical workflow software created by the new requirement.",
    )


def _fingerprint(headline: str, change_type: str) -> str:
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9+.-]{2,}", headline) if t.lower() not in STOPWORDS]
    raw = change_type + "|" + " ".join(tokens[:8])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_world_feeds(path: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(payload.get("feeds", []))


def scan_world(
    config: Path = Path("config/world_sources.yml"),
    *,
    now: datetime | None = None,
    timeout: float = 15.0,
) -> list[GapCandidate]:
    now = now or datetime.now(timezone.utc)
    rows: dict[str, GapCandidate] = {}
    headers = {"User-Agent": "GapRadar/0.8 world-scan"}

    for source in load_world_feeds(config):
        name = str(source.get("name") or "World feed")
        url = str(source.get("url") or "")
        if not url:
            continue
        lookback_hours = int(source.get("lookback_hours") or 72)
        max_entries = int(source.get("max_entries") or 80)
        forced_type = str(source.get("change_type") or "").strip() or None
        prefiltered = bool(source.get("prefiltered", False))
        try:
            response = httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except Exception:
            continue

        for entry in list(parsed.entries)[:max_entries]:
            published = _published(entry)
            if published and published < now - timedelta(hours=lookback_hours):
                continue
            headline = _clean(str(getattr(entry, "title", "")))
            summary = _clean(str(getattr(entry, "summary", "") or getattr(entry, "description", "")))
            link = str(getattr(entry, "link", "")).strip()
            if not headline or not link:
                continue
            text = f"{headline} {summary}"
            classified = classify_change(text)
            if classified:
                change_type, matched_signal = classified
            elif forced_type:
                change_type, matched_signal = forced_type, "query-matched structural change"
            else:
                continue
            if not prefiltered and not TECH_TERMS.search(text):
                continue
            recommendation, why_now, gap_hypothesis = _gap_hypothesis(change_type)
            status = "NEWS SIGNAL" if forced_type and not classified else "STRUCTURAL SIGNAL"
            candidate = GapCandidate(
                id=_fingerprint(headline, change_type),
                discovered_at=now.isoformat(),
                published_at=published.isoformat() if published else None,
                source=name,
                headline=headline[:300],
                url=link,
                summary=summary[:900],
                change_type=change_type,
                matched_signal=matched_signal,
                recommendation=recommendation,
                why_now=why_now,
                gap_hypothesis=gap_hypothesis,
                validation_status=status,
                validation_summary=(
                    f"GapRadar found this {change_type.replace('_', ' ')} candidate in {name}. "
                    + ("The feed itself is a targeted structural-change search, so this remains a discovery lead until a first-party source or independent confirmation is attached. " if status == "NEWS SIGNAL" else "An explicit structural-change phrase was present in the item. ")
                    + "It is a market-gap lead, not proof that replacement supply is weak or that the opportunity is profitable."
                ),
            )
            rows.setdefault(candidate.id, candidate)

    return sorted(rows.values(), key=lambda row: row.published_at or row.discovered_at, reverse=True)


def save_candidates(path: Path, candidates: Iterable[GapCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in candidates], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_candidates(path: Path) -> list[GapCandidate]:
    if not path.exists():
        return []
    return [GapCandidate(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
