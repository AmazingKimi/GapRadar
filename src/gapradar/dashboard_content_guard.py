from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from .worldscan import load_candidates
from .worldverify import load_verifications

WHAT_RE = re.compile(
    r'(<div class="what"><b>.*?</b>)<span>.*?</span>(</div>)',
    flags=re.S,
)

CHANGE_ZH = {
    "shutdown_eol": "停服 / 退役",
    "price_shock": "价格变化",
    "api_terms_change": "API / 条款变化",
    "regulatory_shift": "监管 / 强制要求",
}
CHANGE_EN = {
    "shutdown_eol": "shutdown / end-of-life",
    "price_shock": "price change",
    "api_terms_change": "API / terms change",
    "regulatory_shift": "regulatory requirement",
}


def _host(url: str | None) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.")


def _note(candidate, verification) -> tuple[str, str]:
    signal = (candidate.matched_signal or candidate.change_type).strip().rstrip(".")[:88]
    zh_type = CHANGE_ZH.get(candidate.change_type, "结构变化")
    en_type = CHANGE_EN.get(candidate.change_type, "structural change")
    if verification and verification.status == "tier1_verified" and verification.official_url:
        host = _host(verification.official_url) or "official source"
        zh = f"{zh_type} · 已由 {host} 完成 Tier-1 一手确认 · 命中信号：“{signal}”"
        en = f"{en_type} · Tier-1 confirmed by {host} · matched signal: “{signal}”"
    else:
        source = candidate.source.replace("Google News · ", "")[:48]
        zh = f"{zh_type} · 发现源：{source} · 命中信号：“{signal}” · Tier-1 待确认"
        en = f"{en_type} · discovered via {source} · matched signal: “{signal}” · Tier-1 pending"
    return zh, en


def patch(
    path: Path = Path("docs/index.html"),
    candidates_path: Path = Path("data/world-gaps.json"),
    verification_path: Path = Path("data/world-verifications.json"),
) -> int:
    html = path.read_text(encoding="utf-8")
    candidates = load_candidates(candidates_path)[:10]
    verifications = load_verifications(verification_path)
    index = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal index
        if index >= len(candidates):
            return match.group(0)
        candidate = candidates[index]
        index += 1
        zh, en = _note(candidate, verifications.get(candidate.id))
        return (
            match.group(1)
            + '<span><span class="lang-zh">'
            + escape(zh)
            + '</span><span class="lang-en">'
            + escape(en)
            + '</span></span>'
            + match.group(2)
        )

    html, count = WHAT_RE.subn(repl, html)
    path.write_text(html, encoding="utf-8")
    return count


if __name__ == "__main__":
    count = patch()
    print(f"Dashboard content guard: wrote {count} event-specific Global Feed description(s).")
