from __future__ import annotations

import json
from pathlib import Path

MARKER = "gapradar-polish-v1"

STYLE = r'''
/* gapradar-polish-v1 */
.radar-funnel{margin-top:12px;padding-top:11px;border-top:1px dashed color-mix(in srgb,var(--line) 78%,transparent);color:var(--muted);font-size:10px;line-height:1.55}
.radar-funnel b{color:var(--text);font-weight:700}.radar-funnel .warn{color:#f1b36b}.radar-funnel .ok{color:var(--green)}
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
   card.innerHTML='<div class="oppArt"><svg viewBox="0 0 500 260"><rect width="500" height="260" fill="#173148"/><path d="M0 184 96 118l68 42 81-72 92 57 163-101v216H0Z" fill="#214563"/></svg></div><span class="badge"><span class="lang-zh">'+zh+'</span><span class="lang-en">'+en+'</span></span><span class="badge status"><span class="lang-zh">待一手证据</span><span class="lang-en">Awaiting Tier-1</span></span><h3></h3><p><span class="lang-zh">发现了结构性变化，但尚未通过 Tier-1 一手来源验证，因此暂不判定为市场机会。</span><span class="lang-en">A structural change was detected, but Tier-1 first-party evidence is not verified yet, so this is not promoted to a market opportunity.</span></p><div class="bottommeta"><span class="lang-zh">发现线索</span><span class="lang-en">Discovery lead</span></div><a class="arrow" target="_blank" rel="noopener noreferrer">→</a>';
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

    raw = int(scan.get("raw_entries", 0))
    structural = int(quality.get("input_candidates", scan.get("candidates", 0)))
    kept = int(quality.get("kept_candidates", structural))
    rejected = int(quality.get("context_rejected", 0))
    collapsed = int(quality.get("duplicate_collapsed", 0))
    verified = int(verification.get("tier1_verified", 0))
    awaiting = int(verification.get("awaiting_tier1", max(kept - verified, 0)))
    avg_hours = float(verification.get("average_awaiting_hours", 0.0))
    oldest_hours = float(verification.get("oldest_awaiting_hours", 0.0))

    zh = (
        f"信号漏斗：<b>{raw}</b> 条扫描 → <b>{structural}</b> 条结构性候选 → <b>{kept}</b> 条质量过滤后保留 "
        f"（剔除 {rejected}，合并重复 {collapsed}）→ <b class='ok'>{verified}</b> 条 Tier-1 已验证 · "
        f"<b class='warn'>{awaiting}</b> 条等待验证；平均等待 {avg_hours:.1f}h，最长 {oldest_hours:.1f}h。"
    )
    en = (
        f"Signal funnel: <b>{raw}</b> scanned → <b>{structural}</b> structural candidates → <b>{kept}</b> after quality guard "
        f"({rejected} rejected, {collapsed} duplicates collapsed) → <b class='ok'>{verified}</b> Tier-1 verified · "
        f"<b class='warn'>{awaiting}</b> awaiting; avg pending {avg_hours:.1f}h, oldest {oldest_hours:.1f}h."
    )
    funnel = f'<div class="radar-funnel"><span class="lang-zh">{zh}</span><span class="lang-en">{en}</span></div>'
    anchor = '</div></div></section><section class="section" id="sectors">'
    if anchor in html:
        html = html.replace(anchor, f'</div>{funnel}</div></section><section class="section" id="sectors">', 1)

    html = html.replace('</body></html>', f'<!-- {MARKER} --><style>{STYLE}</style><script>{SCRIPT}</script></body></html>')
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch()
