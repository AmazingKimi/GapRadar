from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from .priority import PriorityLead, load_priority_leads
from .worlddeep import load_assessments
from .worldscan import GapCandidate, load_candidates

SECTOR_ZH = {
    "AI & Technology": "科技与 AI",
    "Energy & Climate": "能源与气候",
    "Healthcare & Biotech": "医疗与生物",
    "Finance & Fintech": "金融与支付",
    "Mobility": "出行与交通",
    "Industry & Robotics": "工业与机器人",
    "Consumer & Society": "消费 / 社会",
    "Frontier": "太空 / 前沿",
}

GRID_RE = re.compile(r'(<div class="opps">).*?(</div></section><section class="section" id="feed">)', re.S)
STATS_RE = re.compile(r'(<div class="stats">.*?<div><b>)(\d+)(</b><span>[^<]*</span></div></div>)', re.S)


def _host(url: str | None) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.")


def _art(kind: str) -> str:
    if kind == "price_shock":
        return '<svg viewBox="0 0 500 260"><rect width="500" height="260" fill="#173148"/><path d="M0 205 92 171l83-47 84 35 96-84 145 56v129H0Z" fill="#214b6a"/></svg>'
    if kind == "shutdown_eol":
        return '<svg viewBox="0 0 500 260"><rect width="500" height="260" fill="#182c45"/><circle cx="385" cy="76" r="64" fill="#2b5a8e" opacity=".5"/><path d="M40 190h420" stroke="#6aa6d9" opacity=".35"/></svg>'
    if kind == "regulatory_shift":
        return '<svg viewBox="0 0 500 260"><rect width="500" height="260" fill="#17334a"/><path d="M0 187 92 122l73 41 82-67 89 52 164-101v213H0Z" fill="#234d68"/></svg>'
    return '<svg viewBox="0 0 500 260"><rect width="500" height="260" fill="#163048"/><path d="M0 192 110 132l80 40 92-86 218 91v83H0Z" fill="#24506d"/></svg>'


def _zh_reason(candidate: GapCandidate, row: PriorityLead) -> str:
    signal = (candidate.matched_signal or candidate.change_type).strip().rstrip(".")[:72]
    if row.evidence_state == "tier1_verified":
        host = row.evidence_label.split("·", 1)[-1].strip()
        return f"{host} 已完成 Tier-1 一手确认。当前优先验证这次变化是否真正释放新需求，以及现有供给是否足够覆盖。"
    if row.evidence_state == "official_candidate":
        host = row.evidence_label.split("·", 1)[-1].strip()
        return f"已找到 {host} 的官方候选页面，但尚未确认标题中的具体主张；因出现明确“{signal}”信号，列入优先调查。"
    return f"新闻中出现明确“{signal}”结构变化信号，但尚未找到可接受的一手来源；先列为优先调查，不视为已验证机会。"


def _status_zh(status: str) -> str:
    return {"REVIEW": "重点评估", "INVESTIGATE": "优先调查", "WATCH": "持续观察", "DISMISS": "暂不关注"}.get(status, status)


def _evidence_zh(state: str) -> str:
    return {"tier1_verified": "Tier-1 已验证", "official_candidate": "已找到官方候选", "news_only": "Tier-1 待确认"}.get(state, "证据待确认")


def _card(candidate: GapCandidate, row: PriorityLead) -> str:
    sector = candidate.sector or "Other"
    zh_sector = SECTOR_ZH.get(sector, sector)
    cls = "review" if row.status == "REVIEW" else "watch"
    title = escape(candidate.headline)
    en_reason = escape(row.reason)
    zh_reason = escape(_zh_reason(candidate, row))
    return (
        '<article class="opp priority-card" data-priority-status="' + escape(row.status) + '">'
        '<div class="oppArt">' + _art(candidate.change_type) + '</div>'
        '<span class="badge"><span class="lang-zh">' + escape(zh_sector) + '</span><span class="lang-en">' + escape(sector) + '</span></span>'
        '<span class="badge status ' + cls + '"><span class="lang-zh">' + escape(_status_zh(row.status)) + '</span><span class="lang-en">' + escape(row.status.title()) + '</span></span>'
        '<h3>' + title + '</h3>'
        '<p><span class="lang-zh">' + zh_reason + '</span><span class="lang-en">' + en_reason + '</span></p>'
        '<div class="bottommeta"><span class="lang-zh">' + escape(_evidence_zh(row.evidence_state)) + '</span><span class="lang-en">' + escape(row.evidence_label) + '</span></div>'
        '<a class="arrow" href="' + escape(candidate.url) + '" target="_blank" rel="noopener noreferrer">→</a>'
        '</article>'
    )


def patch(
    path: Path = Path("docs/index.html"),
    priority_path: Path = Path("data/priority-leads.json"),
    candidates_path: Path = Path("data/world-gaps.json"),
) -> int:
    html = path.read_text(encoding="utf-8")
    candidates = {row.id: row for row in load_candidates(candidates_path)}
    priority = [row for row in load_priority_leads(priority_path) if row.status in {"REVIEW", "INVESTIGATE", "WATCH"}]
    chosen = [row for row in priority if row.status in {"REVIEW", "INVESTIGATE"}][:3]
    if len(chosen) < 3:
        used = {row.candidate_id for row in chosen}
        chosen.extend(row for row in priority if row.candidate_id not in used and row.status == "WATCH")
        chosen = chosen[:3]

    cards = "".join(_card(candidates[row.candidate_id], row) for row in chosen if row.candidate_id in candidates)
    if not cards:
        cards = (
            '<article class="opp"><div class="oppArt">' + _art("") + '</div>'
            '<h3><span class="lang-zh">今天没有达到优先调查门槛的线索</span><span class="lang-en">No lead reached today’s investigation threshold</span></h3>'
            '<p><span class="lang-zh">系统继续扫描，但不会用模板内容凑数。</span><span class="lang-en">The radar keeps scanning and will not manufacture filler recommendations.</span></p></article>'
        )

    html, count = GRID_RE.subn(r'\1' + cards + r'\2', html, count=1)

    # The fourth overview stat is now a research-attention recommendation count,
    # not a claim that all of these are verified market gaps.
    priority_count = sum(row.status in {"REVIEW", "INVESTIGATE"} for row in priority)
    stats = list(re.finditer(r'<div><b>\d+</b><span>[^<]*</span></div>', html))
    if len(stats) >= 4:
        target = stats[3]
        old = target.group(0)
        label = '<span><span class="lang-zh">优先调查线索</span><span class="lang-en">Priority leads</span></span>'
        new = re.sub(r'<b>\d+</b>', f'<b>{priority_count}</b>', old)
        new = re.sub(r'<span>[^<]*</span>', label, new, count=1)
        html = html[:target.start()] + new + html[target.end():]

    path.write_text(html, encoding="utf-8")
    return count


if __name__ == "__main__":
    count = patch()
    print(f"Dashboard priority patch: replaced opportunity grid ({count} section patched).")
