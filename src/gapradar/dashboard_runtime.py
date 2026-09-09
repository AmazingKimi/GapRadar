from __future__ import annotations

import re
from pathlib import Path

STYLE = r'''
/* gapradar-runtime-v6 */
.content{max-width:none!important;width:calc(100vw - 230px)!important;margin-left:230px!important;padding:16px clamp(28px,2.2vw,52px) 48px!important}
.hero{grid-template-columns:minmax(430px,1.12fr) minmax(430px,.88fr)!important;gap:clamp(38px,4vw,76px)!important}
.overview{width:100%}.sectors{grid-template-columns:repeat(auto-fit,minmax(165px,1fr))!important}.opps{grid-template-columns:repeat(3,minmax(280px,1fr))!important}
.more,.filters span,.sector,.control,.nav a,.btn,.arrow,.round{cursor:pointer}.more:hover,.filters span:hover{filter:brightness(1.35)}.sector{transition:transform .16s ease,border-color .16s ease}.sector:hover{transform:translateY(-2px);border-color:#3d7099}.sector.selected{border-color:var(--cyan);box-shadow:0 0 0 1px color-mix(in srgb,var(--cyan) 30%,transparent)}
.filters span.active{color:var(--text);font-weight:750}.saved-on{color:#7bdca3!important}.opp[hidden],.row[hidden]{display:none!important}
.discovery-slot .status{background:#3b4754;border-color:#617182;color:#d9e6f2}.discovery-slot p{max-width:92%}
.globe{left:30%!important;top:-48px!important;width:min(540px,38vw)!important;height:320px!important;opacity:.62!important}.globe svg{overflow:visible}
.control{min-width:88px!important;justify-content:center!important;font-weight:700!important;transition:.16s ease!important}.control:hover{border-color:var(--cyan)!important}.control.is-active{background:rgba(70,142,215,.18)!important;border-color:#3974a8!important}
html[data-lang="en"] .lang-zh{display:none!important}html[data-lang="en"] .lang-en{display:inline!important}html[data-lang="zh"] .lang-en{display:none!important}html[data-lang="zh"] .lang-zh{display:inline!important}
html[data-theme="light"]{color-scheme:light;--bg:#eef5fb!important;--bg2:#e6f0f7!important;--side:#f7fbff!important;--panel:#fff!important;--panel2:#f7fbff!important;--line:#c8d9e7!important;--text:#0d1b28!important;--muted:#60778b!important;--blue:#2a72d6!important;--cyan:#168fc5!important;--green:#258b5b!important;--shadow:0 14px 38px rgba(30,64,95,.12)!important}
html[data-theme="light"] body{background:#eef5fb!important;color:#0d1b28!important}html[data-theme="light"] .app{background:radial-gradient(circle at 61% 4%,rgba(90,157,221,.18),transparent 30%),linear-gradient(135deg,#edf5fb,#f8fbfe 73%)!important}html[data-theme="light"] .sidebar{background:#f7fbff!important}html[data-theme="light"] .nav a{color:#294259!important}html[data-theme="light"] .nav a.active{color:#0d1b28!important;background:#dceafb!important;border-color:#a9c8e5!important}html[data-theme="light"] .overview,html[data-theme="light"] .sector,html[data-theme="light"] .feed,html[data-theme="light"] .row{background:#fff!important;color:#0d1b28!important;border-color:#c8d9e7!important}html[data-theme="light"] .badge{background:#e5f2ff!important;color:#245b86!important}html[data-theme="light"] .opp{background:#fff!important;border-color:#bfd2e2!important;color:#0d1b28!important}
@media(min-width:1600px){.hero h1{font-size:54px}.opps{gap:16px!important}}
@media(min-width:2100px){.content{padding-left:56px!important;padding-right:56px!important}.hero{grid-template-columns:minmax(560px,1.18fr) minmax(520px,.82fr)!important}.sectors{grid-template-columns:repeat(7,minmax(0,1fr))!important}.opp{height:285px!important}}
@media(max-width:1200px){.hero{grid-template-columns:1fr!important}.globe{left:45%!important;opacity:.35!important}.opps{grid-template-columns:repeat(2,1fr)!important}.topline{flex-wrap:wrap!important;height:auto!important}.head,.feedtop{gap:12px!important}}
@media(max-width:860px){.sidebar{display:none!important}.content{width:100%!important;margin-left:0!important;padding:18px 18px 36px!important}.hero{grid-template-columns:1fr!important;gap:18px!important}.globe{left:auto!important;right:-90px!important;top:6px!important;width:390px!important;height:230px!important;opacity:.18!important}.opps{grid-template-columns:1fr!important}.topline{justify-content:flex-start!important;gap:6px!important}.pill,.control{height:30px!important}.head,.feedtop{align-items:flex-start!important;flex-wrap:wrap!important}.row{grid-template-columns:minmax(120px,160px) minmax(0,1fr) 84px 30px!important}.more{white-space:nowrap!important}}
@media(max-width:640px){.content{padding:14px 14px 30px!important}.topline{display:grid!important;grid-template-columns:1fr 1fr!important;gap:7px!important}.pill,.control{width:100%!important;min-width:0!important;justify-content:center!important;font-size:10px!important;padding:0 7px!important;overflow:hidden!important;white-space:nowrap!important}.hero{min-height:0!important;padding-top:8px!important}.hero h1{font-size:clamp(34px,10vw,44px)!important;line-height:1.05!important}.hero p{font-size:14px!important;line-height:1.55!important}.actions{display:grid!important;grid-template-columns:1fr!important;gap:8px!important}.btn{width:100%!important}.overview{padding:16px!important}.stats{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:14px!important}.stats b{font-size:25px!important}.stats span{font-size:10px!important}.section{margin-top:20px!important}.headleft{display:block!important}.head h2,.feedtop h2{font-size:20px!important}.head p,.feedtop p{margin-top:3px!important}.more{display:none!important}.sectors{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important}.sector{height:108px!important;padding:12px!important}.sectorIcon{width:35px!important;height:35px!important}.sector strong{font-size:12px!important}.bars{left:52px!important}.opp{height:245px!important;padding:15px!important}.opp h3{font-size:18px!important;margin-top:68px!important}.filters{width:100%!important;overflow-x:auto!important;gap:8px!important;padding-bottom:2px!important;white-space:nowrap!important}.feed{overflow:hidden!important}.row{grid-template-columns:minmax(0,1fr) 28px!important;gap:8px!important;padding:11px 12px!important}.row .company{grid-column:1!important}.row .what{grid-column:1!important}.row .time{display:none!important}.row .round{grid-column:2!important;grid-row:1 / span 2!important;align-self:center!important}.what b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.what span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.footer{line-height:1.6!important}}
@media(max-width:420px){.content{padding-left:12px!important;padding-right:12px!important}.topline{grid-template-columns:1fr!important}.hero h1{font-size:34px!important}.sectors{grid-template-columns:1fr 1fr!important}.sector{min-width:0!important}.badge{font-size:9px!important;padding:4px 7px!important}.opp h3{font-size:17px!important}}
'''

SCRIPT = r'''
(()=>{
 'use strict';
 const root=document.documentElement;
 const $=(s)=>document.querySelector(s), $$=(s)=>Array.from(document.querySelectorAll(s));
 const COPY={
  zh:{hero1:'从世界的变化',hero2:'发现下一个机会',heroP:'我们持续扫描全球的政策、公司动态、技术进展和市场变化，帮你发现可能被忽视的市场缺口。',today:'查看今日机会　→',browse:'浏览行业雷达',changing:'全球正在发生变化',changingP:'我们为你持续监测，并寻找值得关注的机会。',sector:'行业雷达',sectorP:'哪些领域今天变化最活跃？',opp:'今日推荐机会',oppP:'基于最新变化，我们认为以下机会最值得关注。',feed:'全球重要变化',feedP:'今天发现的其他值得了解的变化。',allSector:'查看全部行业　→',allOpp:'查看全部机会　→',stats:['今日扫描资讯','关键变化事件','深入分析','值得关注机会'],filters:['全部','科技','能源','监管','消费'],footer:'每 6 小时自动扫描一次 · 推荐代表研究价值，不构成投资建议。',updated:'最后更新',next:'下次更新',market:'企业市场',watch:'持续观察',early:'早期机会',unverified:'待一手证据',lead:'发现线索',leadNote:'发现了结构性变化，但尚未通过 Tier-1 一手来源验证，因此暂不判定为市场机会。'},
  en:{hero1:'See what is changing',hero2:'Find the next opportunity',heroP:'We continuously scan policy, company, technology and market shifts worldwide to uncover market gaps others may miss.',today:'View today’s opportunities　→',browse:'Browse sector radar',changing:'The world is changing',changingP:'We continuously monitor those changes and look for opportunities worth your attention.',sector:'Sector Radar',sectorP:'Which sectors are moving most today?',opp:'Today’s Opportunities',oppP:'The opportunities most worth watching based on the latest changes.',feed:'Important Global Changes',feedP:'Other changes worth knowing about today.',allSector:'View all sectors　→',allOpp:'View all opportunities　→',stats:['Items scanned today','Key change events','Deep analyses','Opportunities to watch'],filters:['All','Tech','Energy','Regulation','Consumer'],footer:'Automatic scan every 6 hours · Recommendations indicate research value, not investment advice.',updated:'Last updated',next:'Next update',market:'Business market',watch:'Watch',early:'Early opportunity',unverified:'Awaiting Tier-1',lead:'Discovery lead',leadNote:'A structural change was detected, but Tier-1 first-party evidence is not verified yet, so this is not promoted to a market opportunity.'}
 };
 function text(el,v){if(el&&v!=null)el.textContent=v}
 function esc(v){return String(v||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
 function rawPill(p){if(!p)return'';if(!p.dataset.raw){p.dataset.raw=p.textContent.replace(/^(最后更新|下次更新|Last updated|Next update|●\s*最后更新|●\s*下次更新|●\s*Last updated|●\s*Next update)\s*/,'')}return p.dataset.raw}
 function ensureOpportunityCards(){
  const grid=$('.opps');if(!grid)return;
  let cards=$$('.opps .opp');
  if(cards.length===1&&/今天没有足够证据支持/.test(cards[0].textContent))grid.innerHTML='';
  cards=$$('.opps .opp');
  const rows=$$('.feed .row');
  for(let i=cards.length;i<3;i++){
   const row=rows[i]||rows[0];if(!row)break;
   const sectorEn=row.querySelector('.company .lang-en')?.textContent.trim()||'World Change';
   const sectorZh=row.querySelector('.company .lang-zh')?.textContent.trim()||'全球变化';
   const headline=row.querySelector('.what b')?.textContent.trim()||'Market change under review';
   const href=row.querySelector('.round')?.getAttribute('href')||'#';
   const article=document.createElement('article');
   article.className='opp discovery-slot';
   article.innerHTML='<div class="oppArt"><svg viewBox="0 0 500 260"><rect width="500" height="260" fill="#173148"/><path d="M0 184 96 118l68 42 81-72 92 57 163-101v216H0Z" fill="#214563"/></svg></div><span class="badge"><span class="lang-zh">'+esc(sectorZh)+'</span><span class="lang-en">'+esc(sectorEn)+'</span></span><span class="badge status"><span class="lang-zh">待一手证据</span><span class="lang-en">Awaiting Tier-1</span></span><h3>'+esc(headline)+'</h3><p><span class="lang-zh">发现了结构性变化，但尚未通过 Tier-1 一手来源验证，因此暂不判定为市场机会。</span><span class="lang-en">A structural change was detected, but Tier-1 first-party evidence is not verified yet, so this is not promoted to a market opportunity.</span></p><div class="bottommeta"><span class="lang-zh">发现线索</span><span class="lang-en">Discovery lead</span></div><a class="arrow" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">→</a>';
   grid.appendChild(article);
  }
 }
 function applyLanguage(lang){
  lang=lang==='en'?'en':'zh';const d=COPY[lang];root.dataset.lang=lang;root.setAttribute('lang',lang==='en'?'en':'zh-CN');localStorage.setItem('gapradar-lang',lang);
  const h=$('.hero h1');if(h)h.innerHTML=d.hero1+'<br><span class="grad">'+d.hero2+'</span>';
  text($('.hero-copy p'),d.heroP);const buttons=$$('.hero .btn');text(buttons[0],d.today);text(buttons[1],d.browse);
  text($('.overview h2'),d.changing);text($('.overview p'),d.changingP);$$('.stats span').forEach((el,i)=>text(el,d.stats[i]));
  const heads=$$('.section .head');if(heads[0]){text(heads[0].querySelector('h2'),d.sector);text(heads[0].querySelector('p'),d.sectorP);text(heads[0].querySelector('.more'),d.allSector)}if(heads[1]){text(heads[1].querySelector('h2'),d.opp);text(heads[1].querySelector('p'),d.oppP);text(heads[1].querySelector('.more'),d.allOpp)}
  const fh=$('#feed .feedtop');if(fh){text(fh.querySelector('h2'),d.feed);text(fh.querySelector('p'),d.feedP)}
  const filters=$$('.filters>*');d.filters.forEach((v,i)=>{if(filters[i]){let count='';if(i===0){const m=filters[i].textContent.match(/\d+/);count=m?' '+m[0]:''}text(filters[i],v+count)}});
  $$('.bottommeta:not(.discovery-slot .bottommeta)').forEach(el=>{const early=/早期|Early/i.test(el.textContent);text(el,d.market+'　◷ '+(early?d.early:d.watch))});
  const foot=$('.footer');if(foot)text(foot,'GapRadar by AMAZING KIMI · '+d.footer);
  const pills=$$('.topline .pill');if(pills[0])text(pills[0],d.updated+' '+rawPill(pills[0]));if(pills[1])text(pills[1],'● '+d.next+' '+rawPill(pills[1]).replace(/^●\s*/,''));
  const l=$('#langToggle');if(l){text(l,lang==='zh'?'中文 ✓  |  EN':'中文  |  EN ✓');l.classList.add('is-active')}
  syncTheme();
 }
 function syncTheme(){const t=$('#themeToggle');if(!t)return;const light=root.dataset.theme==='light',en=root.dataset.lang==='en';text(t,en?(light?'Dark  |  Light ✓':'Dark ✓  |  Light'):(light?'深色  |  浅色 ✓':'深色 ✓  |  浅色'));t.classList.toggle('is-active',light)}
 function applyTheme(theme){root.dataset.theme=theme==='light'?'light':'dark';localStorage.setItem('gapradar-theme',root.dataset.theme);syncTheme()}
 function world(){const g=$('.globe');if(!g)return;g.innerHTML='<svg viewBox="0 0 620 330" aria-hidden="true"><defs><pattern id="dots" width="9" height="9" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.35" fill="#3989c9"/></pattern><filter id="glow"><feGaussianBlur stdDeviation="3.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><g fill="url(#dots)" opacity=".86" filter="url(#glow)"><path d="M84 99l31-32 48-19 55 8 35 30-11 23-30 5-18 24-33-5-14 18-36-15-31-8z"/><path d="M205 151l28 12 22 37-8 49-22 45-17-23 4-37-18-31z"/><path d="M281 72l47-25 75 6 35 18 45-2 54 26-14 22-45 8-26 23-32-6-19 18-32-6-16-27-34-9-22-22z"/><path d="M343 156l40 4 31 30-10 50-31 45-27-14-15-44-10-37z"/><path d="M470 205l31-15 38 13 19 25-20 19-48-5z"/></g><g fill="#72d0ff"><circle cx="147" cy="93" r="3"/><circle cx="365" cy="98" r="3"/><circle cx="433" cy="124" r="3"/><circle cx="501" cy="220" r="3"/></g></svg>'}
 function wire(){
  const l=$('#langToggle'),t=$('#themeToggle');if(l)l.onclick=()=>applyLanguage(root.dataset.lang==='en'?'zh':'en');if(t)t.onclick=()=>applyTheme(root.dataset.theme==='light'?'dark':'light');
  $$('.nav a').forEach(a=>{a.onclick=(e)=>{
    var href=a.getAttribute('href')||'';
    $$('.nav a').forEach(x=>x.classList.remove('active'));
    a.classList.add('active');
    if(href==='#'){e.preventDefault();toast(root.dataset.lang==='en'?'Saved view coming soon.':'收藏夹即将上线，敬请期待。');return;}
    var el=href?document.getElementById(href.slice(1)):null;
    if(el){e.preventDefault();el.scrollIntoView({behavior:'smooth',block:'start'});}
  }});
  function toast(msg){var t=document.createElement('div');t.textContent=msg;t.style.cssText='position:fixed;left:50%;bottom:36px;transform:translateX(-50%);background:#0d3152;color:#cfe6ff;border:1px solid #2a5682;border-radius:10px;padding:9px 16px;font-size:12px;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.35);opacity:0;transition:opacity .2s;white-space:nowrap';document.body.appendChild(t);requestAnimationFrame(function(){t.style.opacity='1'});setTimeout(function(){t.style.opacity='0';setTimeout(function(){if(t.parentNode)t.remove()},250)},1800);}
  $$('.sector').forEach(s=>{s.onclick=()=>{const target=s.querySelector('.lang-en')?.textContent.trim()||s.querySelector('strong')?.textContent.trim()||'';$$('.sector').forEach(x=>x.classList.remove('selected'));s.classList.add('selected');$$('.row').forEach(r=>r.hidden=target&&!r.textContent.includes(target));$('#feed')?.scrollIntoView({behavior:'smooth'})}});
  $$('.more').forEach((m,i)=>{m.onclick=()=>{(i===0?$('#sectors'):i===1?$('#opps'):$('#feed'))?.scrollIntoView({behavior:'smooth'})}});
  $$('.arrow,.round').forEach(a=>a.setAttribute('rel','noopener noreferrer'));
 }
 root.dataset.theme=localStorage.getItem('gapradar-theme')==='light'?'light':'dark';ensureOpportunityCards();world();wire();applyLanguage(localStorage.getItem('gapradar-lang')==='en'?'en':'zh');applyTheme(root.dataset.theme);
})();
'''


def patch_dashboard(path: Path = Path('docs/index.html')) -> None:
    html = path.read_text(encoding='utf-8')
    for old in ('gapradar-runtime-v6', 'gapradar-runtime-v5', 'gapradar-runtime-v4', 'gapradar-runtime-v3', 'gapradar-runtime-v2'):
        token = f'<!-- {old} -->'
        if token in html:
            html = html.split(token, 1)[0].rstrip()
            break
    html = re.sub(r'<script>\(function\(\)\{var r=document\.documentElement.*?</script>\s*$', '', html, flags=re.S)
    if html.endswith('</body></html>'):
        html = html[:-14]
    payload = f'<!-- gapradar-runtime-v6 --><style>{STYLE}</style><script>{SCRIPT}</script></body></html>'
    path.write_text(html + payload, encoding='utf-8')


if __name__ == '__main__':
    patch_dashboard()
