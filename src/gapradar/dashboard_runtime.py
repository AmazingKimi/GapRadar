from __future__ import annotations

from pathlib import Path

STYLE = r'''
/* GapRadar runtime hardening: fluid desktop canvas + interaction affordances */
.content{max-width:none!important;width:calc(100% - 230px)!important;margin-left:230px!important;padding-left:34px!important;padding-right:34px!important}
.hero{grid-template-columns:minmax(430px,1.15fr) minmax(420px,.85fr)!important}
.overview{width:100%}.sectors{grid-template-columns:repeat(auto-fit,minmax(155px,1fr))!important}.opps{grid-template-columns:repeat(3,minmax(260px,1fr))!important}
.more,.filters span,.sector,.control,.nav a,.btn,.arrow,.round{cursor:pointer}.more:hover,.filters span:hover{filter:brightness(1.35)}.sector{transition:transform .16s ease,border-color .16s ease}.sector:hover{transform:translateY(-2px);border-color:#3d7099}.sector.selected{border-color:var(--cyan);box-shadow:0 0 0 1px color-mix(in srgb,var(--cyan) 30%,transparent)}
.filters span.active{color:var(--text);font-weight:750}.saved-on{color:#7bdca3!important}.opp[hidden],.row[hidden]{display:none!important}
.globe{left:31%!important;top:-42px!important;width:520px!important;height:310px!important;opacity:.68!important}.globe svg{overflow:visible}
@media(min-width:1600px){.content{padding-right:46px!important}.hero h1{font-size:54px}.opps{gap:16px!important}}
@media(max-width:860px){.content{width:100%!important;margin-left:0!important}.hero{grid-template-columns:1fr!important}.opps{grid-template-columns:1fr!important}}
'''

SCRIPT = r'''
(()=>{
 const root=document.documentElement;
 const $=(s)=>document.querySelector(s), $$=(s)=>[...document.querySelectorAll(s)];
 const zh={hero1:'从世界的变化',hero2:'发现下一个机会',heroP:'我们持续扫描全球的政策、公司动态、技术进展和市场变化，帮你发现可能被忽视的市场缺口。',today:'查看今日机会　→',browse:'浏览行业雷达',changing:'全球正在发生变化',changingP:'我们为你持续监测，并寻找值得关注的机会。',sector:'行业雷达',sectorP:'哪些领域今天变化最活跃？',opp:'今日推荐机会',oppP:'基于最新变化，我们认为以下机会最值得关注。',feed:'全球重要变化',feedP:'今天发现的其他值得了解的变化。',allSector:'查看全部行业　→',allOpp:'查看全部机会　→'};
 const en={hero1:'See what is changing',hero2:'Find the next opportunity',heroP:'We continuously scan policy, company, technology and market shifts worldwide to uncover market gaps others may miss.',today:'View today’s opportunities　→',browse:'Browse sector radar',changing:'The world is changing',changingP:'We continuously monitor those changes and look for opportunities worth your attention.',sector:'Sector Radar',sectorP:'Which sectors are moving most today?',opp:'Today’s Opportunities',oppP:'The opportunities most worth watching based on the latest changes.',feed:'Important Global Changes',feedP:'Other changes worth knowing about today.',allSector:'View all sectors　→',allOpp:'View all opportunities　→'};
 function setText(el,v){if(el) el.textContent=v}
 function applyLanguage(lang){
   root.dataset.lang=lang; localStorage.setItem('gapradar-lang',lang); const d=lang==='en'?en:zh;
   const h=$('.hero h1'); if(h) h.innerHTML=`${d.hero1}<br><span class="grad">${d.hero2}</span>`;
   setText($('.hero-copy p'),d.heroP); const bs=$$('.hero .btn'); setText(bs[0],d.today);setText(bs[1],d.browse);
   setText($('.overview h2'),d.changing);setText($('.overview p'),d.changingP);
   const heads=$$('.section .head, .feedtop');
   if(heads[0]){setText(heads[0].querySelector('h2'),d.sector);setText(heads[0].querySelector('p'),d.sectorP);setText(heads[0].querySelector('.more'),d.allSector)}
   if(heads[1]){setText(heads[1].querySelector('h2'),d.opp);setText(heads[1].querySelector('p'),d.oppP);setText(heads[1].querySelector('.more'),d.allOpp)}
   const feedHead=$('#feed .feedtop')||$('#feed .head'); if(feedHead){setText(feedHead.querySelector('h2'),d.feed);setText(feedHead.querySelector('p'),d.feedP)}
   const toggle=$('#langToggle'); if(toggle) toggle.textContent=lang==='en'?'中文':'EN';
   // Generated sector labels are bilingual too.
   const map={'科技与 AI':'AI & Technology','能源与气候':'Energy & Climate','医疗与生物':'Healthcare & Biotech','金融与支付':'Finance & Fintech','出行与交通':'Mobility','工业与机器人':'Industry & Robotics','消费 / 社会':'Consumer & Society','太空 / 前沿':'Frontier'};
   $$('.sector strong,.company').forEach(el=>{if(!el.dataset.zh){const t=el.textContent.trim();el.dataset.zh=Object.keys(map).find(k=>t.includes(k))||t;el.dataset.en=map[el.dataset.zh]||t} setText(el,lang==='en'?el.dataset.en:el.dataset.zh)});
 }
 function world(){const g=$('.globe');if(!g)return;g.innerHTML=`<svg viewBox="0 0 620 330" aria-hidden="true"><defs><pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.45" fill="#3989c9"/></pattern><filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><ellipse cx="310" cy="164" rx="244" ry="135" fill="none" stroke="#235b88" stroke-opacity=".38"/><g fill="url(#dots)" opacity=".92" filter="url(#glow)"><path d="M96 104l27-32 46-18 49 8 31 28-10 22-28 4-18 23-30-5-13 19-34-15-26-6z"/><path d="M215 154l25 10 20 35-9 47-20 42-15-20 4-35-17-28z"/><path d="M287 76l43-23 70 5 32 17 43-1 50 24-13 20-42 8-24 21-30-6-17 17-30-5-15-25-31-8-20-21z"/><path d="M347 157l38 3 28 29-9 48-30 43-25-13-14-42-10-35z"/><path d="M467 204l29-14 35 12 17 24-18 18-45-5z"/></g><g fill="#66c8ff"><circle cx="151" cy="96" r="3"/><circle cx="365" cy="101" r="3"/><circle cx="430" cy="126" r="3"/><circle cx="497" cy="218" r="3"/></g></svg>`}
 function filterSector(label){const needle=label.toLowerCase();$$('.row').forEach(r=>r.hidden=needle&& !r.textContent.toLowerCase().includes(needle));$('#feed')?.scrollIntoView({behavior:'smooth'});}
 function wire(){
   $('#langToggle')?.addEventListener('click',()=>applyLanguage(root.dataset.lang==='en'?'zh':'en'));
   $('#themeToggle')?.addEventListener('click',()=>{const t=root.dataset.theme==='light'?'dark':'light';root.dataset.theme=t;localStorage.setItem('gapradar-theme',t);$('#themeToggle').textContent=t==='light'?'Dark':'Light'});
   $$('.nav a').forEach(a=>a.addEventListener('click',()=>{$$('.nav a').forEach(x=>x.classList.remove('active'));a.classList.add('active')}));
   $$('.sector').forEach(s=>s.addEventListener('click',()=>{$$('.sector').forEach(x=>x.classList.remove('selected'));s.classList.add('selected');filterSector(s.querySelector('strong')?.textContent||'')}));
   $$('.more').forEach((m,i)=>m.addEventListener('click',()=>{(i===0?$('#sectors'):i===1?$('#opps'):$('#feed'))?.scrollIntoView({behavior:'smooth'})}));
   const saved=$$('.nav a').find(a=>a.textContent.includes('收藏')||a.textContent.includes('Saved')); if(saved){saved.href='#opps';saved.addEventListener('click',e=>{e.preventDefault();saved.classList.toggle('saved-on');$('#opps')?.scrollIntoView({behavior:'smooth'})})}
   $$('.arrow,.round').forEach(a=>{a.setAttribute('rel','noopener noreferrer');});
 }
 const theme=localStorage.getItem('gapradar-theme');if(theme)root.dataset.theme=theme;
 world();wire();applyLanguage(localStorage.getItem('gapradar-lang')||root.dataset.lang||'zh');
 const tb=$('#themeToggle');if(tb)tb.textContent=root.dataset.theme==='light'?'Dark':'Light';
})();
'''

def patch_dashboard(path: Path = Path('docs/index.html')) -> None:
    html = path.read_text(encoding='utf-8')
    marker = 'gapradar-runtime-v2'
    if marker in html:
        html = html.split(f'<!-- {marker} -->', 1)[0].rstrip()
        if html.endswith('</body></html>'):
            html = html[:-14]
    elif html.endswith('</body></html>'):
        html = html[:-14]
    payload = f'<!-- {marker} --><style>{STYLE}</style><script>{SCRIPT}</script></body></html>'
    path.write_text(html + payload, encoding='utf-8')

if __name__ == '__main__':
    patch_dashboard()
