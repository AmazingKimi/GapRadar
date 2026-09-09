from __future__ import annotations

import json
from pathlib import Path

MARKER = "gapradar-dossier-v1"

STYLE = r'''
/* gapradar-dossier-v1 */
.lead-drawer-mask{position:fixed;inset:0;background:rgba(1,8,15,.62);z-index:200;opacity:0;pointer-events:none;transition:opacity .2s}.lead-drawer-mask.open{opacity:1;pointer-events:auto}
.lead-drawer{position:fixed;top:0;right:0;width:min(560px,94vw);height:100vh;z-index:201;background:var(--panel);border-left:1px solid var(--line);transform:translateX(100%);transition:transform .24s;overflow:auto;padding:28px 30px 42px;box-sizing:border-box}.lead-drawer.open{transform:translateX(0)}
.lead-drawer .close{position:absolute;right:18px;top:18px;width:34px;height:34px;border-radius:50%;border:1px solid var(--line);background:transparent;color:var(--text);cursor:pointer}.lead-drawer h2{font-size:24px;line-height:1.25;margin:18px 40px 8px 0}.lead-drawer .meta{font-size:11px;color:var(--cyan);margin-bottom:18px}.lead-drawer .section{margin-top:20px}.lead-drawer .label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}.lead-drawer .body{font-size:13px;line-height:1.65;color:var(--text)}.lead-drawer .box{padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel2)}.lead-drawer a.source{display:inline-block;margin-top:22px;padding:10px 16px;border-radius:999px;background:var(--text);color:var(--bg);text-decoration:none;font-weight:700;font-size:12px}
'''

SCRIPT = r'''
(()=>{
 'use strict';
 const data=JSON.parse(document.getElementById('gapradar-dossier-data')?.textContent||'{}');
 const mask=document.createElement('div');mask.className='lead-drawer-mask';
 const drawer=document.createElement('aside');drawer.className='lead-drawer';drawer.innerHTML='<button class="close">×</button><div class="inner"></div>';
 document.body.append(mask,drawer);const inner=drawer.querySelector('.inner');
 const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
 function section(label,body,box=false){if(!body)return'';return '<div class="section"><div class="label">'+esc(label)+'</div><div class="body '+(box?'box':'')+'">'+esc(body)+'</div></div>'}
 function open(id){const d=data[id];if(!d)return;inner.innerHTML='<div class="meta">'+esc(d.status)+' · '+esc(d.evidence_label)+'</div><h2>'+esc(d.headline)+'</h2>'+section('What changed',d.summary||d.matched_signal)+section('Why it matters',d.reason)+section('Demand hypothesis',d.demand_hypothesis,true)+section('Supply check',d.supply_summary,true)+section('Current gap judgment',d.gap_summary)+section('Next verification step',d.next_check,true)+(d.source_url?'<a class="source" target="_blank" rel="noopener noreferrer" href="'+esc(d.source_url)+'">Open source ↗</a>':'');mask.classList.add('open');drawer.classList.add('open')}
 function close(){mask.classList.remove('open');drawer.classList.remove('open')}
 drawer.querySelector('.close').onclick=close;mask.onclick=close;document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
 document.querySelectorAll('.priority-card[data-candidate-id]').forEach(card=>{const id=card.dataset.candidateId;card.addEventListener('click',e=>{if(e.target.closest('a'))return;open(id)});card.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&!e.target.closest('a')){e.preventDefault();open(id)}})});
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
    candidates = {row["id"]: row for row in _read(Path("data/world-gaps.json"), [])}
    priority = {row["candidate_id"]: row for row in _read(Path("data/priority-leads.json"), [])}
    verification = {row["candidate_id"]: row for row in _read(Path("data/world-verifications.json"), [])}
    assessments = {row["candidate_id"]: row for row in _read(Path("data/world-assessments.json"), [])}
    payload = {}
    for cid, row in priority.items():
        if row.get("status") not in {"REVIEW", "INVESTIGATE", "WATCH"} or cid not in candidates:
            continue
        c = candidates[cid]; v = verification.get(cid) or {}; a = assessments.get(cid) or {}
        demand = a.get("demand_hypothesis") or {}
        if isinstance(demand, dict):
            demand_text = " · ".join(str(demand.get(k) or "") for k in ("affected_users","job_to_be_done","disruption","basis") if demand.get(k))
        else:
            demand_text = str(demand or "")
        supply_summary = ""
        if a:
            supply_summary = f"Coverage: {a.get('supply_coverage','unknown')} · candidates checked: {a.get('supply_candidate_count',0)} · strong evidence: {len(a.get('supply_evidence') or [])}"
        payload[cid] = {
            "headline": c.get("headline"), "summary": c.get("summary"), "matched_signal": c.get("matched_signal"),
            "status": row.get("status"), "evidence_label": row.get("evidence_label"), "reason": row.get("reason"), "next_check": row.get("next_check"),
            "demand_hypothesis": demand_text, "supply_summary": supply_summary,
            "gap_summary": a.get("recommendation_summary") or a.get("gap_assessment") or ("Evidence chain is still incomplete; this remains a research lead." if row.get("status") != "REVIEW" else "Market-gap evidence chain completed."),
            "source_url": v.get("official_url") or c.get("url"),
        }
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace('</body></html>', f'<!-- {MARKER} --><style>{STYLE}</style><script type="application/json" id="gapradar-dossier-data">{blob}</script><script>{SCRIPT}</script></body></html>')
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    patch()
