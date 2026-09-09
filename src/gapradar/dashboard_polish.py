from __future__ import annotations

import json
from pathlib import Path

MARKER = "gapradar-polish-v4"

STYLE = r'''
/* gapradar-polish-v4 */
.radar-funnel{margin-top:12px;padding-top:11px;border-top:1px dashed color-mix(in srgb,var(--line) 78%,transparent);color:var(--muted);font-size:10px;line-height:1.55}
.radar-funnel b{color:var(--text);font-weight:700}.radar-funnel .ok{color:var(--green)}.radar-funnel .bad{color:#e58c87}
.radar-funnel details{margin-top:7px}.radar-funnel summary{cursor:pointer;color:var(--cyan);list-style:none;width:max-content}.radar-funnel summary::-webkit-details-marker{display:none}.radar-funnel .detail{margin-top:7px;max-width:1080px;opacity:.9}
.decision-flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:10px;align-items:center;margin:18px 0 8px;padding:13px 16px;border:1px solid color-mix(in srgb,var(--line) 80%,transparent);border-radius:14px;background:color-mix(in srgb,var(--panel) 72%,transparent)}
.decision-step strong{display:block;font-size:12px}.decision-step span{display:block;margin-top:3px;font-size:9px;color:var(--muted)}.decision-arrow{color:var(--cyan);font-size:18px}
.sector-trend{display:flex;gap:6px;align-items:center;margin-top:7px;font-size:9px;color:var(--muted)}.sector-trend .delta.up{color:#6ed39b}.sector-trend .delta.down{color:#e7a07e}.sector-trend .signal{padding:2px 6px;border:1px solid color-mix(in srgb,var(--line) 80%,transparent);border-radius:999px}
.feed .row{min-height:55px!important;transition:background .15s ease}.feed .row:hover{background:color-mix(in srgb,var(--panel2) 86%,transparent)!important}.feed .what b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.feed-tags{display:flex!important;gap:5px!important;flex-wrap:nowrap!important;overflow:hidden!important;margin-top:4px!important}.feed-tag{display:inline-block;padding:2px 6px;border:1px solid color-mix(in srgb,var(--line) 74%,transparent);border-radius:999px;font-size:8px;line-height:1.3;white-space:nowrap;color:var(--muted)}
.app:after{content:"";position:fixed;left:230px;right:0;top:48%;bottom:0;pointer-events:none;z-index:0;background:linear-gradient(to bottom,transparent,rgba(2,12,22,.18) 35%,rgba(2,12,22,.45))}.content{position:relative;z-index:1}html[data-theme="light"] .app:after{background:linear-gradient(to bottom,transparent,rgba(238,245,251,.22) 35%,rgba(238,245,251,.58))}
@media(max-width:860px){.app:after{left:0}.decision-flow{grid-template-columns:1fr;gap:7px}.decision-arrow{transform:rotate(90deg);justify-self:center}.sector-trend{flex-wrap:wrap}}
'''

SCRIPT_TEMPLATE = r'''
(()=>{
 'use strict';
 const trends=__TRENDS__;
 const typeLabels={
  shutdown_eol:['停服/EOL','Shutdown/EOL'],price_shock:['价格','Pricing'],api_terms_change:['API/条款','API/Terms'],regulatory_shift:['监管','Regulation']
 };
 document.querySelectorAll('.sector').forEach(card=>{
   const text=card.textContent||'';let key=null;
   Object.keys(trends).some(k=>{if(text.includes(k)){key=k;return true}return false});
   if(!key)return;const row=trends[key];
   const wrap=document.createElement('div');wrap.className='sector-trend';
   let d='';if(row.delta!==null&&row.delta!==undefined){const cls=row.delta>0?'up':row.delta<0?'down':'';const arrow=row.delta>0?'↑':row.delta<0?'↓':'→';d='<span class="delta '+cls+'">'+arrow+' '+Math.abs(row.delta)+'</span>'}
   const labs=typeLabels[row.dominant_change_type]||['结构变化','Structural'];
   wrap.innerHTML=d+'<span class="signal"><span class="lang-zh">'+labs[0]+'</span><span class="lang-en">'+labs[1]+'</span></span>';
   card.appendChild(wrap);
 });
 document.querySelectorAll('.feed .what > .lang-en,.feed .what > .lang-zh').forEach(el=>{
   if(el.dataset.tagged)return;el.dataset.tagged='1';const raw=el.textContent.trim();if(!raw)return;el.title=raw;
   const parts=raw.split(/\s+·\s+/).filter(Boolean);if(parts.length<2)return;
   el.textContent='';el.classList.add('feed-tags');parts.slice(0,3).forEach(p=>{const s=document.createElement('span');s.className='feed-tag';s.textContent=p;el.appendChild(s)});
 });
})();
'''


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def patch(path: Path = Path("docs/index.html")) -> None:
    html = path.read_text(encoding="utf-8")
    if MARKER in html:
        return

    scan = _read(Path("data/world-scan-stats.json"), {})
    quality = _read(Path("data/world-quality-report.json"), {})
    verification = _read(Path("data/world-verification-metrics.json"), {})
    cadence = _read(Path("data/commercial-cadence.json"), {})
    trend_payload = _read(Path("data/sector-trends.json"), {})
    trends = trend_payload.get("sectors") or {}

    raw = int(scan.get("raw_entries", 0))
    structural = int(quality.get("input_candidates", scan.get("candidates", 0)))
    kept = int(quality.get("kept_candidates", structural))
    verified = int(verification.get("tier1_verified", 0))
    summary = cadence.get("summary") or {}
    priority_total = int(summary.get("priority_leads_total", 0))
    reviews = int(summary.get("review_opportunities_total", 0))

    short_zh = f"<b>{raw}</b> 扫描 → <b>{kept}</b> 高质量变化 → <b class='ok'>{priority_total}</b> 优先线索 → <b>{reviews}</b> REVIEW"
    short_en = f"<b>{raw}</b> scanned → <b>{kept}</b> quality changes → <b class='ok'>{priority_total}</b> priority leads → <b>{reviews}</b> REVIEW"
    details_zh = (
        f"原始结构性候选 {structural} 条；Tier-1 已验证 {verified} 条。"
        f"质量过滤剔除 {int(quality.get('context_rejected',0))} 条，语义去重合并 {int(quality.get('duplicate_collapsed',0))} 条。"
        f"当前仍有 {int(verification.get('no_first_party_candidate',0))} 条没有找到官方候选源，"
        f"{int(verification.get('verification_failed',0))} 条官方候选页未通过具体主张核验。"
    )
    details_en = (
        f"{structural} structural candidates entered quality review; {verified} are Tier-1 verified. "
        f"The guard rejected {int(quality.get('context_rejected',0))} contextual false positives and collapsed {int(quality.get('duplicate_collapsed',0))} semantic duplicate(s). "
        f"{int(verification.get('no_first_party_candidate',0))} still have no acceptable official-source candidate; "
        f"{int(verification.get('verification_failed',0))} candidate page(s) failed claim verification."
    )
    funnel = (
        '<div class="radar-funnel"><span class="lang-zh">'+short_zh+'</span><span class="lang-en">'+short_en+'</span>'
        '<details><summary><span class="lang-zh">查看证据漏斗详情 ↓</span><span class="lang-en">Evidence funnel details ↓</span></summary>'
        '<div class="detail"><span class="lang-zh">'+details_zh+'</span><span class="lang-en">'+details_en+'</span></div></details></div>'
    )
    flow = '''<div class="decision-flow">
      <div class="decision-step"><strong><span class="lang-zh">世界变化</span><span class="lang-en">World Change</span></strong><span><span class="lang-zh">发现真实结构变化</span><span class="lang-en">Detect structural change</span></span></div><div class="decision-arrow">→</div>
      <div class="decision-step"><strong><span class="lang-zh">优先线索</span><span class="lang-en">Priority Lead</span></strong><span><span class="lang-zh">决定今天先查什么</span><span class="lang-en">Allocate research attention</span></span></div><div class="decision-arrow">→</div>
      <div class="decision-step"><strong><span class="lang-zh">缺口验证</span><span class="lang-en">Gap Validation</span></strong><span><span class="lang-zh">Tier-1 + Demand + Supply</span><span class="lang-en">Tier-1 + Demand + Supply</span></span></div>
    </div>'''

    anchor = '</div></div></section><section class="section" id="sectors">'
    if anchor in html:
        html = html.replace(anchor, f'</div>{funnel}</div></section>{flow}<section class="section" id="sectors">', 1)

    # Permanently disable historical filler-card code even if an old runtime survives export.
    html = html.replace('ensureOpportunityCards();', '/* no filler priority cards */')
    html = html.replace('gapradar-polish-v1', 'gapradar-polish-legacy').replace('gapradar-polish-v2', 'gapradar-polish-legacy').replace('gapradar-polish-v3', 'gapradar-polish-legacy')
    script = SCRIPT_TEMPLATE.replace('__TRENDS__', json.dumps(trends, ensure_ascii=False))
    html = html.replace('</body></html>', f'<!-- {MARKER} --><style>{STYLE}</style><script>{script}</script></body></html>')
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch()
