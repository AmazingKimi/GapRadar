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
    "api_terms_change": (
        r"\bapi\b.{0,80}\bdeprecat",
        r"\bapi\b.{0,80}\bpricing\b",
        r"\bapi access\b.{0,80}\bchange",
        r"\bterms of service\b.{0,60}\bchange",
        r"\blicen[cs](?:e|ing) change\b",
        r"\blicen[cs]e terms?\b.{0,80}\b(change|changing|changed|adopt|adopted)\b",
        r"\bbusiness source licen[cs]e\b",
        r"\bcommercial access terms?\b",
        r"\brate limits?\b.{0,50}\bchange",
        r"\bdeprecat(?:e|ed|ing|ion)\b.{0,80}\b(api|sdk|integration|extension)\b",
        r"\b(api|sdk|integration|extension)\b.{0,80}\b(no longer|removed|restricted|unsupported)\b",
    ),
    "shutdown_eol": (
        r"\bshut(?:ting)? down\b",
        r"\bshutdown\b",
        r"\bsunset(?:ting)?\b",
        r"\bdiscontinu(?:e|ed|ing|ation)\b",
        r"\bretir(?:e|ed|ing|ement)\b",
        r"\bphase(?:d|s|ing)? out\b",
        r"\bwind(?:ing)? down\b",
        r"\bend[- ]of[- ]life\b",
        r"\bend of support\b",
        r"\bending support\b",
        r"\bno longer (?:be )?(?:supported|available|run|operate|offered)\b",
        r"\bwill close\b",
        r"\bis closing\b",
        r"\bgoes away\b",
        r"\bgoing away\b",
        r"\bsaying goodbye to\b",
    ),
    "price_shock": (
        r"\bprice increase\b",
        r"\bprice hike\b",
        r"\braises? prices?\b",
        r"\bpricing changes?\b",
        r"\bprices? (?:are )?going up\b",
        r"\bintroduc(?:e|ed|ing)\b.{0,80}\b(?:new )?(?:runtime )?fee\b",
        r"\bnew (?:runtime )?fee\b",
        r"\bfree (?:tier|plan|users?)\b.{0,100}\b(?:end|ending|remove|removed|cut|limit|limited|deactivat|disconnect|no longer|only available)\b",
        r"\b(?:sms|phone call|feature|features|service|services|access)\b.{0,100}\bonly be available to\b.{0,80}\b(?:pro|paid|premium|enterprise)\b",
        r"\bcharging for\b",
        r"\bsubscription price\b",
        r"\bcancel(?:ing|led|s)?\b.{0,60}\bfee\b",
    ),
    "regulatory_shift": (
        r"\bnew regulation\b",
        r"\bcompliance deadline\b",
        r"\bmandat(?:e|ed|ory)\b",
        r"\blaw takes effect\b",
        r"\bregulator\b.{0,80}\brequir",
        r"\bwill require\b.{0,120}\b(data|software|ai|cyber|platform|energy|power|emissions|health|finance)",
    ),
}

TECH_TERMS = re.compile(
    r"\b(software|saas|app|apps|platform|api|cloud|developer|ai|ecommerce|e-commerce|payment|cyber|security|data|hosting|crm|automation|browser|mobile|marketplace|fintech|subscription|service|tool|streaming|editor|extension|podcast|whiteboard|integration|sdk|energy|power|electricity|grid|battery|storage|solar|wind|nuclear|climate|carbon|emissions|health|healthcare|biotech|drug|medical|banking|insurance|robot|robotics|manufacturing|supply chain|ev|vehicle|mobility|logistics|space|quantum|semiconductor)\b",
    re.IGNORECASE,
)
STOPWORDS = {"the","a","an","and","or","to","of","for","in","on","with","from","after","before","will","is","are","its","new","this","that","as","at","by","up","down","service","platform"}

SECTOR_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Energy & Climate", re.compile(r"\b(energy|electricity|power grid|grid|battery|storage|solar|wind|nuclear|climate|carbon|emissions|renewable|hydrogen|data center power)\b", re.I)),
    ("Healthcare & Biotech", re.compile(r"\b(health|healthcare|biotech|drug|pharma|medical|hospital|clinical|fda|therapy)\b", re.I)),
    ("Finance & Fintech", re.compile(r"\b(fintech|bank|banking|payment|payments|insurance|lending|credit|financial|trading|sec\b)\b", re.I)),
    ("Mobility", re.compile(r"\b(ev|electric vehicle|vehicle|automotive|autonomous|charging|mobility|logistics|aviation|rail|transport)\b", re.I)),
    ("Industry & Robotics", re.compile(r"\b(robot|robotics|manufacturing|factory|industrial|automation|supply chain)\b", re.I)),
    ("Frontier", re.compile(r"\b(space|satellite|quantum|semiconductor|chip|new material|synthetic biology)\b", re.I)),
    ("AI & Technology", re.compile(r"\b(ai|artificial intelligence|software|saas|app|api|cloud|developer|cyber|data|platform|ecommerce|streaming|editor|extension|podcast|whiteboard)\b", re.I)),
)

IRRELEVANT_SHUTDOWN = re.compile(
    r"\b(government shutdown|airport shutdown|road closure|school closure|restaurant closing|store closing|factory shutdown|plant shutdown|mine shutdown|refinery shutdown|power station shutdown)\b",
    re.I,
)


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
    sector: str = "Other"
    image_url: str | None = None


@dataclass(frozen=True)
class WorldScanStats:
    scanned_at: str
    sources_configured: int
    sources_ok: int
    sources_failed: int
    raw_entries: int
    recent_entries: int
    structural_matches: int
    candidates: int


def _clean(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value or "").split())


def _base_headline(headline: str) -> str:
    return re.sub(r"\s+-\s+[^-]{2,80}$", "", headline).strip()


def _published(entry: object) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    return datetime(*parsed[:6], tzinfo=timezone.utc) if parsed else None


def _entry_image(entry: object) -> str | None:
    for thumb in getattr(entry, "media_thumbnail", []) or []:
        if isinstance(thumb, dict) and thumb.get("url"):
            return str(thumb["url"])
    for enc in getattr(entry, "enclosures", []) or []:
        if isinstance(enc, dict) and str(enc.get("type", "")).startswith("image/") and enc.get("href"):
            return str(enc["href"])
    for link in getattr(entry, "links", []) or []:
        if isinstance(link, dict) and str(link.get("type", "")).startswith("image/") and link.get("href"):
            return str(link["href"])
    return None


def infer_sector(text: str) -> str:
    for sector, pattern in SECTOR_RULES:
        if pattern.search(text):
            return sector
    return "Consumer & Society"


def classify_change(text: str) -> tuple[str, str] | None:
    for change_type, patterns in CHANGE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return change_type, _clean(match.group(0))[:120]
    return None


def _forced_gate(change_type: str, text: str) -> bool:
    t = text.lower()
    if change_type == "shutdown_eol":
        if IRRELEVANT_SHUTDOWN.search(t):
            return False
        return bool(
            re.search(
                r"\b(shut(?:ting)? down|shutdown|sunset|discontinu|retir|phase(?:d|s|ing)? out|wind(?:ing)? down|end[- ]of[- ]life|end(?:ing)? support|no longer (?:be )?(?:supported|available|run|operate|offered)|closing|goes away|going away|saying goodbye)\b",
                t,
            )
        )
    if change_type == "price_shock":
        explicit_price = bool(
            re.search(r"\b(price|pricing|fee|subscription|cost)\b", t)
            and re.search(r"\b(increase|hike|raise|raised|rising|change|changes|higher|up|charge|charging|introduc|cancel)\b", t)
        )
        free_restriction = bool(
            re.search(r"\bfree (?:tier|plan|users?)\b.{0,120}\b(end|ending|remove|removed|cut|limit|limited|deactivat|disconnect|no longer|only available)\b", t)
        )
        paid_only = bool(re.search(r"\bonly be available to\b.{0,80}\b(pro|paid|premium|enterprise)\b", t))
        return explicit_price or free_restriction or paid_only
    if change_type == "api_terms_change":
        api_context = bool(re.search(r"\b(api|sdk|integration|extension|license|licensing|terms|commercial access)\b", t))
        hard_change = bool(re.search(r"\b(deprecat|terms|policy|rate limit|pricing|license|licensing|access change|restriction|business source|no longer|removed)\b", t))
        return api_context and hard_change
    if change_type == "regulatory_shift":
        if re.search(r"\b(protest|rally|march|concern|calls? for regulation|opinion|commentary|debate|podcast|thought for the week|mocks?|warns?|priority|talks? about|could influence|should take center stage|new rules of|regulation talks?)\b", t):
            return False
        if re.search(r"\b(launches?|unveils?|introduces?)\b.{0,40}\b(solution|product|tool)\b", t):
            return False
        hard_action = bool(re.search(r"\b(will require|requires?|required|mandate|mandatory|law takes effect|new law|adopts?|adopted|approved|passes?|passed|compliance deadline|rules? take effect|policy takes effect|plan for ai regulation|set up ai regulator)\b", t))
        government_rules = bool(re.search(r"\b(government|regulator|legislature|parliament|commission|agency|state|massachusetts|eu|european union)\b.{0,120}\b(new rules?|rules?|requirements?|regulation|policy)\b", t))
        named_act = bool(re.search(r"\b(ai act|data act|digital services act|digital markets act|climate law|energy act)\b.{0,100}\b(obligation|requirement|guidance|compliance|rule)\b", t))
        return (hard_action or government_rules or named_act) and bool(TECH_TERMS.search(t))
    return False


def _candidate_gate(change_type: str, text: str) -> bool:
    return _forced_gate(change_type, text)


def _gap_hypothesis(change_type: str) -> tuple[str, str, str]:
    if change_type == "shutdown_eol":
        return "REVIEW", "Users, workflows or integrations must move before the old product disappears.", "Look for a replacement that preserves the abandoned workflow with lower migration cost, better compatibility, or a narrower vertical focus."
    if change_type == "price_shock":
        return "REVIEW", "A pricing discontinuity can release budget-sensitive users who were previously locked into the incumbent.", "Look for a simpler lower-cost substitute, usage-based alternative, migration service, or vertical product that removes features customers no longer want to pay for."
    if change_type == "api_terms_change":
        return "REVIEW", "Developers and businesses may need to rewrite integrations, replace data access, or absorb new platform constraints.", "Look for compatibility layers, migration tooling, alternative data/API providers, or workflow products that reduce dependence on the changed platform."
    return "WATCH", "A rule or compliance change can create new mandatory work that did not exist before.", "Look for compliance automation, evidence collection, reporting, migration, or vertical workflow software created by the new requirement."


def _fingerprint(headline: str, change_type: str) -> str:
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9+.-]{2,}", _base_headline(headline)) if t.lower() not in STOPWORDS]
    return hashlib.sha1((change_type + "|" + " ".join(tokens[:8])).encode()).hexdigest()[:16]


def load_world_feeds(path: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(payload.get("feeds", []))


def scan_world_with_stats(config: Path = Path("config/world_sources.yml"), *, now: datetime | None = None, timeout: float = 15.0) -> tuple[list[GapCandidate], WorldScanStats]:
    now = now or datetime.now(timezone.utc)
    rows: dict[str, GapCandidate] = {}
    feeds = load_world_feeds(config)
    headers = {"User-Agent": "GapRadar/0.9 world-scan"}
    sources_ok = sources_failed = raw_entries = recent_entries = structural_matches = 0

    for source in feeds:
        name = str(source.get("name") or "World feed")
        url = str(source.get("url") or "")
        if not url:
            sources_failed += 1
            continue
        lookback_hours = int(source.get("lookback_hours") or 72)
        max_entries = int(source.get("max_entries") or 80)
        forced_type = str(source.get("change_type") or "").strip() or None
        prefiltered = bool(source.get("prefiltered", False))
        try:
            response = httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            sources_ok += 1
        except Exception:
            sources_failed += 1
            continue

        entries = list(parsed.entries)[:max_entries]
        raw_entries += len(entries)
        for entry in entries:
            published = _published(entry)
            if published and published < now - timedelta(hours=lookback_hours):
                continue
            recent_entries += 1
            headline = _clean(str(getattr(entry, "title", "")))
            summary = _clean(str(getattr(entry, "summary", "") or getattr(entry, "description", "")))
            link = str(getattr(entry, "link", "")).strip()
            if not headline or not link:
                continue

            text = f"{headline} {summary}"
            classified = classify_change(text)
            if classified:
                change_type, matched_signal = classified
                if forced_type and change_type != forced_type and not _forced_gate(forced_type, text):
                    continue
                if not _candidate_gate(change_type, text):
                    continue
            elif forced_type and _forced_gate(forced_type, text):
                change_type, matched_signal = forced_type, "query-filtered structural change"
            else:
                continue

            if not prefiltered and not TECH_TERMS.search(text):
                continue

            structural_matches += 1
            recommendation, why_now, gap_hypothesis = _gap_hypothesis(change_type)
            status = "NEWS SIGNAL" if forced_type and not classified else "STRUCTURAL SIGNAL"
            candidate = GapCandidate(
                id=_fingerprint(headline, change_type),
                discovered_at=now.isoformat(),
                published_at=published.isoformat() if published else None,
                source=name,
                headline=_base_headline(headline)[:300],
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
                    + (
                        "The targeted feed and a hard change-language gate both matched, so this is a discovery lead awaiting first-party confirmation. "
                        if status == "NEWS SIGNAL"
                        else "An explicit structural-change phrase was present in the item and the context gate passed. "
                    )
                    + "It is a market-change lead, not proof that replacement supply is weak or that the opportunity is profitable."
                ),
                sector=infer_sector(text),
                image_url=_entry_image(entry),
            )
            previous = rows.get(candidate.id)
            if previous is None or (candidate.published_at or "") > (previous.published_at or ""):
                rows[candidate.id] = candidate

    candidates = sorted(rows.values(), key=lambda row: row.published_at or row.discovered_at, reverse=True)
    return candidates, WorldScanStats(
        scanned_at=now.isoformat(),
        sources_configured=len(feeds),
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        raw_entries=raw_entries,
        recent_entries=recent_entries,
        structural_matches=structural_matches,
        candidates=len(candidates),
    )


def scan_world(config: Path = Path("config/world_sources.yml"), *, now: datetime | None = None, timeout: float = 15.0) -> list[GapCandidate]:
    return scan_world_with_stats(config, now=now, timeout=timeout)[0]


def save_candidates(path: Path, candidates: Iterable[GapCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(row) for row in candidates], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_candidates(path: Path) -> list[GapCandidate]:
    if not path.exists():
        return []
    return [GapCandidate(**row) for row in json.loads(path.read_text(encoding="utf-8"))]


def save_scan_stats(path: Path, stats: WorldScanStats) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(stats), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_scan_stats(path: Path) -> WorldScanStats | None:
    if not path.exists():
        return None
    return WorldScanStats(**json.loads(path.read_text(encoding="utf-8")))
