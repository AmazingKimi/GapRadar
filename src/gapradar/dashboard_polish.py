from __future__ import annotations

import json
from pathlib import Path

MARKER = "gapradar-polish-v2"

STYLE = r'''
/* gapradar-polish-v2 */
.radar-funnel{margin-top:12px;padding-top:11px;border-top:1px dashed color-mix(in srgb,var(--line) 78%,transparent);color:var(--muted);font-size:10px;line-height:1.55}
.radar-funnel b{color:var(--text);font-weight:700}.radar-funnel .warn{color:#f1b36b}.radar-funnel .ok{color:var(--green)}.radar-funnel .bad{color:#e58c87}
.discovery-slot{padding-bottom:56px!important}.discovery-slot h3{margin-top:60px!important;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.discovery-slot p{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;max-height:4.35em;line-height:1.45}.discovery-slot .bottommeta{bottom:16px!important;white-space:nowrap}.discovery-slot .arrow{bottom:13px!important}
@media(max-width:640px){.radar-funnel{font-size:9px}.discovery-slot h3{margin-top:55px!important}.discovery-slot p{-webkit-line-clamp:2;max-height:3em}}
'''

SCRIPT = r'''
(()=>{
 'use strict';
 const norm=(v)=>String(v||'').toLowerCase().replace(/[’']/g,'').replace(/[^a-z0-9\u4e00-\u9fff]+/g,' ').trim().split(/\s+/).filter(Boolean).slice(0,18).join(' ');
 const grid=document.querySelector('.opps');if(!grid)return;
 const seen=new Set();
 Array.from(grid.querySelectorAll('.opp')).forEach(card=>{
   const key=norm(card.querySelector('h3')?.textContent);
   if(key&&seen.has(key))card.remove();else if(key)seen.add(key);
 });
 const rows=Array.from(document.querySelectorAll('.feed .row'));
 for(const row of rows){
   if(grid.querySelectorAll('.opp').length>=3)break;
   const headline=row.querySelector('.what b')?.textContent?.trim()||'';
   const key=norm(headline);if(!key||seen.has(key))continue;
   seen.add(key);
   const zh=row.querySelector('.company .lang-zh')?.textContent?.trim()||'全球变化';
   const en=row.querySelector('.company .lang-en')?.textContent?.trim()||'World Change';
   const href=row.querySelector('.round')?.getAttribute('href')||'#';
   const card=document.createElement('article');card.className='opp discovery-slot';
   card.innerHTML='<div class="oppArt"><svg viewBox="0 0 500 260"><rect width="500" height="260" fill="#173148"/><path d="M0 184 96 118l68 42 81-72 92 57 163-101v216H0Z" fill="#214563"/></svg></div><span class="badge"><span class="lang-zh">'+zh+'</span><span class="lang-en">'+en+'</span></span><span class="badge status"><span class="lang-zh">Tier-1 未解决</span><span class="lang-en">Tier-1 unresolved</span></span><h3></h3><p><span class="lang-zh">本轮尚未取得可验证的一手证据。可能是未找到官方候选源，也可能是候选官方页面未通过事实核验；因此暂不判定为市场机会。</span><span class="lang-en">This run did not obtain verifiable first-party evidence. The official source may be missing or a candidate page may have failed factual verification, so this is not promoted to an opportunity.</span></p><div class="bottommeta"><span class="lang-zh">发现线索</span><span class="lang-en">Discovery lead</span></div><a class="arrow" target="_blank" rel="noopener noreferrer">→</a>';
   card.querySelector('h3').textContent=headline;card.querySelector('.arrow').href=href;grid.appendChild(card);
 }
})();
'''


def _read_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def patch(path: Path = Path("docs/index.html")) -> None:
    html = path.read_text(encoding="utf-8")
    if MARKER in html:
        return

    scan = _read_json(Path("data/world-scan-stats.json"), {})
    quality = _read_json(Path("data/world-quality-report.json"), {})
    verification = _read_json(Path("data/world-verification-metrics.json"), {})
    cadence = _read_json(Path("data/commercial-cadence.json"), {})

    raw = int(scan.get("raw_entries", 0))
    structural = int(quality.get("input_candidates", scan.get("candidates", 0)))
    kept = int(quality.get("kept_candidates", structural))
    rejected = int(quality.get("context_rejected", 0))
    collapsed = int(quality.get("duplicate_collapsed", 0))
    verified = int(verification.get("tier1_verified", 0))
    official_found = int(verification.get("first_party_candidate_found", 0))
    no_official = int(verification.get("no_first_party_candidate", 0))
    verification_failed = int(verification.get("verification_failed", 0))
    search_failed = int(verification.get("search_failed", 0))
    avg_hours = float(verification.get("average_awaiting_hours", 0.0))
    oldest_hours = float(verification.get("oldest_awaiting_hours", 0.0))
    candidate_yield = float(verification.get("first_party_candidate_yield", 0.0)) * 100
    tier1_yield = float(verification.get("tier1_verification_yield", 0.0)) * 100

    summary = cadence.get("summary") or {}
    observed_days = int(summary.get("days_observed", 0))
    reviews = int(summary.get("review_opportunities_total", 0))
    review_days = int(summary.get("days_with_review", 0))

    zh = (
        f"信号漏斗：<b>{raw}</b> 条扫描 → <b>{structural}</b> 条结构性候选 → <b>{kept}</b> 条质量过滤后保留 "
        f"（剔除 {rejected}，合并重复 {collapsed}）→ <b class='ok'>{verified}</b> 条 Tier-1 已验证。"
        f"官方候选源命中 <b>{official_found}</b> 条（{candidate_yield:.0f}%）；<b class='bad'>{no_official}</b> 条未找到官方候选源，"
        f"<b class='warn'>{verification_failed}</b> 条候选源核验失败，搜索失败 {search_failed} 条。"
        f"未解决线索平均存在 {avg_hours:.1f}h，最长 {oldest_hours:.1f}h；Tier-1 通过率 {tier1_yield:.0f}%。"
    )
    en = (
        f"Signal funnel: <b>{raw}</b> scanned → <b>{structural}</b> structural candidates → <b>{kept}</b> after quality guard "
        f"({rejected} rejected, {collapsed} duplicates collapsed) → <b class='ok'>{verified}</b> Tier-1 verified. "
        f"Official-source candidates found for <b>{official_found}</b> ({candidate_yield:.0f}%); <b class='bad'>{no_official}</b> had no official candidate, "
        f"<b class='warn'>{verification_failed}</b> had candidate pages that failed verification, {search_failed} searches failed. "
        f"Unresolved leads average {avg_hours:.1f}h, oldest {oldest_hours:.1f}h; Tier-1 yield {tier1_yield:.0f}%."
    )
    if observed_days:
        zh += f" 商业产出基线：已观察 <b>{observed_days}</b> 天，共产出 <b>{reviews}</b> 条 REVIEW，<b>{review_days}</b> 天至少有 1 条。"
        en += f" Commercial cadence: <b>{observed_days}</b> observed day(s), <b>{reviews}</b> REVIEW opportunities total, with at least one on <b>{review_days}</b> day(s)."

    funnel = f'<div class="radar-funnel"><span class="lang-zh">{zh}</span><span class="lang-en">{en}</span></div>'
    anchor = '</div></div></section><section class="section" id="sectors">'
    if anchor in html:
        html = html.replace(anchor, f'</div>{funnel}</div></section><section class="section" id="sectors">', 1)

    # Strip older polish layer before adding the current one when an already-exported
    # page is patched locally.
    html = html.replace('gapradar-polish-v1', 'gapradar-polish-legacy')
    html = html.replace('</body></html>', f'<!-- {MARKER} --><style>{STYLE}</style><script>{SCRIPT}</script></body></html>')
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch()
