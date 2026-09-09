from __future__ import annotations

import re
from pathlib import Path

STYLE = r'''
/* gapradar-runtime-v4 */
.content{max-width:none!important;width:calc(100vw - 230px)!important;margin-left:230px!important;padding:16px clamp(28px,2.2vw,52px) 48px!important}
.hero{grid-template-columns:minmax(430px,1.12fr) minmax(430px,.88fr)!important;gap:clamp(38px,4vw,76px)!important}
.overview{width:100%}.sectors{grid-template-columns:repeat(auto-fit,minmax(165px,1fr))!important}.opps{grid-template-columns:repeat(3,minmax(280px,1fr))!important}
.more,.filters span,.sector,.control,.nav a,.btn,.arrow,.round{cursor:pointer}.more:hover,.filters span:hover{filter:brightness(1.35)}.sector{transition:transform .16s ease,border-color .16s ease}.sector:hover{transform:translateY(-2px);border-color:#3d7099}.sector.selected{border-color:var(--cyan);box-shadow:0 0 0 1px color-mix(in srgb,var(--cyan) 30%,transparent)}
.filters span.active{color:var(--text);font-weight:750}.saved-on{color:#7bdca3!important}.opp[hidden],.row[hidden]{display:none!important}
.globe{left:30%!important;top:-48px!important;width:min(540px,38vw)!important;height:320px!important;opacity:.62!important}.globe svg{overflow:visible}
.control{min-width:88px!important;justify-content:center!important;font-weight:700!important;transition:.16s ease!important}.control:hover{border-color:var(--cyan)!important}.control.is-active{background:rgba(70,142,215,.18)!important;border-color:#3974a8!important}
html[data-lang="en"] .lang-zh{display:none!important}html[data-lang="en"] .lang-en{display:inline!important}html[data-lang="zh"] .lang-en{display:none!important}html[data-lang="zh"] .lang-zh{display:inline!important}
html[data-theme="light"]{color-scheme:light;--bg:#eef5fb!important;--bg2:#e6f0f7!important;--side:#f7fbff!important;--panel:#fff!important;--panel2:#f7fbff!important;--line:#c8d9e7!important;--text:#0d1b28!important;--muted:#60778b!important;--blue:#2a72d6!important;--cyan:#168fc5!important;--green:#258b5b!important;--shadow:0 14px 38px rgba(30,64,95,.12)!important}
html[data-theme="light"] body{background:#eef5fb!important;color:#0d1b28!important}html[data-theme="light"] .app{background:radial-gradient(circle at 61% 4%,rgba(90,157,221,.18),transparent 30%),linear-gradient(135deg,#edf5fb,#f8fbfe 73%)!important}html[data-theme="light"] .sidebar{background:#f7fbff!important}html[data-theme="light"] .nav a{color:#294259!important}html[data-theme="light"] .nav a.active{color:#0d1b28!important;background:#dceafb!important;border-color:#a9c8e5!important}html[data-theme="light"] .overview,html[data-theme="light"] .sector,html[data-theme="light"] .feed,html[data-theme="light"] .row{background:#fff!important;color:#0d1b28!important;border-color:#c8d9e7!important}html[data-theme="light"] .badge{background:#e5f2ff!important;color:#245b86!important}html[data-theme="light"] .opp{background:#fff!important;border-color:#bfd2e2!important;color:#0d1b28!important}
@media(min-width:1600px){.hero h1{font-size:54px}.opps{gap:16px!important}}
@media(min-width:2100px){.content{padding-left:56px!important;padding-right:56px!important}.hero{grid-template-columns:minmax(560px,1.18fr) minmax(520px,.82fr)!important}.sectors{grid-template-columns:repeat(7,minmax(0,1fr))!important}.opp{height:285px!important}}
@media(max-width:1200px){.hero{grid-template-columns:1fr!important}.globe{left:45%!important;opacity:.35!important}.opps{grid-template-columns:repeat(2,1fr)!important}}
@media(max-width:860px){.content{width:100%!important;margin-left:0!important;padding:18px 16px!important}.hero{grid-template-columns:1fr!important}.opps{grid-template-columns:1fr!important}}
'''

SCRIPT = r'''
(()=>{
 'use strict';
 const root=document.documentElement;
 const $=(s)=>document.querySelector(s), $$=(s)=>Array.from(document.querySelectorAll(s));
 const COPY={
  zh:{hero1:'从世界的变化',hero2:'发现下一个机会',heroP:'我们持续扫描全球的政策、公司动态、技术进展和市场变化，帮你发现可能被忽视的市场缺口。',today:'查看今日机会　→',browse:'浏览行业雷达',changing:'全球正在发生变化',changingP:'我们为你持续监测，并寻找值得关注的机会。',sector:'行业雷达',sectorP:'哪些领域今天变化最活跃？',opp:'今日推荐机会',oppP:'基于最新变化，我们认为以下机会最值得关注。',feed:'全球重要变化',feedP:'今天发现的其他值得了解的变化。',allSector:'查看全部行业　→',allOpp:'查看全部机会　→',stats:['今日扫描资讯','关键变化事件','深入分析','值得关注机会'],filters:['全部','科技','能源','监管','消费'],footer:'每 6 小时自动扫描一次 · 推荐代表研究价值，不构成投资建议。',updated:'最后更新',next:'下次更新',market:'企业市场',watch:'持续观察',early:'早期机会'},
  en:{hero1:'See what is changing',hero2:'Find the next opportunity',heroP:'We continuously scan policy, company, technology and market shifts worldwide to uncover market gaps others may miss.',today:'View today’s opportunities　→',browse:'Browse sector radar',changing:'The world is changing',changingP:'We continuously monitor those changes and look for opportunities worth your attention.',sector:'Sector Radar',sectorP:'Which sectors are moving most today?',opp:'Today’s Opportunities',oppP:'The opportunities most worth watching based on the latest changes.',feed:'Important Global Changes',feedP:'Other changes worth knowing about today.',allSector:'View all sectors　→',allOpp:'View all opportunities　→',stats:['Items scanned today','Key change events','Deep analyses','Opportunities to watch'],filters:['All','Tech','Energy','Regulation','Consumer'],footer:'Automatic scan every 6 hours · Recommendations indicate research value, not investment advice.',updated:'Last updated',next:'Next update',market:'Business market',watch:'Watch',early:'Early opportunity'}
 };
 function text(el,v){if(el&&v!=null)el.textContent=v}
 function rawPill(p){if(!p)return'';if(!p.dataset.raw){p.dataset.raw=p.textContent.replace(/^(最后更新|下次更新|Last updated|Next update)\s*/,'')}return p.dataset.raw}
 function applyLanguage(lang){
  lang=lang==='en'?'en':'zh';const d=COPY[lang];root.dataset.lang=lang;root.setAttribute('lang',lang==='en'?'en':'zh-CN');localStorage.setItem('gapradar-lang',lang);
  const h=$('.hero h1');if(h)h.innerHTML=d.hero1+'<br><span class="grad">'+d.hero2+'</span>';
  text($('.hero-copy p'),d.heroP);const buttons=$$('.hero .btn');text(buttons[0],d.today);text(buttons[1],d.browse);
  text($('.overview h2'),d.changing);text($('.overview p'),d.changingP);$$('.stats span').forEach((el,i)=>text(el,d.stats[i]));
  const heads=$$('.section .head');if(heads[0]){text(heads[0].querySelector('h2'),d.sector);text(heads[0].querySelector('p'),d.sectorP);text(heads[0].querySelector('.more'),d.allSector)}if(heads[1]){text(heads[1].querySelector('h2'),d.opp);text(heads[1].querySelector('p'),d.oppP);text(heads[1].querySelector('.more'),d.allOpp)}
  const fh=$('#feed .feedtop');if(fh){text(fh.querySelector('h2'),d.feed);text(fh.querySelector('p'),d.feedP)}
  const filters=$$('.filters>*');d.filters.forEach((v,i)=>{if(filters[i]){let count='';if(i===0){const m=filters[i].textContent.match(/\d+/);count=m?' '+m[0]:''}text(filters[i],v+count)}});
  $$('.bottommeta').forEach(el=>{const early=/早期|Early/i.test(el.textContent);text(el,d.market+'　◷ '+(early?d.early:d.watch))});
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
  $$('.nav a').forEach(a=>{a.onclick=(e)=>{if(a.getAttribute('href')==='#')e.preventDefault();$$('.nav a').forEach(x=>x.classList.remove('active'));a.classList.add('active')}});
  $$('.sector').forEach(s=>{s.onclick=()=>{const target=s.querySelector('.lang-en')?.textContent.trim()||s.querySelector('strong')?.textContent.trim()||'';$$('.sector').forEach(x=>x.classList.remove('selected'));s.classList.add('selected');$$('.row').forEach(r=>r.hidden=target&&!r.textContent.includes(target));$('#feed')?.scrollIntoView({behavior:'smooth'})}});
  $$('.more').forEach((m,i)=>{m.onclick=()=>{(i===0?$('#sectors'):i===1?$('#opps'):$('#feed'))?.scrollIntoView({behavior:'smooth'})}});
  $$('.arrow,.round').forEach(a=>a.setAttribute('rel','noopener noreferrer'));
 }
 root.dataset.theme=localStorage.getItem('gapradar-theme')==='light'?'light':'dark';world();wire();applyLanguage(localStorage.getItem('gapradar-lang')==='en'?'en':'zh');applyTheme(root.dataset.theme);
})();
'''


def patch_dashboard(path: Path = Path('docs/index.html')) -> None:
    html = path.read_text(encoding='utf-8')
    # Remove any previous injected runtime first.
    for old in ('gapradar-runtime-v4', 'gapradar-runtime-v3', 'gapradar-runtime-v2'):
        token = f'<!-- {old} -->'
        if token in html:
            html = html.split(token, 1)[0].rstrip()
            break
    # Remove the renderer's legacy inline controller. Two controllers on the same
    # buttons caused language/theme clicks to toggle twice and cancel themselves.
    html = re.sub(r'<script>\(function\(\)\{var r=document\.documentElement.*?</script>\s*$', '', html, flags=re.S)
    if html.endswith('</body></html>'):
        html = html[:-14]
    payload = f'<!-- gapradar-runtime-v4 --><style>{STYLE}</style><script>{SCRIPT}</script></body></html>'
    path.write_text(html + payload, encoding='utf-8')


if __name__ == '__main__':
    patch_dashboard()
