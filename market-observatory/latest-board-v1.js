(()=>{
'use strict';
const ITEMS=[
  {k:'KOSPI',label:'KOSPI',kind:'pct',digits:2,group:'한국'},
  {k:'KOSDAQ',label:'KOSDAQ',kind:'pct',digits:2,group:'한국'},
  {k:'RUSSELL2000',label:'Russell 2000',kind:'pct',digits:2,group:'미국'},
  {k:'DOW',label:'Dow',kind:'pct',digits:2,group:'미국'},
  {k:'SP500',label:'S&P 500',kind:'pct',digits:2,group:'미국'},
  {k:'NASDAQCOMPOSITE',label:'NASDAQ 종합',kind:'pct',digits:2,group:'미국'},
  {k:'NASDAQ100',label:'NASDAQ 100',kind:'pct',digits:2,group:'미국'},
  {k:'VIX',label:'VIX',kind:'pct',digits:2,group:'위험'},
  {k:'FEAR_GREED',label:'Fear & Greed',kind:'pts',digits:0,suffix:'/100',group:'심리'},
  {k:'USDKRW',label:'USD/KRW',kind:'pct',digits:2,group:'환율'},
  {k:'USDJPY',label:'USD/JPY',kind:'pct',digits:2,group:'환율'},
  {k:'JPYKRW',label:'JPY/KRW',kind:'pct',digits:3,group:'환율'},
  {k:'DXY',label:'DXY',kind:'pct',digits:2,group:'환율'},
  {k:'US3M',label:'미국 3개월',kind:'bp',digits:2,suffix:'%',group:'금리'},
  {k:'JP30Y',label:'일본 30Y',kind:'bp',digits:3,suffix:'%',group:'금리'},
  {k:'BTCUSD',label:'비트코인',kind:'pct',digits:2,prefix:'$',group:'암호화폐'},
  {k:'ETHUSD',label:'이더리움',kind:'pct',digits:2,prefix:'$',group:'암호화폐'},
  {k:'US2Y',label:'미국 2Y',kind:'bp',digits:2,suffix:'%',group:'금리'},
  {k:'US10Y_OFFICIAL',seriesKey:'US10Y',label:'미국 10Y',kind:'bp',digits:3,suffix:'%',group:'금리'},
  {k:'US30Y_OFFICIAL',seriesKey:'US30Y',label:'미국 30Y',kind:'bp',digits:3,suffix:'%',group:'금리'},
  {k:'KR3Y',label:'한국 3Y',kind:'bp',digits:3,suffix:'%',group:'금리'},
  {k:'KR10Y',label:'한국 10Y',kind:'bp',digits:3,suffix:'%',group:'금리'},
  {k:'JP2Y',label:'일본 2Y',kind:'bp',digits:3,suffix:'%',group:'금리'},
  {k:'JP10Y',label:'일본 10Y',kind:'bp',digits:3,suffix:'%',group:'금리'},
  {k:'US_2S10S',label:'US 2s10s',kind:'bp',digits:3,suffix:'%',group:'스프레드'},
  {k:'KR_3S10S',label:'KR 3s10s',kind:'bp',digits:3,suffix:'%',group:'스프레드'},
  {k:'JP_2S10S',label:'JP 2s10s',kind:'bp',digits:3,suffix:'%',group:'스프레드'},
  {k:'WTI',label:'WTI',kind:'pct',digits:2,prefix:'$',group:'에너지'},
  {k:'BRENT',label:'Brent',kind:'pct',digits:2,prefix:'$',group:'에너지'},
  {k:'NATGAS',label:'Natural Gas',kind:'pct',digits:3,prefix:'$',group:'에너지'},
  {k:'GOLD',label:'Gold',kind:'pct',digits:1,prefix:'$',group:'금속'},
  {k:'SILVER',label:'Silver',kind:'pct',digits:2,prefix:'$',group:'금속'},
  {k:'COPPER',label:'Copper',kind:'pct',digits:3,prefix:'$',group:'금속'}
];
const BY_KEY=Object.fromEntries(ITEMS.map(x=>[x.k,x]));
const INDEX_KEYS=['KOSPI','KOSDAQ','SP500','NASDAQCOMPOSITE','NASDAQ100','DOW','RUSSELL2000'];
const OVERVIEW_GROUPS=[
  {key:'indices',label:'① 지수 점검',sub:'미국 주요 지수 → VIX → 국내 지수·투자심리',keys:['RUSSELL2000','DOW','SP500','NASDAQCOMPOSITE','NASDAQ100','VIX','KOSPI','KOSDAQ','FEAR_GREED']},
  {key:'tripod',label:'② TRI-POD',sub:'현재 전략 상태와 핵심 위험입력',special:'tripod'},
  {key:'macro',label:'③ 매크로 점검',sub:'원자재 · 금리 · 암호화폐 · 환율',special:'macro'},
  {key:'week',label:'④ 이번 주 관전 포인트',sub:'이번 주 월요일~일요일 · KST 기준',special:'week'}
];
const OVERVIEW_MACRO_GROUPS=[
  {key:'commodity',label:'원자재',keys:['WTI','BRENT','NATGAS','GOLD','SILVER','COPPER']},
  {key:'rates',label:'금리',keys:['US3M','US2Y','US10Y_OFFICIAL','US30Y_OFFICIAL','JP2Y','JP10Y','JP30Y','KR3Y','KR10Y']},
  {key:'crypto',label:'암호화폐 · 현물 USD · 24시간 거래',keys:['BTCUSD','ETHUSD']},
  {key:'fx',label:'환율',keys:['DXY','USDJPY','USDKRW','JPYKRW']},
  {key:'spreads',label:'장단기 스프레드',keys:['US_2S10S','KR_3S10S','JP_2S10S']}
];

const COMPARES={
  D1:{label:'일간',mode:'prev'},
  W1:{label:'주간',days:7},
  M1:{label:'전월',months:1},
  M2:{label:'2개월 전',months:2},
  Y1:{label:'전년',years:1}
};
let compareKey='D1';
const TAB_CONFIG={
  overview:{title:'시장 한눈에 보기',sub:'지수 → TRI-POD → 매크로 → 이번 주 일정',groups:OVERVIEW_GROUPS},
  indices:{title:'주요 지수',sub:'일간: 최근 시세 vs 전일 종가 · 주간 이상·차트: 완료 종가 기준',keys:INDEX_KEYS},
  rates:{title:'금리 주요 지표',sub:'수집 시각은 파일 갱신 시간이며 각 카드의 관측 기준일과 다릅니다 · 미국 10·30년=Cboe 금리지수 · 2년·3개월=미 재무부 공식 일별 · 한국=ECOS · 일본=MOF',keys:['US2Y','US10Y_OFFICIAL','US30Y_OFFICIAL','KR3Y','KR10Y','JP2Y','JP10Y','US_2S10S','KR_3S10S','JP_2S10S']},
  fx:{title:'환율 주요 지표',sub:'Yahoo daily close · 다른 제공사의 마감 cutoff와 소폭 차이 가능',keys:['USDKRW','USDJPY','JPYKRW','DXY']},
  energy:{title:'원자재 주요 지표',sub:'Yahoo 연속선물 daily close · 거래소 settlement/특정 월물과 직접 동일값 아님',keys:['WTI','BRENT','NATGAS','GOLD','SILVER','COPPER']},
  sectors:{title:'섹터·ETF 주요 지표',sub:'송팀장 Sector Observatory의 상대강도·breadth·rotation 요약',special:'sector'},
  tripod:{title:'TRI-POD 주요 입력',sub:'NASDAQ-100 레짐·VIX10·Drawdown·현재 목표노출',special:'tripod'},
  calendar:{title:'경제일정 주요 지표',sub:'오늘·향후 7일·다음 중요 이벤트 중심',special:'calendar'}
};
const fmt=(v,d)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
function seriesOf(item){if(typeof DATA==='undefined'||!DATA?.series)return[];const a=DATA.series[item.seriesKey||item.k]||[];if(a.length)return a;return item.fallback?(DATA.series[item.fallback]||[]):[]}
function utcDate(s){const d=new Date(String(s||'').slice(0,10)+'T00:00:00Z');return Number.isNaN(d.getTime())?null:d}
function refPoint(s,last,key){if(s.length<2)return null;const cfg=COMPARES[key]||COMPARES.D1;if(cfg.mode==='prev')return s[s.length-2]||null;const d=utcDate(last?.date);if(!d)return s[s.length-2]||null;if(cfg.days)d.setUTCDate(d.getUTCDate()-cfg.days);if(cfg.months)d.setUTCMonth(d.getUTCMonth()-cfg.months);if(cfg.years)d.setUTCFullYear(d.getUTCFullYear()-cfg.years);const target=d.toISOString().slice(0,10);for(let i=s.length-2;i>=0;i--){if(String(s[i]?.date||'')<=target)return s[i]}return null}
function stat(item,key=compareKey){const s=seriesOf(item).filter(p=>p?.date&&p.value!==null&&p.value!==undefined&&String(p.value).trim()!==''&&typeof p.value!=='boolean'&&Number.isFinite(Number(p.value))),last=s[s.length-1];const quote=key==='D1'&&typeof window!=='undefined'?window.__JJOONI_OBSERVATORY_QUOTES?.get(item.k):null;if(quote&&(!last||quote.session_date>=last.date))return {value:quote.value,date:quote.session_date,change:quote.change_pct,refDate:null,refValue:quote.previous_close,intraday:quote};if(!last)return null;const ref=refPoint(s,last,key);let ch=null;if(ref&&Number.isFinite(Number(ref.value))&&Number.isFinite(Number(last.value))){ch=item.kind==='bp'?(Number(last.value)-Number(ref.value))*100:item.kind==='pts'?(Number(last.value)-Number(ref.value)):(Number(ref.value)!==0?(Number(last.value)/Number(ref.value)-1)*100:null)}return{value:Number(last.value),date:last.date,change:ch,refDate:ref?.date||null,refValue:ref?Number(ref.value):null}}
function arrow(v){return v==null?'':v>0?'▲':v<0?'▼':'■'}
function cls(v){return v==null?'flat':v>0?'up':v<0?'down':'flat'}
function changeText(item,v){const label=COMPARES[compareKey]?.label||'비교';if(v==null||!Number.isFinite(v))return `${label} 대비 —`;if(item.kind==='bp')return `${label} ${arrow(v)} ${Math.abs(v).toFixed(1)}bp`;if(item.kind==='pts')return `${label} ${arrow(v)} ${Math.abs(v).toFixed(1)}pt`;return `${label} ${arrow(v)} ${Math.abs(v).toFixed(2)}%`}
function activeTab(){return document.querySelector('#tabs button.on[data-tab]')?.dataset.tab||'overview'}
function ensureIndexShell(){const tabs=document.getElementById('tabs'),main=document.querySelector('main.wrap');if(!tabs||!main)return false;let tab=tabs.querySelector('button[data-tab="indices"]');if(!tab){tab=document.createElement('button');tab.type='button';tab.dataset.tab='indices';tab.textContent='주요 지수';const ref=tabs.querySelector('button[data-tab="rates"]');if(ref)tabs.insertBefore(tab,ref);else tabs.appendChild(tab)}let panel=document.getElementById('indices');if(!panel){panel=document.createElement('section');panel.className='panel';panel.id='indices';panel.innerHTML='<div class="grid obsIndexGrid"><div class="card"><h3>한국 주요 지수</h3><div class="meta">KOSPI · KOSDAQ</div><div class="chart"><canvas id="krIndexChart"></canvas></div></div><div class="card"><h3>미국 대표 지수</h3><div class="meta">S&P 500 · Dow · Russell 2000</div><div class="chart"><canvas id="usBroadIndexChart"></canvas></div></div><div class="card"><h3>미국 기술주 지수</h3><div class="meta">NASDAQ 종합 · NASDAQ 100</div><div class="chart"><canvas id="usTechIndexChart"></canvas></div></div></div>';const ref=main.querySelector('#rates');if(ref)main.insertBefore(panel,ref);else main.appendChild(panel)}return true}
function ensure(){ensureIndexShell();let host=document.getElementById('latestMarketBoard');if(host)return host;const nav=document.getElementById('tabs');if(!nav)return null;host=document.createElement('section');host.id='latestMarketBoard';host.className='latestBoardWrap';host.innerHTML='<div class="latestBoardHead"><div class="latestBoardTitleBox"><b id="latestBoardTitle">주요 지표</b><span id="latestBoardSub"></span></div><div class="latestBoardTools"><div id="latestCompare" class="latestCompare" aria-label="비교 기준"></div><span id="latestBoardGenerated"></span></div></div><div id="latestBoardGrid" class="latestBoardGrid"></div>';nav.insertAdjacentElement('afterend',host);return host}
function japaneseRateFreshness(item,s){
 if(item.kind!=='bp')return null;
 const data=typeof DATA!=='undefined'?DATA:null;
 const quality=data?.cross_market_freshness_quality||{};
 const q=quality[item.seriesKey||item.k]||quality[item.k.startsWith('JP')?'JP_RATES':item.k.startsWith('KR')?'KR_RATES':'US_RATES']||{};
 const observed=s?.date||'';
 const required=String(q.expected_latest_weekday||q.target_session||'').slice(0,10);
 const state=String(q.status||'').toUpperCase();
 const delayed=!!observed&&(['LAGGING','STALE','UNAVAILABLE'].includes(state)||(required&&observed<required));
 if(!delayed)return null;
 return {state:state||'LAGGING',observed,expected:required||null,fetchError:!!q.fetch_error};
}
function periodContext(item){const daily=stat(item,'D1'),weekly=stat(item,'W1');const lag=japaneseRateFreshness(item,daily);const unit=item.kind==='bp'?'bp':item.kind==='pts'?'pt':'%';const digits=item.kind==='bp'||item.kind==='pts'?1:2;const cell=(name,s)=>`<span class="${cls(s?.change)}" title="${esc(s?.refDate&&s?.date?`${s.refDate} → ${s.date}`:'비교 기준값 부족')}">${name} ${s?.change==null?'—':(s.change>0?'+':'')+s.change.toFixed(digits)+unit}</span>`;const dailyLabel=lag?'직전 관측일':'일간';return `<div class="latestTilePeriods" aria-label="관측일 기준 일간과 주간 변동폭">${cell(dailyLabel,daily)}${cell('주간',weekly)}</div>`}
function rateSourceWarning(item,s){
 const lag=japaneseRateFreshness(item,s);
 if(!lag)return '';
 const basis=lag.expected?`${lag.expected} 자료 미확인`:'최근 거래일 자료 지연';
 const note=lag.fetchError?'원천 조회 실패 · 이전 검증값 유지':'원천 최신 발표 확인 대기 · 이전 검증값 유지';
 return `<div class="latestRateLag" role="status"><b>자료 지연 · ${esc(basis)}</b><small>실제 관측 ${esc(lag.observed)} · ${esc(note)}<br>아래 등락은 직전 관측일 기준이며 오늘 등락이 아닙니다.</small></div>`;
}
function rateDateContext(item,s){if(item.kind!=='bp'||!s)return '';const region=item.k.startsWith('US')?'미국 현지':item.k.startsWith('JP')?'일본 현지':'한국';return `<div class="latestCryptoBasis">${region} ${esc(s.date)} 기준 · 일별 확정값<br>실시간 금리가 아닙니다.</div>`}
function cryptoQuoteContext(item){if(!['BTCUSD','ETHUSD'].includes(item.k))return '';const q=(typeof DATA!=='undefined'&&DATA?.crypto_market?.[item.k])||{};const when=q.quote_as_of_kst?String(q.quote_as_of_kst).slice(0,16).replace('T',' ')+' KST':'시각 미확인';const stamp=Date.parse(q.quote_as_of_kst||'');const age=Date.now()-stamp;const fresh=Number.isFinite(stamp)&&age>=-60000&&age<=3600000;const label=q.status==='LIVE'&&fresh?'수집 시점 시세':q.status==='LIVE'||q.status==='STALE'?'이전 시세 · 갱신 지연':'시세 확인 중';return `<div class="latestCryptoBasis">${esc(when)} · ${esc(label)}<br>등락 기준: UTC 일봉</div>`}
function primaryChange(item,s){
 const lag=compareKey==='D1'&&japaneseRateFreshness(item,s);
 const label=s?.intraday?(['BTCUSD','ETHUSD'].includes(item.k)?'전일 기준값 대비':'전일 종가 대비'):lag?'직전 관측일 대비':(COMPARES[compareKey]?.label||'비교')+' 대비';
 const v=s?.change,unit=item.kind==='bp'?'bp':item.kind==='pts'?'pt':'%',digits=item.kind==='pct'?2:1;
 const value=v==null||!Number.isFinite(v)?'—':(v>0?'+':'')+v.toFixed(digits)+unit;
 return `<div class="latestPrimaryChange ${cls(v)}"><span class="latestPrimaryLabel">${esc(label)}</span><b class="latestPrimaryValue">${esc(value)}</b></div>`;
}
function standardTile(item){const s=stat(item);const val=s?`${item.prefix||''}${fmt(s.value,item.digits)}${item.suffix||''}`:'—';const ch=s?changeText(item,s.change):'확인 가능한 값 없음';const source=item.sourceNote||(item.seriesKey?'Cboe 금리지수 · Yahoo 일별 · 공식 금리와 별도 원천':item.k==='US_2S10S'?'미 재무부 공식 10년 − 2년 · 화면의 Cboe 10년과 별도 원천':(['US3M','US2Y'].includes(item.k)?'미 재무부 공식 일별 · 원천 소수 2자리':''));const dates=s?.intraday?new Date(s.intraday.observed_at).toLocaleString('sv-SE',{timeZone:'Asia/Seoul'}).slice(5,19)+' KST':s?.refDate?`${s.refDate} → ${s.date}`:(s?.date||'—');return `<div class="latestTile latestChangeFirst" data-comparison="${esc(compareKey)}" data-metric="${esc(item.k)}" role="button" tabindex="0" aria-haspopup="dialog" aria-label="${esc(item.label)} 추이 보기"><div class="latestTileTop"><span>${esc(item.group)}</span><b>${esc(item.label)}</b></div>${primaryChange(item,s)}<strong class="latestLevelValue" aria-label="현재 값">${esc(val)}</strong><div class="latestTileFoot">${!s||!['D1','W1'].includes(compareKey)?`<span class="${cls(s?.change)}">${esc(ch)}</span>`:''}<time>${esc(dates)}</time></div>${rateDateContext(item,s)}${periodContext(item)}${rateSourceWarning(item,s)}${s?.intraday?intradayContext(item,s.intraday):cryptoQuoteContext(item)}${source?`<div class="latestCryptoBasis">${esc(source)}</div>`:''}</div>`}
function intradayContext(item,q){const warning=/유지|지연$/.test(q.display_status||'');return `<div class="latestQuoteContext ${warning?'quoteWarning':''}"><b>${esc(q.display_status)}</b><span>Yahoo 시세 · 실제 관측 시각 위 표시</span>${['BTCUSD','ETHUSD'].includes(item.k)?'<span>UTC 일간 기준 · 24시간 수익률과 다름</span>':''}<span>차트·주간 비교·TRI-POD는 완료 종가 기준</span></div>`}
function ma250Display(value){return fmt(value,2);}
function ma250Change(t,scale=1){
 const current=t.ma250,previous=t.previous_ma250;
 if(current==null||previous==null||current===''||previous===''||!Number.isFinite(Number(current))||!Number.isFinite(Number(previous))||Number(previous)<=0)return null;
 const delta=Number(current)-Number(previous),sign=delta>0?'+':delta<0?'-':'';
 return {points:sign+fmt(Math.abs(delta*scale),2),percent:sign+fmt(Math.abs(delta/Number(previous)*100),3),tone:cls(delta)};
}
function tripodBipodLevel(t){
 if(t?.ndx==null||t.drawdown_52w_pct==null)return null;
 const px=Number(t.ndx),dd=Number(t.drawdown_52w_pct);
 return Number.isFinite(px)&&px>0&&Number.isFinite(dd)&&dd>-100?px/(1+dd/100)*.91:null;
}
// BIPOD is based on the rolling 252-trading-close high. For the reference
// comparison show last week's completed close, never the previous trading day.
function tripodPreviousWeekRow(t){
 const current=utcDate(t?.session_date||t?.date);
 if(!current)return null;
 const monday=new Date(current);
 monday.setUTCDate(monday.getUTCDate()-((monday.getUTCDay()+6)%7));
 const prevMonday=new Date(monday);prevMonday.setUTCDate(prevMonday.getUTCDate()-7);
 const from=prevMonday.toISOString().slice(0,10),to=monday.toISOString().slice(0,10);
 const history=typeof DATA!=='undefined'?(DATA?.tripod_history||[]):[];
 return history.filter(row=>row?.date>=from&&row.date<to&&tripodBipodLevel(row)!=null)
  .sort((a,b)=>String(a.date).localeCompare(String(b.date))).pop()||null;
}
function tripodBipodChange(t){
 const prior=tripodPreviousWeekRow(t);
 if(!prior)return null;
 const change=ma250Change({ma250:tripodBipodLevel(t),previous_ma250:tripodBipodLevel(prior)});
 return change?{...change,label:'전주',refDate:prior.date}:null;
}
function tripodPriceDistance(level,price){return level==null||price==null||price<=0?'현재 종가 대비 —':`현재 종가 대비 ${level>=price?'+':''}${fmt((level/price-1)*100,2)}%`;}
function customTile(group,label,value,foot='',tone='flat',time='',change=null,note=''){const key={REGIME:'TRIPOD_TREND',TARGET:'TRIPOD_TARGET',INDEX:'NASDAQ100',TREND:'TRIPOD_MA',FALL:'TRIPOD_FALL',RISE:'TRIPOD_RISE',BIPOD:'TRIPOD_BIPOD',NOPOD:'TRIPOD_FALL',RISK:'TRIPOD_VIX',DRAWDOWN:'TRIPOD_DD'}[group];return `<div class="latestTile" ${key?`data-metric="${key}" role="button" tabindex="0" aria-haspopup="dialog" aria-label="${esc(label)} 추이 보기"`:''}><div class="latestTileTop"><span>${esc(group)}</span><b>${esc(label)}</b></div><strong class="${esc(tone)}">${esc(value)}</strong>${change?`<div class="latestMaChange ${esc(change.tone)}"><span title="${esc(change.refDate?'기준: '+change.refDate:'')}">${esc(change.label||'전일')} ${esc(change.points)}pt</span><span>(${esc(change.percent)}%)</span></div>`:''}<div class="latestTileFoot"><span class="${esc(tone)}">${esc(foot||'')}</span><time>${esc(time||'')}</time></div>${note?`<div class="latestCryptoBasis">${esc(note)}</div>`:''}</div>`}
function dataGenerated(){const d=typeof DATA!=='undefined'?DATA:null;const clock=[d?.generated_kst,d?.supplemental_refreshed_kst].filter(x=>Number.isFinite(Date.parse(x))).sort((a,b)=>Date.parse(b)-Date.parse(a))[0];return String(clock||'').replace('T',' ').slice(0,16)}
function renderCompare(show=true){const host=ensure(),box=host?.querySelector('#latestCompare');if(!box)return;box.style.display=show?'flex':'none';if(!show)return;box.innerHTML=Object.entries(COMPARES).map(([k,v])=>`<button type="button" data-compare="${k}" class="${k===compareKey?'on':''}">${esc(v.label)}</button>`).join('');box.querySelectorAll('button[data-compare]').forEach(b=>b.onclick=()=>{compareKey=b.dataset.compare;renderBoard()})}
function setHeader(title,sub,generated,showCompare=true){const host=ensure();if(!host)return;const t=host.querySelector('#latestBoardTitle'),s=host.querySelector('#latestBoardSub'),g=host.querySelector('#latestBoardGenerated');if(t)t.textContent=title;if(s)s.textContent=showCompare?`${sub} · 선택 기준: ${COMPARES[compareKey]?.label||'일간'} 대비`:sub;if(g)g.textContent=generated?`수집 ${generated} KST`:'';renderCompare(showCompare)}
function setGrid(html,count,grouped=false){const host=ensure();if(!host)return;host.dataset.tab=activeTab();const grid=host.querySelector('#latestBoardGrid');grid.classList.toggle('grouped',grouped);grid.innerHTML=html;grid.style.gridTemplateColumns=grouped?'1fr':(count>0&&count<=5?`repeat(${count},minmax(0,1fr))`:'')}
function groupHtml(g){if(g.special==='tripod')return overviewGroup(g,`<div class="latestGroupGrid">${tripodTiles().join('')}</div>`);if(g.special==='macro')return overviewGroup(g,`<div class="overviewMacroGrid">${OVERVIEW_MACRO_GROUPS.map(x=>`<div class="overviewMacroBlock"><h4>${esc(x.label)}</h4><div class="latestGroupGrid">${x.keys.map(k=>standardTile(BY_KEY[k])).join('')}</div></div>`).join('')}</div>`);if(g.special==='week')return overviewGroup(g,overviewWeekHtml());const items=(g.keys||[]).map(k=>BY_KEY[k]).filter(Boolean);return `<section class="latestGroup latestGroup-${esc(g.key)}" data-overview-group="${esc(g.key)}"><div class="latestGroupHead"><div><b>${esc(g.label)}</b><span>${esc(g.sub||'')}</span></div><em>${items.length}개</em></div><div class="latestGroupGrid">${items.map(standardTile).join('')}</div></section>`}
function pulseChips(items){const p=document.getElementById('pulse');if(!p)return;p.innerHTML=items.map(x=>`<span class="chip">${esc(x)}</span>`).join('')}
function overviewGroup(g,html){return `<section class="latestGroup latestGroup-${esc(g.key)}" data-overview-group="${esc(g.key)}"><div class="latestGroupHead"><div><b>${esc(g.label)}</b><span>${esc(g.sub||'')}</span></div></div>${html}</section>`}
let overviewCalendarState='idle';
function overviewWeekHtml(){
 if(typeof CAL==='undefined'||!CAL){
  if(overviewCalendarState==='idle'&&typeof loadCalendar==='function'){
   overviewCalendarState='loading';loadCalendar().then(()=>{overviewCalendarState='loaded';if(activeTab()==='overview')renderBoard()}).catch(()=>{overviewCalendarState='error';if(activeTab()==='overview')renderBoard()});
  }
  return `<div class="overviewWeekEmpty">${overviewCalendarState==='error'?'일정을 불러오지 못했습니다. 경제일정 탭에서 다시 확인해 주세요.':'이번 주 주요 일정을 불러오는 중입니다.'}</div>`;
 }
 const today=kstDay(),start=new Date(today+'T00:00:00Z');start.setUTCDate(start.getUTCDate()-((start.getUTCDay()+6)%7));const end=new Date(start);end.setUTCDate(end.getUTCDate()+7);
 const from=start.toISOString().slice(0,10),to=end.toISOString().slice(0,10);
 const rows=(CAL.events||[]).filter(e=>{const d=String(e.datetime_kst||e.date||'').slice(0,10);return d>=from&&d<to&&Number(e.importance||0)>=2}).sort((a,b)=>String(a.datetime_kst||a.date).localeCompare(String(b.datetime_kst||b.date)));
 const heading=`<div class="overviewWeekMeta">${esc(from)} 시작 주 · 중요도 ★★ 이상 ${rows.length}건 · 일정 원천 ${esc(String(CAL.generated_kst||'').slice(0,16).replace('T',' '))} KST</div>`;
 if(!rows.length)return heading+'<div class="overviewWeekEmpty">이번 주에 등록된 주요 일정이 없습니다.</div>';
 return heading+`<div class="overviewWeekTable"><div class="overviewWeekRow head"><span>날짜</span><span>시각</span><span>발표·이벤트</span></div>${rows.map(e=>{const raw=String(e.datetime_kst||e.date||'');const day=raw.slice(0,10);const clock=e.time_status==='TBD'?'미정':raw.includes('T')?raw.slice(11,16):'종일';return `<div class="overviewWeekRow" data-open-calendar role="button" tabindex="0" aria-label="${esc(e.title)} 일정 보기"><span>${esc(day.slice(5))}</span><span>${esc(clock)}</span><div><b>${esc(e.title)}</b><small>${esc(e.country||'')} · ${'★'.repeat(Math.min(3,Number(e.importance)||1))}</small></div></div>`}).join('')}</div>`;
}
function renderStandard(tab,cfg){setHeader(cfg.title,cfg.sub,dataGenerated(),true);if(cfg.groups){setGrid(cfg.groups.map(groupHtml).join(''),cfg.groups.length,true)}else{const items=(cfg.keys||[]).map(k=>BY_KEY[k]).filter(Boolean);setGrid(items.map(standardTile).join(''),items.length,false)}const pulseKeys=tab==='overview'?['SP500','NASDAQ100','KOSPI','US10Y_OFFICIAL','USDKRW','VIX','WTI']:(cfg.keys||[]).slice(0,7);pulseChips(pulseKeys.map(k=>{const i=BY_KEY[k],s=i?stat(i):null;return `${i?.label||k} ${s?`${i?.prefix||''}${fmt(s.value,i?.digits??2)}${i?.suffix||''}`:'—'}`}));window.__JJOONI_OBSERVATORY_QUOTES?.paintSummary?.()}
function rowsFor(keys){const map=new Map();if(typeof DATA==='undefined'||!DATA?.series)return[];for(const k of keys){const item=BY_KEY[k];for(const p of seriesOf(item||{k})){if(!p?.date)continue;if(!map.has(p.date))map.set(p.date,{date:p.date});map.get(p.date)[k]=p.value}}return[...map.values()].sort((a,b)=>String(a.date).localeCompare(String(b.date)))}
function renderIndexPanel(){if(activeTab()!=='indices'||typeof window.chart!=='function')return;const kr=rowsFor(['KOSPI','KOSDAQ']),broad=rowsFor(['SP500','DOW','RUSSELL2000']),tech=rowsFor(['NASDAQCOMPOSITE','NASDAQ100']);window.chart('krIndexChart',kr.map(x=>x.date),[{label:'KOSPI',data:kr.map(x=>x.KOSPI)},{label:'KOSDAQ',data:kr.map(x=>x.KOSDAQ)}]);window.chart('usBroadIndexChart',broad.map(x=>x.date),[{label:'S&P 500',data:broad.map(x=>x.SP500)},{label:'Dow',data:broad.map(x=>x.DOW)},{label:'Russell 2000',data:broad.map(x=>x.RUSSELL2000)}]);window.chart('usTechIndexChart',tech.map(x=>x.date),[{label:'NASDAQ 종합',data:tech.map(x=>x.NASDAQCOMPOSITE)},{label:'NASDAQ 100',data:tech.map(x=>x.NASDAQ100)}])}
let SECTOR_DATA=null,SECTOR_PROMISE=null;
function loadSector(){if(SECTOR_DATA)return Promise.resolve(SECTOR_DATA);if(SECTOR_PROMISE)return SECTOR_PROMISE;SECTOR_PROMISE=window.JjooniDataReads.read('./data/sector-etf.json').then(d=>{if(d?.schema!=='JJOONI_OBSERVATORY_SECTOR_ETF_V1')throw new Error('sector schema');SECTOR_DATA=d;return d}).finally(()=>{SECTOR_PROMISE=null});return SECTOR_PROMISE}
function renderSector(){const d=SECTOR_DATA;if(!d){setHeader(TAB_CONFIG.sectors.title,TAB_CONFIG.sectors.sub,'',false);setGrid(customTile('SECTOR','데이터','불러오는 중','sector-etf lazy load'),1);pulseChips(['Sector ETF 로딩중']);loadSector().then(()=>{if(activeTab()==='sectors')renderSector()}).catch(()=>{if(activeTab()==='sectors'){setGrid(customTile('SECTOR','데이터','로딩 실패','다음 갱신 후 재시도','down'),1);pulseChips(['Sector ETF 로딩 실패'])}});return}
 const s=d.summary||{},lead=s.leaders_1m_rs_spy?.[0],lag=s.laggards_1m_rs_spy?.[0],spread=num(s.growth_defense_spread_1m_pct),spy=d.benchmarks?.SPY,qqq=d.benchmarks?.QQQ;
 const base=[
  customTile('BREADTH','MA20 상회',`${s.classic_above_ma20??'—'} / ${s.classic_count??11}`,'S&P 500 11개 섹터','flat',d.as_of_date||''),
  customTile('LEADER','1M RS 강세',lead?`${lead.ticker} ${lead.value>=0?'+':''}${Number(lead.value).toFixed(2)}%`:'—','vs SPY','up',d.as_of_date||''),
  customTile('LAGGARD','1M RS 약세',lag?`${lag.ticker} ${Number(lag.value).toFixed(2)}%`:'—','vs SPY','down',d.as_of_date||''),
  customTile('ROTATION','성장-방어',spread==null?'—':`${spread>=0?'+':''}${spread.toFixed(2)}%`,'1M spread',cls(spread),d.as_of_date||''),
  customTile('BENCH','SPY 1M',spy?.ret_1m_pct==null?'—':`${spy.ret_1m_pct>=0?'+':''}${Number(spy.ret_1m_pct).toFixed(2)}%`,'benchmark',cls(spy?.ret_1m_pct),d.as_of_date||''),
  customTile('BENCH','QQQ 1M',qqq?.ret_1m_pct==null?'—':`${qqq.ret_1m_pct>=0?'+':''}${Number(qqq.ret_1m_pct).toFixed(2)}%`,'benchmark',cls(qqq?.ret_1m_pct),d.as_of_date||'')
 ];
 const themes=(d.groups||[]).filter(g=>g.key!=='classic').map(g=>{
   const members=g.rows||[];
   const best=members.map(r=>({ticker:r.ticker,rs:num(r.rs_spy_20d_pct),ret:num(r.ret_20d_pct)})).sort((a,b)=>(b.rs??-999)-(a.rs??-999))[0];
   const value=best?`${best.ticker} ${best.ret==null?'':(best.ret>=0?'+':'')+best.ret.toFixed(1)+'%'}`:'—';
   return customTile('THEME',g.label||g.key,value,`${members.map(r=>r.ticker).join(' · ')} · 상세 아래`,cls(best?.ret),d.as_of_date||'');
 });
 const rows=[...base,...themes];
 setHeader(TAB_CONFIG.sectors.title,'S&P 500 11개 섹터 + 추가 테마·업종 ETF 전체 표시',String(d.generated_kst||'').replace('T',' ').slice(0,16),false);setGrid(rows.join(''),rows.length);pulseChips([`MA20 ${s.classic_above_ma20??'—'}/${s.classic_count??11}`,...((d.groups||[]).filter(g=>g.key!=='classic').map(g=>g.label||g.key))])}
// Distances use the certified signal snapshot, never intraday quotes or comparison controls.
function tripodNextModel(t,session,previous=null,previousWeek=null){
 const number=v=>v==null||v===''?null:(Number.isFinite(Number(v))?Number(v):null);
 const ndx=number(t.ndx),ma=number(t.ma250),vix=number(t.vix10),dd=number(t.drawdown_52w_pct);
 const date=t.session_date||t.date;
 if(t.ok!==true||!session||date!==session||ndx==null||ndx<=0||ma==null||ma<=0||vix==null||dd==null||t.vix_window_count!==10||!['상승','하락'].includes(t.regime))return {available:false,date};
 const target=t.regime==='상승'?(vix<28&&dd>=-9?'TQQQ 100%':'QQQ 50% + QLD 50%'):(vix<18?'QQQ 50% + QLD 50%':'현금 100%');
 if(target!==t.target)return {available:false,date};
 const high=ndx/(1+dd/100);
 if(!Number.isFinite(high)||high<=0)return {available:false,date};
 const priceGate=(key,label,boundary,op,met,note)=>({key,label,current:ndx,boundary,op,met,unit:'pt',distance:Math.abs(boundary/ndx-1)*100,note});
 const vixGate=(boundary,op,met)=>({key:'vix',label:'VIX 10일 평균',current:vix,boundary,op,met,unit:'pt',distance:Math.abs(boundary-vix),note:'일일 VIX가 아닌 종가 10개 평균'});
 const fall=priceGate('fall','하락 레짐 전환선 · 노팟 조건',ma*.95,'<',ndx<ma*.95,'MA250 × 0.95 미만 종가 · VIX10 ≥ 18이면 노팟(현금 100%), 18 미만이면 바이팟');
 const rise=priceGate('rise','상승 레짐 복귀',ma*1.01,'>',ndx>ma*1.01,'MA250 × 1.01 초과 종가');
 const drawdown=priceGate('drawdown','바이팟 전환선 · 고점 −9%',high*.91,'<',dd<-9,'낙폭 9% 초과 · 동일 고점 고정 시');
 drawdown.gapPctPoint=Math.abs(dd+9);
 // Compare the same rule boundaries across completed sessions, not MA250 itself.
 const previousMa=number(t.previous_ma250);
 if(previousMa!=null&&previousMa>0){fall.previousBoundary=previousMa*.95;rise.previousBoundary=previousMa*1.01;}
 if(previousWeek&&previousWeek.date<date){
  const px=number(previousWeek.ndx),decline=number(previousWeek.drawdown_52w_pct);
  const priorHigh=px!=null&&decline!=null?px/(1+decline/100):null;
  if(px>0&&priorHigh>0&&Number.isFinite(priorHigh)){
   drawdown.previousBoundary=priorHigh*.91;
   drawdown.previousBoundaryDate=previousWeek.date;
  }
 }

 const max=target==='TQQQ 100%',cash=target==='현금 100%';
 return {available:true,date,ndx,ma,vix,dd,target,max,cash,
  state:max?'최대 노출':cash?'현금 대기':'감속 · BIPOD·MONOPOD',
  title:max?'다음 스텝 · 감속 (BIPOD·MONOPOD)':cash?'다음 스텝 · 위험자산 재진입':'다음 스텝 · 최대 노출 복귀 / 현금 전환',
  gates:max?[drawdown,vixGate(28,'≥',vix>=28),fall]:cash?[vixGate(18,'<',vix<18),rise]:t.regime==='상승'?[{...drawdown,op:'≥',met:dd>=-9,note:'낙폭 9% 이내 회복' },vixGate(28,'<',vix<28),fall]:[rise,vixGate(18,'≥',vix>=18)],
  rule:max?'낙폭 9% 초과 또는 VIX10 ≥ 28이면 감속. 단, 지수가 MA250 × 0.95 미만이면 하락 레짐이 먼저 적용되며 VIX10 ≥ 18일 때 현금 전환.':cash?'하락 레짐에서 VIX10 < 18이면 감속 목표로 재진입. 상승 복귀는 NDX > MA250 × 1.01이며 VIX10·낙폭 조건에 따라 목표가 결정됩니다.':t.regime==='상승'?'최대 노출 복귀는 낙폭 9% 이내와 VIX10 < 28을 모두 충족해야 합니다. NDX < MA250 × 0.95이면 하락 레짐으로 전환 후 VIX10 18 기준을 적용합니다.':'하락 레짐에서 VIX10 ≥ 18이면 현금 전환. NDX > MA250 × 1.01이면 상승 복귀 후 VIX10 28·낙폭 9% 기준을 적용합니다.'};
}
function tripodNextHtml(t,session){
 const history=typeof DATA!=='undefined'?(DATA?.tripod_history||[]):[];
 const previous=[...history].reverse().find(row=>row?.date&&row.date<session);
 const previousWeek=tripodPreviousWeekRow(t);
 const m=tripodNextModel(t,session,previous,previousWeek);
 if(!m.available)return '<section class="tripodNext"><h3>다음 스텝 · 판정 보류</h3><p>동일 완료세션의 검증된 NDX·MA250·VIX10·낙폭 데이터가 필요합니다.</p></section>';
 const comparison=g=>{if(g.previousBoundary==null)return '';const delta=g.boundary-g.previousBoundary,sign=delta>0?'+':delta<0?'-':'',weekly=g.key==='drawdown',label=weekly?'전주':'전일',date=weekly&&g.previousBoundaryDate?' ('+g.previousBoundaryDate+')':'';return `<div class="tripodBoundaryChange"><span>${label} 기준${date} ${fmt(g.previousBoundary,2)}</span><span>${label} ${sign}${fmt(Math.abs(delta),2)}pt (${sign}${fmt(Math.abs(delta/g.previousBoundary*100),3)}%)</span></div>`};
 const distance=g=>g.met?'조건 충족':g.key==='vix'?`${fmt(g.distance,2)}pt ${g.op==='<'?'하락':'상승'} 필요${g.op==='<'?' · 경계 미만':''}`:`${fmt(g.distance,2)}% ${g.boundary<m.ndx?'하락':'상승'} 시 경계${g.gapPctPoint!=null?' · 낙폭 차이 '+fmt(g.gapPctPoint,2)+'%p':''}`;
 return `<section class="tripodNext" data-tripod-next="ready"><header><h3>${esc(m.title)}</h3><span>완료세션 ${esc(m.date)}</span></header><p><b>현재 ${esc(m.state)}</b> · ${esc(m.target)}</p><div class="tripodGateGrid">${m.gates.map(g=>`<article data-gate="${esc(g.key)}" role="button" tabindex="0" aria-haspopup="dialog" aria-label="${esc(g.label)} 추이 보기"><h4>${esc(g.label)}</h4><b>${esc(distance(g))}</b><p>현재 ${fmt(g.current,2)} → ${esc(g.op)} ${fmt(g.boundary,2)}</p>${comparison(g)}<small>${esc(g.note)}</small></article>`).join('')}</div><p>${esc(m.rule)}</p><small>판정: ${esc(t.action||'—')} · 종가 기준 조건까지의 거리이며 남은 일수 예측이 아닙니다. MA250·52주 고점·VIX10은 매일 변합니다. 상품 배수가 아닌 전략 전환 조건이며 계좌별 목표 구성은 다릅니다.</small></section>`;
}
function tripodTiles(){const t=(typeof DATA!=='undefined'&&DATA?.tripod_latest)||{},ndx=stat(BY_KEY.NASDAQ100),vix=stat(BY_KEY.VIX),ma=num(t.ma250),v10=num(t.vix10),dd=num(t.drawdown_52w_pct);const rows=[
 customTile('REGIME','현재 상태',t.regime||'—','상승 ×1.01 / 하락 ×0.95'),
 customTile('TARGET','목표 노출',t.target||'—','송팀장 Tri-Pod'),
 customTile('INDEX','NASDAQ 100',ndx?fmt(ndx.value,2):'—',ndx?changeText(BY_KEY.NASDAQ100,ndx.change):'전일 대비 —',cls(ndx?.change),ndx?.date||''),
 customTile('BIPOD','BIPOD 전환가격',fmt(tripodBipodLevel(t),2),tripodPriceDistance(tripodBipodLevel(t),t.ndx),'flat',t.date||'',tripodBipodChange(t),'52주 최고 종가 × 0.91 · 전주 마지막 거래일 대비 · VIX10 ≥ 28도 감속 조건'),
 customTile('NOPOD','NOPOD 가격선',ma==null?'—':fmt(ma*.95,2),tripodPriceDistance(ma==null?null:ma*.95,t.ndx),'flat',t.date||'',ma250Change(t,.95),'MA250 × 0.95 미만 + VIX10 ≥ 18 · 52주 낙폭 기준 아님'),
 customTile('TREND','MA250 · 계산 참고',ma250Display(t.ma250),'전환선 아님 · 250일 평균','flat',t.date||'',ma250Change(t)),
 customTile('RISK','VIX / VIX10',`${vix?fmt(vix.value,2):'—'} / ${v10==null?'—':fmt(v10,2)}`,'현재 / 10일 평균',cls(vix?.change),vix?.date||''),
 customTile('DRAWDOWN','52주 고점대비',dd==null?'—':`${dd.toFixed(2)}%`,ma!=null&&tripodBipodLevel(t)!=null?`52주 최고 종가 ${fmt(tripodBipodLevel(t)/.91,2)}pt · 낙폭`:'낙폭',dd<-9?'down':'flat',t.date||'')
 ];rows.push(tripodNextHtml(t,typeof DATA!=='undefined'?DATA.us_completed_session_date:null));return rows}
function renderTripod(){const rows=tripodTiles();setHeader(TAB_CONFIG.tripod.title,TAB_CONFIG.tripod.sub,dataGenerated(),false);setGrid(rows.join(''),rows.length);const t=(typeof DATA!=='undefined'&&DATA?.tripod_latest)||{};pulseChips([`Regime ${t.regime||'—'}`,`Target ${t.target||'—'}`])}

function kstDay(d=new Date()){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(d)}
function renderCalendarSummary(){if(typeof CAL==='undefined'||!CAL){setHeader(TAB_CONFIG.calendar.title,TAB_CONFIG.calendar.sub,'',false);setGrid(customTile('CALENDAR','일정','불러오는 중','economic-calendar lazy load'),1);pulseChips(['경제일정 로딩중']);return}
 const now=Date.now(),today=kstDay(),weekEnd=now+7*86400000,events=(CAL.events||[]).map(e=>({...e,_ts:Date.parse(e.datetime_kst||e.date||'')})).filter(e=>Number.isFinite(e._ts));const todayEvents=events.filter(e=>String(e.datetime_kst||e.date||'').startsWith(today));const upcoming=events.filter(e=>e._ts>=now).sort((a,b)=>a._ts-b._ts);const week=upcoming.filter(e=>e._ts<=weekEnd),weekHigh=week.filter(e=>(e.importance||0)>=3),next=upcoming[0],major=upcoming.find(e=>(e.importance||0)>=3);const time=e=>e?new Date(e._ts).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):'—';const rows=[
 customTile('TODAY','오늘 일정',`${todayEvents.length}건`,'KST 기준','flat',today),
 customTile('7D','향후 7일',`${week.length}건`,`★★★ ${weekHigh.length}건`),
 customTile('NEXT','다음 일정',next?.title||'예정 없음',next?`${next.country||''} · ${next.category||''}`:'','flat',time(next)),
 customTile('MAJOR','다음 ★★★',major?.title||'예정 없음',major?`${major.country||''} · ${major.category||''}`:'','flat',time(major))
 ];setHeader(TAB_CONFIG.calendar.title,TAB_CONFIG.calendar.sub,String(CAL.generated_kst||'').replace('T',' ').slice(0,16),false);setGrid(rows.join(''),rows.length);pulseChips([`오늘 ${todayEvents.length}건`,`7일 ${week.length}건`,`★★★ ${weekHigh.length}건`,major?`다음 ★★★ ${time(major)}`:'다음 ★★★ —'])}
function renderBoard(){const host=ensure();if(!host||typeof DATA==='undefined'||!DATA)return false;const tab=activeTab();if(!TAB_CONFIG[tab]){host.style.display='none';return true}host.style.display='';const cfg=TAB_CONFIG[tab]||TAB_CONFIG.overview;if(cfg.special==='sector')renderSector();else if(cfg.special==='tripod')renderTripod();else if(cfg.special==='calendar')renderCalendarSummary();else renderStandard(tab,cfg);if(tab==='indices')setTimeout(renderIndexPanel,0);return true}
function hookRender(){const base=window.render;if(typeof base!=='function'||base.__latestBoardHooked)return false;const w=function(){const r=base.apply(this,arguments);setTimeout(renderBoard,0);return r};w.__latestBoardHooked=true;window.render=w;return true}
function hookCalendar(){const base=window.renderCalendar;if(typeof base!=='function'||base.__latestBoardCalendarHooked)return false;const w=function(){const r=base.apply(this,arguments);if(['calendar','overview'].includes(activeTab()))setTimeout(renderBoard,0);return r};w.__latestBoardCalendarHooked=true;window.renderCalendar=w;return true}
function ensureOfficialMacroRuntime(){
  if(window.__JJOONI_OFFICIAL_MACRO_V1)return true;
  const existing=document.querySelector('script[data-official-macro-runtime]');
  if(existing && typeof tries!=='undefined' && tries<30)return false;
  if(existing)existing.remove();
  const s=document.createElement('script');s.dataset.officialMacroRuntime='1';s.src='./official-macro-v1.js?v=20261026-fallback';document.body.appendChild(s);return false
}
function bindTabs(){const tabs=document.getElementById('tabs');if(!tabs||tabs.dataset.latestBoardBound)return false;tabs.dataset.latestBoardBound='1';tabs.addEventListener('click',e=>{const b=e.target.closest('button[data-tab]');if(!b)return;[0,120,350,900].forEach(ms=>setTimeout(()=>{renderBoard();if(b.dataset.tab==='indices')renderIndexPanel()},ms))});return true}
const st=document.createElement('style');st.textContent=`
.latestBoardWrap{max-width:1180px;margin:12px auto 0;padding:0 14px}.latestBoardHead{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:9px}.latestBoardTitleBox{display:flex;align-items:baseline;gap:8px;min-width:0}.latestBoardTitleBox b{font-size:14px}.latestBoardTitleBox span{font-size:9px;color:#718096}.latestBoardTools{display:flex;align-items:center;justify-content:flex-end;gap:9px;min-width:0}.latestBoardTools>span{font-size:9px;color:#718096;white-space:nowrap}.latestCompare{display:flex;align-items:center;gap:4px;flex-wrap:wrap}.latestCompare:before{content:'비교';font-size:8px;font-weight:900;color:#98a2b3;margin-right:2px}.latestCompare button{border:1px solid #d9e1ea;background:#fff;color:#526071;border-radius:8px;padding:5px 7px;font-size:9px;font-weight:850;white-space:nowrap;cursor:pointer}.latestCompare button.on{background:#0b3b70;color:#fff;border-color:#0b3b70}.latestBoardGrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.latestBoardGrid.grouped{display:block}.latestGroup{background:#ffffff80;border:1px solid #e5ebf2;border-radius:15px;padding:10px;margin-bottom:10px}.latestGroup:last-child{margin-bottom:0}.latestGroupHead{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-bottom:7px}.latestGroupHead>div{display:flex;align-items:baseline;gap:7px;min-width:0}.latestGroupHead b{font-size:12px;color:#1d2b3d}.latestGroupHead span{font-size:8px;color:#8794a5}.latestGroupHead em{font-size:8px;color:#98a2b3;font-style:normal;white-space:nowrap}.latestGroupGrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.latestTile{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:9px 10px;min-width:0;box-shadow:0 4px 14px #10233d08}.latestTileTop{display:flex;align-items:center;gap:5px;min-width:0}.latestTileTop span{flex:0 0 auto;font-size:8px;font-weight:900;color:#667085;background:#f2f4f7;border-radius:999px;padding:2px 5px}.latestTileTop b{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.latestTile strong{display:block;margin-top:5px;font-size:18px;line-height:1.05;letter-spacing:-.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.latestTile strong.up{color:#d92d20}.latestTile strong.down{color:#175cd3}.latestTileFoot{display:flex;justify-content:space-between;align-items:flex-end;gap:5px;margin-top:5px;font-size:8px;color:#7d8b9d}.latestTileFoot span{font-weight:850;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.latestTileFoot .up{color:#d92d20}.latestTileFoot .down{color:#175cd3}.latestTileFoot .flat{color:#667085}.latestTile[data-metric^="TRIPOD_"] .latestTileTop b{white-space:normal;word-break:keep-all}.latestTile[data-metric="TRIPOD_MA"] strong{font-size:clamp(11px,3.2vw,16px);white-space:normal;overflow-wrap:anywhere;overflow:visible;text-overflow:clip}.tripodBoundaryChange{display:flex;flex-direction:column;gap:2px;margin:6px 0;font-size:11px;line-height:1.5;color:#526071}.tripodBoundaryChange span{white-space:normal;word-break:keep-all;overflow-wrap:anywhere}.latestMaChange{display:flex;flex-wrap:wrap;gap:2px 4px;margin-top:6px;font-size:11px;font-weight:850;line-height:1.4}.latestMaChange span{white-space:nowrap}.latestMaChange.up{color:#d92d20}.latestMaChange.down{color:#175cd3}.latestMaChange.flat{color:#667085} .latestCryptoBasis{font-size:8px;color:#667085;margin-top:5px;line-height:1.45;overflow-wrap:anywhere}.latestRateLag{margin-top:7px;padding:6px 7px;border:1px solid #f1cd83;border-radius:7px;background:#fffbeb;color:#92400e;font-size:9px;line-height:1.55;overflow-wrap:anywhere}.latestRateLag b{display:block;font-weight:850}.latestRateLag small{display:block;font-size:8px;color:#92400e}.latestTilePeriods{display:flex;gap:8px;flex-wrap:wrap;margin-top:5px;font-size:9px;font-weight:850}.latestTilePeriods .up{color:#d92d20}.latestTilePeriods .down{color:#175cd3}.latestTilePeriods .flat{color:#667085}.latestTileFoot{flex-wrap:wrap}.latestTileFoot time{white-space:nowrap;font-size:7px;color:#98a2b3}.obsIndexGrid .card:last-child{grid-column:1/-1}
@media(max-width:980px) and (min-width:761px){.latestGroupGrid,.latestBoardGrid{grid-template-columns:repeat(4,minmax(0,1fr))}.latestBoardHead{align-items:flex-start}.latestBoardTools{align-items:flex-end;flex-direction:column;gap:5px}}
@media(max-width:760px){.latestBoardWrap{padding:0 10px;margin-top:9px}.latestBoardHead{align-items:flex-start;flex-direction:column;gap:7px}.latestBoardTitleBox{display:block}.latestBoardTitleBox span{display:block;margin-top:2px}.latestBoardTools{width:100%;align-items:flex-start;flex-direction:column-reverse;gap:5px}.latestCompare{width:100%;overflow-x:auto;flex-wrap:nowrap;padding-bottom:2px;scrollbar-width:none}.latestCompare::-webkit-scrollbar{display:none}.latestCompare button{flex:0 0 auto;min-height:28px}.latestBoardGrid:not(.grouped){grid-template-columns:none!important;grid-template-rows:repeat(2,auto);grid-auto-flow:column;grid-auto-columns:minmax(138px,42vw);gap:6px;overflow-x:auto;padding-bottom:6px;scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch;scrollbar-width:none}.latestBoardGrid:not(.grouped)::-webkit-scrollbar{display:none}.latestGroup{padding:8px;margin-bottom:8px}.latestGroupHead{align-items:flex-start}.latestGroupHead>div{display:block}.latestGroupHead span{display:block;margin-top:2px}.latestGroupGrid{grid-template-columns:none;grid-template-rows:repeat(2,auto);grid-auto-flow:column;grid-auto-columns:minmax(138px,42vw);gap:6px;overflow-x:auto;padding-bottom:5px;scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch;scrollbar-width:none}.latestGroupGrid::-webkit-scrollbar{display:none}.latestTile{padding:8px 9px;scroll-snap-align:start}.latestTile strong{font-size:17px}.latestTileFoot{font-size:8px}.obsIndexGrid .card:last-child{grid-column:auto}}
.latestBoardWrap[data-tab="overview"] .latestGroupGrid{grid-template-columns:repeat(5,minmax(0,1fr));grid-template-rows:none;grid-auto-flow:row;grid-auto-columns:auto;overflow:visible}.overviewMacroGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.overviewMacroBlock{min-width:0}.overviewMacroBlock h4{margin:0 0 7px;font-size:11px;color:#344054}.latestBoardWrap[data-tab="overview"] .overviewMacroBlock .latestGroupGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.overviewWeekMeta{font-size:9px;color:#667085;margin-bottom:8px}.overviewWeekRow{display:grid;grid-template-columns:65px 55px minmax(0,1fr);gap:8px;padding:9px 8px;border-top:1px solid #e8edf3;font-size:11px}.overviewWeekRow.head{background:#f4f7fb;font-weight:850}.overviewWeekRow b{font-size:11px;overflow-wrap:anywhere}.overviewWeekRow small{display:block;font-size:9px;color:#667085;margin-top:3px}.overviewWeekEmpty{padding:10px;font-size:11px;color:#667085}@media(max-width:980px){.latestBoardWrap[data-tab="overview"] .latestGroupGrid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:760px){.overviewMacroGrid{grid-template-columns:1fr}.latestBoardWrap[data-tab="overview"] .latestGroupGrid,.latestBoardWrap[data-tab="overview"] .overviewMacroBlock .latestGroupGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.overviewWeekRow{grid-template-columns:48px 44px minmax(0,1fr);font-size:10px;gap:5px}}

.latestQuoteContext{display:flex;flex-direction:column;gap:3px;margin-top:7px;font-size:12px;line-height:1.5;color:#526071}.latestQuoteContext b{color:#175cd3}.latestQuoteContext.quoteWarning b{color:#b54708}

/* Market direction is the primary reading task; levels remain available below. */
.latestChangeFirst .latestPrimaryChange{margin-top:10px;min-width:0}
.latestChangeFirst .latestPrimaryLabel{display:block;font-size:12px;line-height:1.5;color:#667085}
.latestChangeFirst .latestPrimaryValue{display:block;font-size:26px;line-height:1.25;font-weight:850;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.latestChangeFirst .latestPrimaryChange.up{color:#d92d20}.latestChangeFirst .latestPrimaryChange.down{color:#175cd3}.latestChangeFirst .latestPrimaryChange.flat{color:#667085}
.latestTile.latestChangeFirst>strong.latestLevelValue{margin-top:6px;font-size:15px;line-height:1.5;font-weight:650;color:#526071;white-space:normal;overflow-wrap:anywhere;overflow:visible}
.latestChangeFirst[data-comparison="D1"] .latestTilePeriods>span:first-child,.latestChangeFirst[data-comparison="W1"] .latestTilePeriods>span:nth-child(2){display:none}
`;document.head.appendChild(st);
let tries=0;const id=setInterval(()=>{tries++;ensureIndexShell();ensureOfficialMacroRuntime();hookRender();hookCalendar();bindTabs();if(renderBoard()&&tries>10&&window.__JJOONI_OFFICIAL_MACRO_V1)clearInterval(id);if(tries>120)clearInterval(id)},100);
window.__JJOONI_LATEST_BOARD={version:'20261101-crypto-runtime-stale',items:ITEMS,render:renderBoard,getSeries:seriesOf,getComparison:()=>({key:compareKey,...COMPARES[compareKey]}),contract:'GROUPED_MARKET_BOARD_WITH_INDEX_TAB_PERIOD_COMPARISON_AND_SOURCE_BASIS',tabs:Object.keys(TAB_CONFIG),comparisons:Object.keys(COMPARES)};
})();
