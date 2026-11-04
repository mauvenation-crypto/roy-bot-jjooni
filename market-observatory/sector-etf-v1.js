(()=>{
'use strict';
if(window.__JJOONI_OBSERVATORY_SECTOR_ETF_V1)return;
const LEGACY_QA_TOKEN='RS vs SPY 1M';
const STATE={version:'1.7',status:'BOOTING',loaded:false,loading:false,error:null,chart_error:null,rendered_at:null};
window.__JJOONI_OBSERVATORY_SECTOR_ETF_V1=STATE;
const q=(s,r=document)=>{try{return r.querySelector(s)}catch(_){return null}};
const n=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(v);return Number.isFinite(x)?x:null};
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const pct=v=>{const x=n(v);return x==null?'—':(x>=0?'+':'')+x.toFixed(2)+'%'};
const cls=v=>{const x=n(v);return x==null?'flat':x>0?'up':x<0?'down':'flat'};
const price=(v,market='US')=>{const x=n(v);return x==null?'—':(market==='KR'?'₩':'$')+x.toLocaleString(market==='KR'?'ko-KR':'en-US',{maximumFractionDigits:market==='KR'?0:2})};
const H=[1,5,10,20,50,100];
let DATA=null,rsChart=null;const openThemes=new Set();

function ensureStyle(){
 if(q('#obsSectorEtfStyle'))return;
 const st=document.createElement('style');st.id='obsSectorEtfStyle';st.textContent=`
 #sectors .obsSectorHead{display:flex;justify-content:space-between;gap:10px;align-items:flex-end;margin-bottom:12px}
 #sectors .obsSectorTitle{font-size:19px;font-weight:950;color:#10233d;letter-spacing:-.3px}
 #sectors .obsSectorBadge{font-size:9px;font-weight:900;color:#245b98;background:#eef5ff;border:1px solid #d7e6fb;border-radius:999px;padding:6px 9px;white-space:nowrap}
 #sectors .obsSectorKpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:10px 0 12px}
 #sectors .obsSectorKpi{background:#fff;border:1px solid #e4eaf1;border-radius:13px;padding:10px;min-width:0}
 #sectors .obsSectorKpi span{display:block;font-size:8px;font-weight:850;color:#7b8798}
 #sectors .obsSectorKpi b{display:block;margin-top:4px;font-size:14px;color:#172033;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 #sectors{min-width:0;max-width:100%;overflow-x:clip}
 #sectors .obsSectorGrid{display:grid;grid-template-columns:1.35fr .65fr;gap:12px;min-width:0;max-width:100%}
 #sectors .obsSectorGrid>*{min-width:0;max-width:100%}
 #sectors .obsSectorCard{background:#fff;border:1px solid #e4eaf1;border-radius:15px;padding:13px;box-shadow:0 4px 16px rgba(12,31,54,.035);min-width:0}
 #sectors .obsSectorCard h3{margin:0 0 3px;font-size:14px}
 #sectors .obsSectorTableWrap{width:100%;max-width:100%;min-width:0;overflow:auto;-webkit-overflow-scrolling:touch;border:1px solid #edf1f5;border-radius:11px;margin-top:9px}
 #sectors table{border-collapse:collapse;width:100%;min-width:760px;font-size:10px}
 #sectors th,#sectors td{padding:8px 7px;border-bottom:1px solid #eef2f6;text-align:right;white-space:nowrap}
 #sectors th{position:sticky;top:0;background:#f8fafc;color:#667085;font-size:9px;z-index:1}
 #sectors th:first-child,#sectors td:first-child{text-align:left;position:sticky;left:0;background:#fff;z-index:1}
 #sectors th:first-child{background:#f8fafc;z-index:2}
 #sectors .obsClassicSparkCell{width:170px;min-width:150px;padding:5px 7px}
 #sectors .obsClassicSparkCell .obsSpark{min-width:130px;margin-top:0}
 #sectors .ticker{font-size:11px;font-weight:950;color:#101828}.name{font-size:8px;color:#8b97a6;margin-top:2px}
 #sectors .up{color:#d92d20}.down{color:#175cd3}.flat{color:#667085}
 #sectors .obsTheme{margin-top:13px}.obsTheme:first-child{margin-top:0}.obsThemeTitle{font-size:10px;font-weight:950;color:#526071;margin-bottom:7px}
 #sectors details.obsTheme>summary{cursor:pointer;min-height:44px;padding:12px 4px;font-size:13px}#sectors details.obsTheme[open]>summary{border-bottom:1px solid #e4eaf1;margin-bottom:10px}
 #sectors .obsThemeRows{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
 #sectors .obsEtfCard{border:1px solid #e6ebf1;border-radius:12px;padding:9px;background:#fff;min-width:0}
 #sectors .obsEtfTop{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;margin-bottom:7px}
 #sectors .obsEtfPrice{font-size:10px;font-weight:900;color:#475467;white-space:nowrap}
 #sectors .obsPeriodGrid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:4px}
 #sectors .obsPeriod{background:#f8fafc;border:1px solid #eef2f6;border-radius:8px;padding:5px 3px;text-align:center;min-width:0}
 #sectors .obsPeriod span{display:block;font-size:7px;font-weight:900;color:#98a2b3}.obsPeriod b{display:block;margin-top:2px;font-size:9px;white-space:nowrap}
 #sectors .obsSpark{margin-top:7px;padding:6px 7px 4px;border:1px solid #eef2f6;border-radius:9px;background:linear-gradient(180deg,#fbfcfe,#f8fafc);overflow:hidden}
 #sectors .obsSparkHead{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:3px;font-size:7px;font-weight:850;color:#98a2b3}
 #sectors .obsSparkHead b{font-size:8px}.obsSpark svg{display:block;width:100%;height:42px;overflow:visible}.obsSpark polyline{fill:none;stroke:currentColor;stroke-width:2;vector-effect:non-scaling-stroke;stroke-linecap:round;stroke-linejoin:round}.obsSpark circle{fill:currentColor}.obsSpark .sparkBase{stroke:#e4e7ec;stroke-width:1;vector-effect:non-scaling-stroke}
 #sectors .obsRs20{margin-top:6px;padding-top:6px;border-top:1px solid #eef2f6;display:flex;justify-content:space-between;font-size:8px;color:#667085}.obsRs20 b{font-size:9px}
 #sectors .obsSectorLeader{display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid #eef2f6;font-size:10px}
 #sectors .obsSectorLeader:last-child{border-bottom:0}.obsSectorLeader b{font-size:11px}.obsSectorRank{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;border-radius:999px;background:#f2f4f7;font-size:9px;font-weight:950;margin-right:7px}
 #sectors .obsSectorQuality{margin-top:10px;padding:9px 10px;border-radius:10px;font-size:9px;line-height:1.5;background:#f8fafc;border:1px solid #e8edf3;color:#667085}.obsSectorQuality.warn{background:#fff7ed;border-color:#fed7aa;color:#9a3412}
 #sectors .obsSectorChart{position:relative;width:100%;max-width:100%;min-width:0;height:330px;margin-top:8px;overflow:hidden}
 #sectors .obsSectorChart canvas{display:block;width:100%!important;max-width:100%!important;min-width:0!important}
 #sectors .obsSectorLoading{padding:40px 14px;text-align:center;color:#718096;font-size:11px}

 #sectors .sectorRanking{margin-bottom:12px;padding:18px;border-top:5px solid #171717}
 #sectors .sectorRankTop{display:flex;justify-content:space-between;gap:8px;align-items:start}#sectors .sectorRankTop h3{font-size:20px}#sectors .sectorRankTop p,#sectors .sectorRankTop span,#sectors .sectorRankNote{font-size:12px;color:#667085;line-height:1.5}
 #sectors .sectorRankControls{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}#sectors .sectorRankControls button{min-height:44px;padding:8px 14px;border-radius:9px;border:1px solid #d8e1ed;background:#fff;color:#344054;font-weight:750}#sectors .sectorRankControls button[aria-pressed=true]{background:#17233a;border-color:#17233a;color:#fff}
 #sectors .sectorRankRows{display:grid;gap:3px}#sectors .sectorRankRow{display:grid;grid-template-columns:minmax(95px,150px) minmax(30px,1fr) 86px;align-items:center;gap:10px;width:100%;min-height:48px;background:#fff;border:0;border-bottom:1px solid #eef1f5;text-align:left;cursor:pointer;padding:6px}#sectors .sectorRankRow:focus-visible{outline:3px solid #497ad2}#sectors .sectorRankLabel b{font-size:14px;display:block}#sectors .sectorRankLabel small{font-size:11px;color:#667085}#sectors .sectorRankTrack{background:#f1f4f8;height:12px;border-radius:8px;overflow:hidden}#sectors .sectorRankTrack i{display:block;height:100%;border-radius:8px}#sectors .sectorRankTrack i.up{background:#d92d20}#sectors .sectorRankTrack i.down{background:#175cd3}#sectors .sectorRankRow strong{text-align:right;font-size:15px;white-space:nowrap}#sectors .sectorRankDetail{margin-top:12px;border:1px solid #e4eaf1;border-radius:10px;padding:12px;background:#f9fbff}#sectors .sectorRankDetail p{font-size:12px;color:#526071;line-height:1.5;margin:8px 0}
 @media(max-width:1100px){
  #sectors .obsSectorHead{align-items:flex-start;flex-wrap:wrap}
  #sectors .obsSectorBadge{max-width:100%;white-space:normal;overflow-wrap:anywhere}
  #sectors .obsSectorKpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  #sectors .obsSectorGrid{grid-template-columns:minmax(0,1fr)}
  #sectors .obsSectorCard{width:100%;max-width:100%;padding:11px}
  #sectors .obsSectorTableWrap{overflow:hidden}
  #sectors table{display:block;width:100%;min-width:0}
  #sectors thead{display:none}
  #sectors tbody{display:grid;gap:8px;padding:7px;background:#f8fafc}
  #sectors tbody tr{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));width:100%;min-width:0;overflow:hidden;background:#fff;border:1px solid #e7edf4;border-radius:10px}
  #sectors tbody td{display:block;min-width:0;padding:7px 3px;border:0;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #sectors tbody td::before{content:attr(data-label);display:block;margin-bottom:2px;color:#98a2b3;font-size:7px;font-weight:850}
  #sectors tbody td:first-child{position:static;grid-column:1/-1;padding:8px 9px;text-align:left;background:#fff;border-bottom:1px solid #eef2f6;overflow:visible}
  #sectors tbody td:first-child::before{display:none}
  #sectors tbody .obsClassicSparkCell{grid-column:1/-1;width:auto;min-width:0;padding:5px 7px 8px;overflow:hidden}
  #sectors tbody .obsClassicSparkCell::before{display:none}
  #sectors tbody .obsClassicSparkCell .obsSpark{width:100%;min-width:0;margin-top:0}
  #sectors details.obsTheme>summary{cursor:pointer;min-height:44px;padding:12px 4px;font-size:13px}#sectors details.obsTheme[open]>summary{border-bottom:1px solid #e4eaf1;margin-bottom:10px}
 #sectors .obsThemeRows{grid-template-columns:minmax(0,1fr)}
  #sectors .obsEtfCard{width:100%;max-width:100%;overflow:hidden}
  #sectors .obsPeriodGrid{grid-template-columns:repeat(3,minmax(0,1fr))}
  #sectors .obsSpark{width:100%;max-width:100%}
  #sectors .obsSpark svg{width:100%;max-width:100%;height:38px;overflow:hidden}
  #sectors .obsSectorChart{height:280px}
  #sectors .obsSectorLeader{align-items:flex-start;flex-wrap:wrap}
  #sectors .obsSectorLeader>b{min-width:0;max-width:100%;margin-left:auto;text-align:right;white-space:normal;overflow-wrap:anywhere}
 }
 @media(max-width:380px){
  #sectors .obsSectorKpis{grid-template-columns:1fr 1fr;gap:6px}
  #sectors .obsSectorKpi{padding:8px}
  #sectors .obsSectorKpi b{font-size:12px}
  #sectors .obsSectorCard{padding:9px}
  #sectors tbody{padding:5px}
 }
 `;(document.head||document.documentElement).appendChild(st);
}

function ensureShell(){
 ensureStyle();
 const tabs=q('#tabs'),main=q('main.wrap');if(!tabs||!main)return false;
 let tab=q('button[data-tab="sectors"]',tabs);
 if(!tab){tab=document.createElement('button');tab.type='button';tab.dataset.tab='sectors';tab.textContent='섹터·ETF';const ref=q('button[data-tab="tripod"]',tabs);if(ref)tabs.insertBefore(tab,ref);else tabs.appendChild(tab)}
 let panel=q('#sectors');
 if(!panel){panel=document.createElement('section');panel.className='panel';panel.id='sectors';panel.innerHTML='<div class="obsSectorLoading">섹터 ETF 데이터는 이 탭을 열 때만 불러옵니다.</div>';const ref=q('#tripod',main);if(ref)main.insertBefore(panel,ref);else main.appendChild(panel)}
 return true;
}

function classicRows(){return (DATA?.groups||[]).find(g=>g.key==='classic')?.rows||[]}
function seriesRet(ticker,days){
 const xs=DATA?.series?.[ticker]||[];if(xs.length<=days)return null;
 const a=n(xs[xs.length-1]?.value),b=n(xs[xs.length-1-days]?.value);return a!=null&&b?((a/b)-1)*100:null;
}
function ret(r,days){const direct=n(r?.[`ret_${days}d_pct`]);return direct!=null?direct:seriesRet(r?.ticker,days)}
function benchRet(ticker,days){const b=DATA?.benchmarks?.[ticker]||{ticker};const direct=n(b?.[`ret_${days}d_pct`]);return direct!=null?direct:seriesRet(ticker,days)}
function rsSpy(r,days){if(r?.market==='KR')return null;const direct=n(r?.[`rs_spy_${days}d_pct`]);if(direct!=null)return direct;const a=ret(r,days),b=benchRet('SPY',days);return a!=null&&b!=null?a-b:null}
function leaderText(xs){return xs?.length?xs.map(x=>`${x.ticker} ${pct(x.value)}`).join(' · '):'—'}
function ranked20(rows){return rows.map(r=>({ticker:r.ticker,value:rsSpy(r,20)})).filter(x=>x.value!=null).sort((a,b)=>b.value-a.value)}
function growthDefense20(rows){const avg=xs=>{const a=xs.filter(v=>v!=null);return a.length?a.reduce((s,v)=>s+v,0)/a.length:null};const g=avg(rows.filter(r=>['XLK','XLC','XLY'].includes(r.ticker)).map(r=>ret(r,20)));const d=avg(rows.filter(r=>['XLV','XLP','XLU'].includes(r.ticker)).map(r=>ret(r,20)));return g!=null&&d!=null?g-d:null}

function periodGrid(r){return `<div class="obsPeriodGrid">${H.map(d=>`<div class="obsPeriod"><span>${d}일</span><b class="${cls(ret(r,d))}">${pct(ret(r,d))}</b></div>`).join('')}</div>`}
function sparkline(r){
 const xs=(DATA?.series?.[r?.ticker]||[]).slice(-101).map(p=>({date:p?.date,value:n(p?.value)})).filter(p=>p.value!=null);
 if(xs.length<2)return '<div class="obsSpark"><div class="obsSparkHead"><span>100거래일 수익률</span><b class="flat">데이터 부족</b></div></div>';
 const vals=xs.map(p=>p.value),lo=Math.min(...vals),hi=Math.max(...vals),span=hi-lo||1,w=320,h=42,pad=2;
 const points=vals.map((v,i)=>`${(pad+(i*(w-pad*2)/(vals.length-1))).toFixed(1)},${(pad+((hi-v)/span)*(h-pad*2)).toFixed(1)}`).join(' ');
 const move=ret(r,100),tone=move==null?'flat':move>=0?'up':'down';
 const lastPair=points.split(' ').pop().split(',');
 return `<div class="obsSpark ${tone}"><div class="obsSparkHead"><span>100거래일 수익률</span><b class="${tone}">${pct(move)}</b></div><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="${esc(r.ticker)} 최근 100거래일 가격 추이"><line class="sparkBase" x1="0" y1="${h-1}" x2="${w}" y2="${h-1}"></line><polyline points="${points}"></polyline><circle cx="${lastPair[0]}" cy="${lastPair[1]}" r="2.4"></circle></svg></div>`;
}
function themeHtml(){
 const groups=(DATA?.groups||[]).filter(g=>g.key!=='classic');
 return groups.map(g=>`<details class="obsTheme" data-theme="${esc(g.key)}" ${openThemes.has(g.key)?'open':''}><summary class="obsThemeTitle">${esc(g.label)} · ${(g.rows||[]).length}개 ETF · 펼쳐보기</summary><div class="obsThemeRows">${(g.rows||[]).map(r=>`<div class="obsEtfCard"><div class="obsEtfTop"><div><div class="ticker">${esc(r.ticker)}</div><div class="name">${esc(r.name||r.ticker)}</div></div><div class="obsEtfPrice">${price(r.price,r.market)}</div></div>${periodGrid(r)}${sparkline(r)}<div class="obsRs20"><span>20일 RS vs SPY</span><b class="${cls(rsSpy(r,20))}">${pct(rsSpy(r,20))}</b></div></div>`).join('')}</div></details>`).join('');
}

function classicTable(rows){
 const sorted=rows.slice().sort((a,b)=>(rsSpy(b,20)??-999)-(rsSpy(a,20)??-999));
 return `<div class="obsSectorTableWrap"><table><thead><tr><th>ETF / 섹터</th><th>가격</th>${H.map(d=>`<th>${d}일</th>`).join('')}<th>RS20 vs SPY</th><th>100일 추이</th></tr></thead><tbody>${sorted.map(r=>`<tr><td><div class="ticker">${esc(r.ticker)}</div><div class="name">${esc(r.name||'')}</div></td><td data-label="가격">${price(r.price,r.market)}</td>${H.map(d=>`<td data-label="${d}일" class="${cls(ret(r,d))}">${pct(ret(r,d))}</td>`).join('')}<td data-label="RS20" class="${cls(rsSpy(r,20))}"><b>${pct(rsSpy(r,20))}</b></td><td class="obsClassicSparkCell">${sparkline(r)}</td></tr>`).join('')}</tbody></table></div>`;
}

function drawRsChart(rows){
 const canvas=q('#sectorRsChart');if(!canvas||typeof Chart==='undefined')return true;
 const sorted=rows.map(r=>({ticker:r.ticker,value:rsSpy(r,20)})).filter(x=>x.value!=null).sort((a,b)=>a.value-b.value);
 if(rsChart)try{rsChart.destroy()}catch(_){}
 rsChart=new Chart(canvas,{type:'bar',data:{labels:sorted.map(r=>r.ticker),datasets:[{label:'20D RS vs SPY (%p)',data:sorted.map(r=>r.value)}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},scales:{x:{ticks:{font:{size:9}},grid:{color:'#eef2f6'}},y:{ticks:{font:{size:9}},grid:{display:false}}}}});
 return true;
}

const SECTOR_KO={XLK:'기술',XLC:'커뮤니케이션',XLY:'경기소비재',XLF:'금융',XLI:'산업재',XLE:'에너지',XLB:'소재',XLV:'헬스케어',XLP:'필수소비재',XLU:'유틸리티',XLRE:'부동산'};
const PERIODS=[['1d','1일'],['5d','1주'],['1m','1개월'],['3m','3개월'],['1y','1년']];
let rankPeriod='1d',rankScope='classic',rankSelected=null;
function periodInfo(row,key){
 const xs=DATA?.series?.[row.ticker]||[], end=xs.at(-1), marketEnd=row.observed_date;
 if(!end||end.date!==marketEnd||end.date!==DATA?.completed_cutoffs?.[row.market])return null;
 let base=null;
 if(key==='1d'||key==='5d'){const days=key==='1d'?1:5;base=xs.at(-1-days)}
 else {
  const months=key==='1m'?1:key==='3m'?3:12, cached=row.calendar_returns?.[String(months)];
  if(cached?.end_date===end.date&&n(cached.pct)!=null)return {value:n(cached.pct),base:cached.base_date,end:end.date};
  const ed=new Date(end.date+'T00:00:00Z'),target=new Date(Date.UTC(ed.getUTCFullYear(),ed.getUTCMonth()-months,1));
  const lastDay=new Date(Date.UTC(target.getUTCFullYear(),target.getUTCMonth()+1,0)).getUTCDate();target.setUTCDate(Math.min(ed.getUTCDate(),lastDay));
  const cutoff=target.toISOString().slice(0,10);base=xs.filter(p=>p.date<=cutoff).at(-1);
  if(!base||(target-new Date(base.date+'T00:00:00Z'))/86400000>7)return null;
 }
 const a=n(end.value),b=n(base?.value);return a!=null&&b>0?{value:(a/b-1)*100,base:base.date,end:end.date}:null;
}
function rankRows(){
 if(rankScope==='classic')return classicRows();
 const wanted=['SMH','SOXX','IGV','SKYY','HACK','XBI','KRE','ITA','XAR','PAVE','XOP','BOTZ','ROBO'];
 return (DATA?.groups||[]).flatMap(g=>g.rows||[]).filter(r=>wanted.includes(r.ticker));
}
function rankView(){
 const rows=rankRows().map(r=>({r,info:periodInfo(r,rankPeriod)})).sort((a,b)=>a.info&&b.info?b.info.value-a.info.value:a.info?-1:b.info?1:0);
 const scale=Math.max(1,...rows.map(x=>Math.abs(x.info?.value||0)));
 const current=rows.find(x=>x.r.ticker===rankSelected);
 return `<section class="obsSectorCard sectorRanking" aria-label="기간별 섹터 등락"><div class="sectorRankTop"><div><h3>시장의 방향 · 섹터별 등락</h3><p>완료 종가 기준 · 선택 기간의 상승률 순</p></div><span>미국 ${esc(DATA.completed_cutoffs?.US||'—')}</span></div><div class="sectorRankControls" role="group" aria-label="비교 기간">${PERIODS.map(([k,v])=>`<button type="button" data-rank-period="${k}" aria-pressed="${rankPeriod===k}">${v}</button>`).join('')}</div><div class="sectorRankControls" role="group" aria-label="섹터 종류"><button type="button" data-rank-scope="classic" aria-pressed="${rankScope==='classic'}">미국 11개 섹터</button><button type="button" data-rank-scope="theme" aria-pressed="${rankScope==='theme'}">주요 테마 ETF</button></div><p class="sectorRankNote">1일=전 거래일 · 1주=5거래일 · 1개월/3개월/1년=같은 날짜 이전 최근 거래일 · 배당 제외 가격수익률. 종가 지연 또는 이력 부족은 확인 대기로 표시합니다.</p><div class="sectorRankRows">${rows.map(({r,info})=>`<button type="button" class="sectorRankRow" data-rank-ticker="${esc(r.ticker)}" aria-expanded="${rankSelected===r.ticker}"><span class="sectorRankLabel"><b>${esc(SECTOR_KO[r.ticker]||r.name||r.ticker)}</b><small>${esc(r.ticker)}</small></span><span class="sectorRankTrack"><i class="${cls(info?.value)}" style="width:${info?Math.max(2,Math.abs(info.value)/scale*100):0}%"></i></span><strong class="${cls(info?.value)}">${info?pct(info.value):'확인 대기'}</strong></button>`).join('')}</div>${current?`<div class="sectorRankDetail"><b>${esc(SECTOR_KO[current.r.ticker]||current.r.name)} · ${esc(current.r.ticker)}</b><p>${current.info?`${esc(current.info.base)} → ${esc(current.info.end)} · ${pct(current.info.value)}`:'해당 기간의 완료 종가 이력이 충분하지 않습니다.'}</p><p>최근 100거래일 추이 · ${esc(current.r.source||'원천 미확인')}</p>${sparkline(current.r)}<p>ETF 가격 변동이며 분배금은 반영하지 않습니다. 테마 ETF는 해당 산업 전체와 다를 수 있습니다.</p></div>`:''}</section>`;
}
function attachRank(panel){
 const host=q('#sectorRankHost',panel);if(!host)return;
 host.innerHTML=rankView();
 host.onclick=e=>{const btn=e.target.closest('button');if(!btn)return;
  if(btn.dataset.rankPeriod)rankPeriod=btn.dataset.rankPeriod;
  if(btn.dataset.rankScope){rankScope=btn.dataset.rankScope;rankSelected=null}
  if(btn.dataset.rankTicker)rankSelected=rankSelected===btn.dataset.rankTicker?null:btn.dataset.rankTicker;
  const attr=btn.dataset.rankPeriod?'rankPeriod':btn.dataset.rankScope?'rankScope':'rankTicker',val=btn.dataset[attr];
  host.innerHTML=rankView();host.querySelector(`[data-${attr.replace(/[A-Z]/g,c=>'-'+c.toLowerCase())}="${val}"]`)?.focus();
 };
}

function render(){
 const panel=q('#sectors');if(!panel||!DATA)return;
 if(!panel.dataset.themeToggleBound){panel.dataset.themeToggleBound='1';panel.addEventListener('toggle',e=>{if(!e.target.matches?.('details[data-theme]'))return;const key=e.target.dataset.theme;if(e.target.open)openThemes.add(key);else openThemes.delete(key)},true)}
 const s=DATA.summary||{},rows=classicRows(),rank=ranked20(rows),leaders=rank.slice(0,3),laggards=rank.slice(-3).reverse(),quality=DATA.quality||{};
 const spread20=n(s.growth_defense_spread_20d_pct)??growthDefense20(rows),warning=n(quality.fetch_error_count)>0;
 panel.innerHTML=`<div class="obsSectorHead"><div><div class="obsSectorTitle">송팀장 Sector Observatory</div><div class="meta">완료 일봉 기준 · 수익률 구간을 1일·5일·10일·20일·50일·100일로 통일</div></div><div class="obsSectorBadge">국내·해외 ETF · 완료 일봉</div></div>
 <div id="sectorRankHost"></div>
 <div class="obsSectorKpis"><div class="obsSectorKpi"><span>기준일</span><b>${esc(DATA.completed_cutoffs?'KR '+DATA.completed_cutoffs.KR+' / US '+DATA.completed_cutoffs.US:DATA.as_of_date||'—')}</b></div><div class="obsSectorKpi"><span>MA20 상회 · 11개 섹터</span><b>${esc(s.classic_above_ma20??'—')} / ${esc(s.classic_count??11)}</b></div><div class="obsSectorKpi"><span>20일 RS 강세</span><b>${esc(leaders[0]?.ticker||'—')} ${pct(leaders[0]?.value)}</b></div><div class="obsSectorKpi"><span>20일 RS 약세</span><b>${esc(laggards[0]?.ticker||'—')} ${pct(laggards[0]?.value)}</b></div><div class="obsSectorKpi"><span>성장-방어 20일</span><b class="${cls(spread20)}">${pct(spread20)}</b></div></div>
 <div class="obsSectorGrid"><div><section class="obsSectorCard"><h3>S&P 500 섹터 상대강도</h3><div class="meta">1·5·10·20·50·100 거래일 수익률 · 20일 SPY 대비 상대강도 순 정렬</div>${classicTable(rows)}</section><section class="obsSectorCard" style="margin-top:12px"><h3>테마·업종·국가 ETF</h3><div class="meta">6개 기간 수익률 + 최근 100거래일 스파크라인으로 테마·업종·국가별 방향과 속도를 함께 확인합니다.</div>${themeHtml()}</section></div><div><section class="obsSectorCard"><h3>20일 RS Ranking</h3><div class="meta">SPY 20거래일 성과 대비 상대강도 · 섹터 회전 확인</div><div class="obsSectorChart"><canvas id="sectorRsChart"></canvas></div></section><section class="obsSectorCard" style="margin-top:12px"><h3>리더 / 래거드</h3><div class="obsSectorLeader"><span><span class="obsSectorRank">L</span>강세 TOP3</span><b class="up">${esc(leaderText(leaders))}</b></div><div class="obsSectorLeader"><span><span class="obsSectorRank">W</span>약세 TOP3</span><b class="down">${esc(leaderText(laggards))}</b></div><div class="obsSectorLeader"><span>SPY 20일</span><b class="${cls(benchRet('SPY',20))}">${pct(benchRet('SPY',20))}</b></div><div class="obsSectorLeader"><span>QQQ 20일</span><b class="${cls(benchRet('QQQ',20))}">${pct(benchRet('QQQ',20))}</b></div><div class="obsSectorQuality ${warning?'warn':''}">${warning?'일부 Yahoo 일봉 수집 실패가 있어 직전 검증값으로 대체된 ETF가 있습니다.':'전체 섹터 ETF가 최신 완료 일봉으로 수집되었습니다.'}<br>가격 확인 ${esc(s.priced_count??0)}/${esc(s.total_count??0)} · fetch error ${esc(quality.fetch_error_count??0)} · source: ${esc(DATA.source_contract||'Yahoo public daily')}</div></section></div></div>`;
 attachRank(panel);
 try{drawRsChart(rows)}catch(e){STATE.chart_error=String(e);STATE.status='ACTIVE_DEGRADED';console.warn('sector RS chart render failed',e);const host=q('#sectorRsChart')?.parentElement;if(host)host.innerHTML='<div class="obsSectorLoading" style="padding:22px 8px">RS 차트만 표시하지 못했습니다. 표·ETF 데이터는 정상입니다.</div>'}
 if(STATE.status!=='ACTIVE_DEGRADED')STATE.status='ACTIVE';STATE.loaded=true;STATE.error=null;STATE.rendered_at=new Date().toISOString();
}

async function load(){
 if(STATE.loaded&&DATA){render();return DATA}
 if(STATE.loading)return null;
 STATE.loading=true;STATE.status='LOADING';
 const box=q('#sectors .obsSectorLoading');if(box)box.textContent='섹터 ETF 완료 일봉을 불러오는 중입니다…';
 try{
   const d=await window.JjooniDataReads.read('./data/sector-etf.json');if(d?.schema!=='JJOONI_OBSERVATORY_SECTOR_ETF_V1')throw new Error('sector-etf schema mismatch');
   DATA=d;render();return d;
 }catch(e){STATE.status='ERROR';STATE.error=String(e);const panel=q('#sectors');if(panel)panel.innerHTML='<div class="obsSectorLoading">섹터 ETF 원천 데이터를 불러오지 못했습니다. 새로고침 후 다시 확인해 주세요.</div>';console.error(e);return null}
 finally{STATE.loading=false}
}

function onTab(e){const b=e.target?.closest?.('button[data-tab="sectors"]');if(!b)return;setTimeout(load,0)}
function boot(){if(!ensureShell())return;const tabs=q('#tabs');if(tabs&&!tabs.dataset.sectorEtfBound){tabs.dataset.sectorEtfBound='1';tabs.addEventListener('click',onTab)}STATE.status='READY_LAZY'}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();

