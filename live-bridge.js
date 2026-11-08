(function(){
'use strict';

const SHEET_ID='1t8TNfIHxSIc_uoSxAgmSbkqCz00923nF1u-b6jlCgYE';
const TAB='GITHUB_CT_LIVE';
const REFRESH_MS=60000;
const MAX_AGE=20*60*1000;
const M=window.JjooniMetrics;
if(!M)throw new Error('CANONICAL_METRICS_MISSING');
const REGISTRY=[
 {id:'TOSS',label:'Toss',type:'HUMAN',broker:'Toss증권'},
 {id:'ISA',label:'ISA',type:'HUMAN',broker:'KB증권'},
 {id:'PENSION',label:'연금저축',type:'HUMAN',broker:'KB증권'},
 {id:'IRP',label:'IRP',type:'HUMAN',broker:'KB증권'}
];
const ORIGINAL={
 latestAccountRows:typeof window.latestAccountRows==='function'?window.latestAccountRows:null,
 openTradePerformanceDetail:typeof window.openTradePerformanceDetail==='function'?window.openTradePerformanceDetail:null
};
const b64=s=>Uint8Array.from(atob(String(s||'')),c=>c.charCodeAt(0));
const n=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(v);return Number.isFinite(x)?x:null};
const z=v=>n(v)==null?0:n(v);
const sym=v=>String(v||'').trim().toUpperCase().replace(/\.(KS|KQ)$/,'');
const won=v=>n(v)==null?'—':'₩'+Math.round(Math.abs(z(v))).toLocaleString('ko-KR');
const signed=v=>n(v)==null?'—':(z(v)>=0?'+':'-')+won(v);
const pct=v=>n(v)==null?'—':(z(v)>=0?'+':'')+z(v).toFixed(2)+'%';
const usd=v=>n(v)==null?'—':'$'+z(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const clone=x=>JSON.parse(JSON.stringify(x));
const FIVE_ACCOUNT_NAV_SOURCES=new Set(['ACCOUNT_SUM_4','ACCOUNT_SUM_4_TOSS_OWNS_TRIPOD','FAST_EFFECTIVE_SUM_4_ACCOUNT_NAV']);
function isFiveAccountNavSource(source,live){
 const s=String(source||'');
 if(!FIVE_ACCOUNT_NAV_SOURCES.has(s))return false;
 if(s==='FAST_EFFECTIVE_SUM_4_ACCOUNT_NAV'||s==='ACCOUNT_SUM_4_TOSS_OWNS_TRIPOD'){
  const count=n(live?.total_nav_component_count);
  const missing=Array.isArray(live?.total_nav_missing_accounts)?live.total_nav_missing_accounts:[];
  if(count!=null&&count!==REGISTRY.length)return false;
  if(missing.length)return false;
 }
 return true;
}
let LAST_LIVE=null;
let lastAppliedSignature=null;
let CANON=null;
let TRADE_QUOTES={};
const STATIC_SECURITY_NAMES=(()=>{
 const m=new Map(),manual={'091170':'KODEX 은행','418660':'TIGER 미국나스닥100레버리지(합성)','006400':'삼성SDI','005380':'현대차'};
 Object.entries(manual).forEach(([k,v])=>m.set(k,v));
 const seen=new WeakSet(),key=v=>{const s=sym(v);return /^\d{1,6}$/.test(s)?s.padStart(6,'0'):s};
 const walk=(v,d=0)=>{if(!v||typeof v!=='object'||d>9||seen.has(v))return;seen.add(v);if(!Array.isArray(v)){const raw=v.ticker??v.symbol??v.code??v.stock_code??v.pdno??v.product_code??v.isu_cd;const nm=String(v.name??v.stock_name??v.security_name??v.prdt_name??v.product_name??v.isu_nm??v.kor_name??'').trim();const k=key(raw);if(k&&nm&&key(nm)!==k&&!m.has(k))m.set(k,nm)}const xs=Array.isArray(v)?v:Object.values(v);for(const x of xs)walk(x,d+1)};
 try{if(typeof D!=='undefined')walk(D)}catch(_){}
 return m;
})();
window.__JJOONI_SECURITY_NAMES=Object.fromEntries(STATIC_SECURITY_NAMES);

async function decryptEnvelope(env,password){
 const raw=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
 const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:b64(env.salt),iterations:Number(env.iterations),hash:'SHA-256'},raw,{name:'AES-GCM',length:256},false,['decrypt']);
 const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64(env.nonce),additionalData:b64(env.aad),tagLength:128},key,b64(env.ciphertext));
 return JSON.parse(new TextDecoder().decode(plain));
}

function loadGviz(){return new Promise((resolve,reject)=>{
 const cb='__ct_'+Date.now()+'_'+Math.random().toString(36).slice(2),s=document.createElement('script');let done=false;
 const finish=(e,v)=>{if(done)return;done=true;try{delete window[cb]}catch(_){};try{s.remove()}catch(_){};clearTimeout(timer);e?reject(e):resolve(v)};
 window[cb]=resp=>{try{const o={};((((resp||{}).table||{}).rows)||[]).forEach(r=>{const c=r.c||[],k=c[0]&&c[0].v!=null?String(c[0].v):'',v=c[1]&&c[1].v!=null?String(c[1].v):'';if(k)o[k]=v});finish(null,o)}catch(e){finish(e)}};
 const timer=setTimeout(()=>finish(new Error('GVIZ_TIMEOUT')),15000);s.onerror=()=>finish(new Error('GVIZ_LOAD_FAIL'));
 s.src='https://docs.google.com/spreadsheets/d/'+SHEET_ID+'/gviz/tq?sheet='+encodeURIComponent(TAB)+'&tqx='+encodeURIComponent('responseHandler:'+cb)+'&_='+Date.now();document.head.appendChild(s);
});}

function badge(){let e=document.getElementById('ctEncryptedLiveBadge');if(!e){e=document.createElement('div');e.id='ctEncryptedLiveBadge';e.style.cssText='position:fixed;right:12px;top:10px;z-index:100000;padding:6px 10px;border-radius:999px;font:800 10px/1.2 system-ui,-apple-system,sans-serif;box-shadow:0 4px 14px #0002;white-space:nowrap';document.body.appendChild(e)}return e}
function setBadge(text,state,title){const e=badge(),txt=String(text||''),ttl=String(title||'');if(e.textContent!==txt)e.textContent=txt;if(e.title!==ttl)e.title=ttl;const s=state==='good'?['#ecfdf3','#abefc6','#087443']:state==='warn'?['#fff7ed','#fed7aa','#b45309']:['#fff1f2','#fecdd3','#be123c'];const border='1px solid '+s[1];if(e.style.background!==s[0])e.style.background=s[0];if(e.style.border!==border)e.style.border=border;if(e.style.color!==s[2])e.style.color=s[2]}

function injectResponsiveCss(){
 if(document.getElementById('ct-final-responsive-v5'))return;
 const st=document.createElement('style');st.id='ct-final-responsive-v5';st.textContent=`
/* FINAL responsive contract: phone = top tabs, tablet = original left rail */
@media (max-width:767px){
 html,body{overflow-x:hidden!important}
 html.ctTouchTablet .app,html .app,.app{margin-left:0!important;width:100%!important;max-width:100%!important;padding:0 10px 20px!important;overflow-x:hidden!important}
 html.ctTouchTablet .top,html .top,.top{position:sticky!important;top:0!important;z-index:5000!important;height:56px!important;min-height:56px!important;margin:0 -10px!important;padding:0 12px!important;width:auto!important;background:linear-gradient(180deg,#05172e,#061d3b)!important}
 html.ctTouchTablet .tabs,html .tabs,.tabs{position:relative!important;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;width:calc(100% + 20px)!important;height:52px!important;margin:0 -10px 10px!important;padding:4px 6px!important;display:flex!important;flex-direction:row!important;grid-template-columns:none!important;gap:4px!important;overflow-x:auto!important;overflow-y:hidden!important;background:#061a36!important;border:0!important;z-index:20!important;box-shadow:0 3px 10px rgba(6,24,51,.10)!important;scrollbar-width:none!important}
 html.ctTouchTablet .tabs::-webkit-scrollbar,.tabs::-webkit-scrollbar{display:none!important}
 html.ctTouchTablet .tabs:before,html.ctTouchTablet .tabs:after,.tabs:before,.tabs:after{display:none!important}
 html.ctTouchTablet .tab,html.ctTouchTablet .tab[data-tab],html .tab,.tab,.tab[data-tab]{display:flex!important;flex:0 0 auto!important;min-width:78px!important;width:auto!important;height:44px!important;min-height:44px!important;padding:3px 7px!important;border:0!important;border-radius:8px!important;align-items:center!important;justify-content:center!important;text-align:center!important;font-size:8px!important;line-height:1.15!important;color:#c3d1e2!important;background:transparent!important;box-shadow:none!important}
 html.ctTouchTablet .tab.on,.tab.on{background:rgba(255,255,255,.1)!important;color:#fff!important}
 html.ctTouchTablet .tabPanel,.tabPanel{padding-top:0!important}
 #ctEncryptedLiveBadge{top:7px!important;right:8px!important;bottom:auto!important}
}
@media (min-width:768px) and (max-width:1199px){
 html,body{overflow-x:hidden!important}
 html.ctTouchTablet .tabs,html .tabs,.tabs{position:fixed!important;left:0!important;top:0!important;bottom:0!important;right:auto!important;width:158px!important;height:100vh!important;margin:0!important;padding:108px 12px 18px!important;display:flex!important;flex-direction:column!important;grid-template-columns:none!important;gap:6px!important;overflow-y:auto!important;overflow-x:hidden!important;background:linear-gradient(180deg,#061a36,#07162b)!important;border:0!important;z-index:4500!important;box-shadow:8px 0 28px rgba(6,24,51,.10)!important}
 html.ctTouchTablet .tabs:before,.tabs:before{content:'CONTROL\\A TOWER'!important;white-space:pre!important;display:block!important;position:absolute!important;left:20px!important;top:28px!important;color:white!important;font:900 17px/1.05 system-ui!important;letter-spacing:.02em!important}
 html.ctTouchTablet .tabs:after,.tabs:after{content:'INVESTMENT'!important;display:block!important;position:absolute!important;left:20px!important;top:72px!important;color:#8fa4bb!important;font:700 8px/1 system-ui!important;letter-spacing:.18em!important}
 html.ctTouchTablet .tab,html.ctTouchTablet .tab[data-tab],html .tab,.tab,.tab[data-tab]{display:flex!important;flex:0 0 auto!important;width:100%!important;min-width:0!important;min-height:46px!important;height:auto!important;padding:10px 10px!important;border:0!important;border-radius:9px!important;align-items:center!important;justify-content:flex-start!important;text-align:left!important;font-size:11px!important;color:#c3d1e2!important;background:transparent!important;box-shadow:none!important}
 html.ctTouchTablet .tab.on,.tab.on{background:linear-gradient(90deg,#123e75,#0c2d57)!important;color:#fff!important;box-shadow:inset 3px 0 #62a8ff!important}
 html.ctTouchTablet .app,html .app,.app{margin-left:158px!important;width:calc(100% - 158px)!important;max-width:none!important;padding:0 18px 28px!important}
 html.ctTouchTablet .top,html .top,.top{margin-left:0!important;width:100%!important}
 html.ctTouchTablet .top:before,.top:before{display:none!important}
 html.ctTouchTablet .tabPanel,.tabPanel{padding-top:0!important}
 #ctEncryptedLiveBadge{top:10px!important;right:12px!important;bottom:auto!important}
}
/* watchlist */
#panel-watchlist{max-width:100%}
.ctWlHead{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:8px 0 12px}
.ctWlTitle{font-size:22px;font-weight:900;color:#14243a}.ctWlSub{font-size:11px;color:#7d8b9d;margin-top:3px}
.ctWlControls{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.ctWlBtn{appearance:none;border:1px solid #dbe3ec;background:#fff;color:#344054;border-radius:999px;padding:7px 10px;font:800 10px/1 system-ui;cursor:pointer}
.ctWlBtn.on{background:#0b2f5d;color:#fff;border-color:#0b2f5d}
.ctWlCard{background:#fff;border:1px solid #e6ebf1;border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(12,31,54,.06)}
.ctWlMeta{padding:10px 12px;border-bottom:1px solid #edf1f5;font-size:10px;color:#7d8b9d;display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}
.ctWlRow{display:grid;grid-template-columns:34px minmax(0,1.6fr) minmax(80px,.7fr) repeat(4,minmax(66px,.58fr));align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid #f0f3f6;font-size:11px;color:#344054}.ctWlRow:last-child{border-bottom:0}
.ctWlRank{font-weight:900;color:#98a2b3}.ctWlName{font-weight:900;color:#101828}.ctWlTicker{font-size:9px;color:#98a2b3;margin-top:2px}.ctWlPrice{text-align:right;font-weight:800}.ctWlRet{text-align:right;font-weight:900}.ctWlRet.pos{color:#d92d20}.ctWlRet.neg{color:#175cd3}.ctWlBadges{display:flex;gap:4px;flex-wrap:wrap;margin-top:4px}.ctWlTag{font-size:8px;padding:2px 5px;border-radius:999px;background:#f2f4f7;color:#667085}.ctWlTag.live{background:#ecfdf3;color:#087443}.ctWlTag.held{background:#eff8ff;color:#175cd3}
@media(max-width:767px){.ctWlHead{display:block}.ctWlControls{justify-content:flex-start;margin-top:8px}.ctWlRow{grid-template-columns:24px minmax(0,1fr) 72px 64px;padding:9px 8px}.ctWlRow .ctWlRet[data-period="5d"],.ctWlRow .ctWlRet[data-period="10d"],.ctWlRow .ctWlRet[data-period="20d"]{display:none}.ctWlTitle{font-size:18px}.ctWlPrice{font-size:10px}}
`;(document.head||document.documentElement).appendChild(st);
}

function staticRows(){try{return ORIGINAL.latestAccountRows?ORIGINAL.latestAccountRows()||{}:{}}catch(_){return {}}}
function staticHumanRow(id){return staticRows()[id]||{}}
function staticPrincipal(id){const r=staticHumanRow(id);if(n(r.principal)!=null)return z(r.principal);try{const p=((D.human||{}).performance||[]).filter(x=>String(x.account||'').toUpperCase()===id).at(-1);return n(p&&p.principal)}catch(_){return null}}
function staticNetFlow(id){const r=staticHumanRow(id);if(n(r.net_cash_flow)!=null)return z(r.net_cash_flow);try{const p=((D.human||{}).performance||[]).filter(x=>String(x.account||'').toUpperCase()===id).at(-1);return n(p&&p.net_cash_flow)}catch(_){return null}}
function humanStaticPositions(id){try{return ((D.human||{}).positions||[]).filter(x=>String(x.account||x.account_type||'').toUpperCase()===id)}catch(_){return []}}
function legacyName(id,ticker){
 const k=sym(ticker);if(!k)return '';
 const sk=/^\d{1,6}$/.test(k)?k.padStart(6,'0'):k;const cached=STATIC_SECURITY_NAMES.get(sk)||STATIC_SECURITY_NAMES.get(k);if(cached)return cached;
 try{
  const hp=[...((D.human||{}).positions||[]),...((D.human||{}).trades||[])];
  const pools=[...hp];
  for(const x of pools){
   if(sym(x.ticker||x.symbol)!==k)continue;
   const nm=String(x.name||x.stock_name||x.security_name||x.prdt_name||'').trim();
   if(nm&&sym(nm)!==k)return nm;
  }
 }catch(_){}
 return '';
}

function makeCanonical(live){
 const A=live.accounts||{},out={};
 for(const r of REGISTRY){
  const a=A[r.id]||{},id=r.id,nav=n(a.nav),principal=n(a.principal),funded=(['ISA','PENSION'].includes(id)&&principal>0)||(id==='IRP'&&M.confirmedIrpPrincipal?.(a));
  let ps=Array.isArray(a.positions)?a.positions:[];
  ps=ps.map(p=>{const nm=String(p.name||p.stock_name||legacyName(id,p.ticker||p.symbol)||'').trim();return {...p,name:nm||p.name,stock_name:p.stock_name||nm,account:id,account_type:id,market_value_krw:M.valueKrw(p,a),market_value_currency:'KRW'}});
  const day=n(a.today_pnl??(id==='TRIPOD'?a.today_change:null)),flow=n(a.net_flow??a.net_cash_flow);
  out[id]={...a,id,type:r.type,nav,principal,performance_basis:funded?'CONTRIBUTED_CAPITAL':a.performance_basis,...M.cumulative({...a,id}),today_pnl:day,today_return:n(a.today_return),net_flow:flow,cash_krw:n(a.cash_krw??(['ISA','PENSION','IRP'].includes(id)?a.cash:null)),cash_usd:n(a.cash_usd),positions:ps,source:String(a.mode||a.source||''),quality:String(a.status||'MISSING'),account_quality:String(a.status||'MISSING'),today_pnl_quality:a.today_pnl_quality||(['ISA','PENSION','IRP','TRIPOD'].includes(id)?'MODELED':'BROKER_MEASURED'),signal:a.signal||live.tripod_signal||{}};
  out[id].cash_total_krw=M.cash(out[id]);
  out[id].nav_change=day!=null&&flow!=null?day+flow:null;
 }
 out.TRIPOD={id:'TRIPOD',type:'STRATEGY_VIEW',parent_account:'TOSS',additive:false,nav:null,positions:[],signal:(A.TRIPOD||{}).signal||live.tripod_signal||{}};
 const t=M.aggregate(out),rows=REGISTRY.map(r=>out[r.id]);
 // Producer canonical owns total NAV. The browser must not silently replace the
 // five-account ACCOUNT_SUM_5 total with a partial client-side recomputation.
 const producerTotal=n(live.total_nav??live.total_nav_krw);
 const producerTotalSource=String(live.total_nav_source||'');
 const accountSum=t.nav;
 const producerTotalTrusted=producerTotal!=null&&isFiveAccountNavSource(producerTotalSource,live);
 const authoritativeTotal=producerTotalTrusted?producerTotal:accountSum;
 const totalGap=producerTotalTrusted&&producerTotal!=null&&accountSum!=null?accountSum-producerTotal:null;
 return {snapshot_id:live.snapshot_id,master_refresh:live.master_refresh||null,performance_day:live.performance_day||null,generated_kst:live.generated_kst,observed_at:live.observed_at,source_snapshot_kst:live.source_snapshot_kst,registry:REGISTRY,accounts:out,account_ownership:{schema:'TOSS_OWNS_TRIPOD_V1',physical_accounts:REGISTRY.map(r=>r.id),strategy_parents:{TRIPOD:'TOSS'}},total_nav:authoritativeTotal,total_nav_source:producerTotalTrusted?producerTotalSource:'BROWSER_PHYSICAL_ACCOUNT_SUM',total:{day_quality:t.day_quality,today_quality_state:t.day_quality?.state||'UNKNOWN',nav:authoritativeTotal,nav_source:producerTotalTrusted?'PRODUCER_'+producerTotalSource:'BROWSER_ACCOUNT_SUM',browser_account_sum:accountSum,producer_total_nav:producerTotal,reconciliation_gap:totalGap,principal:t.principal,pnl:t.cum,return_pct:t.return_pct,today_change:t.day!=null&&t.flow!=null?t.day+t.flow:null,today_pnl:t.day,known_today_subtotal:t.known_day_subtotal,net_flow:t.flow,today_complete:t.known_day===REGISTRY.length,flow_complete:t.flow!=null,known_today_count:t.known_day,known_flow_count:rows.filter(x=>n(x.net_flow)!=null).length,account_count:REGISTRY.length,missing_today:rows.filter(x=>n(x.today_pnl)==null).map(x=>x.id),missing_flow:rows.filter(x=>n(x.net_flow)==null).map(x=>x.id),position_count:rows.reduce((sum,x)=>sum+M.positions(x).length,0)}};
}

function mergePositions(live){
 D.human=D.human||{};D.human.positions=Array.isArray(D.human.positions)?D.human.positions:[];const legacyPositions=D.human.positions.filter(p=>String(p.account||p.account_type||'').toUpperCase()==='TRIPOD');if(legacyPositions.length)D.human.legacy_tripod_reference_positions=legacyPositions;D.human.positions=D.human.positions.filter(p=>String(p.account||p.account_type||'').toUpperCase()!=='TRIPOD');const a=live.accounts||{};
 ['TOSS','ISA','PENSION','IRP'].forEach(id=>{const x=a[id]||{};if(!Array.isArray(x.positions))return;
  D.human.positions=D.human.positions.filter(q=>{const acct=String(q.account||q.account_type||'').toUpperCase(),rt=String(q.record_type||'POSITION').toUpperCase();return acct!==id});
  (x.positions||[]).forEach(p=>{const nm=String(p.name||p.stock_name||legacyName(id,p.ticker||p.symbol)||'').trim();const m={...p,name:nm||p.name,stock_name:p.stock_name||nm,account:id,account_type:id,record_type:String(p.record_type||'POSITION').toUpperCase(),current_price:n(p.current_price),market_value:n(p.market_value),avg_price:n(p.avg_price),price_source:p.price_source||x.source||x.mode||'SOURCE_UNSPECIFIED',data_state:p.data_state||'CURRENT'};D.human.positions.push(m)});
 });
 const tp=a.TRIPOD||{};D.human.tripod_positions=((a.TOSS||{}).positions||[]).filter(p=>['QQQ','QQQM','QLD','TQQQ'].includes(sym(p.ticker||p.symbol))).map(p=>({...p,account:'TOSS',account_type:'TOSS',strategy:'TRIPOD'}));D.human.tripod_market={ticker:'TQQQ',current_price:z(tp.current_price),prev_close:z(tp.prev_close),fx:z(tp.fx),previous_fx:n(tp.previous_fx),currency:'USD',quote_timestamp:live.observed_at,current_price_source:'PUBLIC_MARKET_MODEL'};D.human.tripod_signal=tp.signal||live.tripod_signal||{};
}

function mergeTrades(live){
 D.human=D.human||{};const old=(Array.isArray(D.human.trades)?D.human.trades:[]).filter(t=>!['AI','AIBOT','AI_BOT','TRIPOD'].includes(String(t.account||t.account_type||'').trim().toUpperCase())),fresh=(Array.isArray(live.recent_trades)?live.recent_trades:[]).filter(t=>!['AI','AIBOT','AI_BOT','TRIPOD'].includes(String(t.account||t.account_type||'').trim().toUpperCase())),key=t=>[String(t.account||t.account_type||''),String(t.trade_date||t.filled_at_kst||''),sym(t.ticker||t.symbol),String(t.side||''),String(t.qty??t.quantity??''),String(t.price??t.filled_price??'')].join('|'),m=new Map();[...fresh,...old].forEach(t=>{const k=key(t);if(!k)return;if(!m.has(k)){m.set(k,{...t});return}const cur=m.get(k),have=String(cur.name||cur.stock_name||'').trim(),incoming=String(t.name||t.stock_name||'').trim();if(!have&&incoming){if(t.name)cur.name=t.name;if(t.stock_name)cur.stock_name=t.stock_name}});D.human.trades=[...m.values()].map(t=>{const nm=String(t.name||t.stock_name||legacyName(String(t.account||t.account_type||'').toUpperCase(),t.ticker||t.symbol)||'').trim();return nm?{...t,name:t.name||nm,stock_name:t.stock_name||nm}:t}).sort((a,b)=>String(b.filled_at_kst||b.trade_date||'').localeCompare(String(a.filled_at_kst||a.trade_date||''))).slice(0,240);
}

function syncTradeCurrentPrices(){
 if(typeof D==='undefined'||!D.human)return;
 const horizonMap=((TRADE_QUOTES||{}).trade_horizons)||{};
 if(horizonMap&&typeof horizonMap==='object'&&Object.keys(horizonMap).length){
   D.human.trade_review_horizons=horizonMap;
   D.human.trade_review_horizons_asof=String((TRADE_QUOTES||{}).trade_horizons_asof||'');
   D.human.trade_review_horizons_source=String((((TRADE_QUOTES||{}).trade_horizon_meta)||{}).source||'TOSS_OPENAPI_CANDLES_1D_UNADJUSTED');
   window.__JJOONI_TRADE_HORIZONS_V26=horizonMap;
 }else{
   delete D.human.trade_review_horizons;
   delete D.human.trade_review_horizons_asof;
   delete D.human.trade_review_horizons_source;
   window.__JJOONI_TRADE_HORIZONS_V26={};
 }
 const px=new Map(),src=new Map(),put=(ticker,price,source)=>{const k=sym(ticker),v=n(price);if(k&&v!=null&&v>0&&!px.has(k)){px.set(k,v);src.set(k,source||'CURRENT_QUOTE')}};
 if(CANON)Object.values(CANON.accounts||{}).forEach(c=>(c.positions||[]).filter(p=>String(p.record_type||'').toUpperCase()!=='FUND'&&!/^F\d+$/i.test(p.ticker||'')).forEach(p=>put(p.ticker,p.current_price||p.price,p.price_source||c.source)));
 const side=((TRADE_QUOTES||{}).q)||{};Object.entries(side).forEach(([ticker,q])=>put(ticker,q&&q.p,q&&q.s));
 const tp=((LAST_LIVE&&LAST_LIVE.accounts)||{}).TRIPOD||{};put('TQQQ',tp.current_price,tp.mode||'TRIPOD_MARKET');
 (D.human.trades||[]).forEach(t=>{if(/^F\d+$/i.test(sym(t.ticker))||String(t.record_type||'').toUpperCase()==='FUND'){delete t.current_price;delete t.trade_return;return}const k=sym(t.ticker),p=px.get(k);if(p>0){t.current_price=p;t.current_price_source=src.get(k)||'CURRENT_QUOTE';const ep=n(t.price),sideText=String(t.side||'').toUpperCase();if(ep!=null&&ep>0){if(sideText.includes('BUY')||sideText.includes('매수'))t.trade_return=(p/ep)-1;else t.trade_return=null;}}});
 window.__JJOONI_TRADE_QUOTES=TRADE_QUOTES;
}
function syncLegacyMirrors(){
 if(!CANON||typeof D==='undefined')return;
 D.human=D.human||{};
 const ids=['TOSS','ISA','PENSION','IRP'],h=M.aggregate(CANON.accounts,ids),day=CANON.performance_day?.date||M.dayKey(CANON.observed_at);
 D.human.current_account_navs=D.human.current_account_navs||{};D.human.current_account_details=D.human.current_account_details||{};delete D.human.current_account_navs.TRIPOD;delete D.human.current_account_details.TRIPOD;
 ids.forEach(id=>{const a=CANON.accounts[id];D.human.current_account_navs[id]=a.nav;D.human.current_account_details[id]={...(D.human.current_account_details[id]||{}),current_nav:a.nav,modeled_current_nav:a.nav,cash_krw:a.cash_krw,cash_usd:a.cash_usd,cash_total_krw:M.cash(a),canonical_source:a.source,canonical_quality:a.quality}});
 Object.assign(D.human,{total_asset:h.nav,principal:h.principal,total_pnl:h.cum,return_pct:h.return_pct});
 const history=Array.isArray(D.human.performance)?D.human.performance:[],legacyHistory=history.filter(r=>String(r.account||'').toUpperCase()==='TRIPOD');if(legacyHistory.length)D.human.legacy_tripod_reference_performance=legacyHistory;const rows=history.filter(r=>String(r.account||'').toUpperCase()!=='TRIPOD');
 rows.forEach(x=>{x.date=M.dayKey(x.date)});
 function upsert(id,fields){if(!day)return;let r=rows.find(x=>x.date===day&&String(x.account||'').toUpperCase()===id&&String(x.series_id||'ACTUAL').toUpperCase()==='ACTUAL');if(!r){r={date:day,account:id,series_id:'ACTUAL'};rows.push(r)}Object.assign(r,fields,{sync_kst:CANON.observed_at,snapshot_id:CANON.snapshot_id,data_state:'CANONICAL_CURRENT_OBSERVATION'})}
 ids.forEach(id=>{const a=CANON.accounts[id];upsert(id,{total_asset:a.nav,principal:a.principal,total_pnl:a.pnl,market_pnl:a.today_pnl,net_cash_flow:a.net_flow,daily_return:n(a.today_return)==null?null:a.today_return/100,flow_adj_return:n(a.today_return)==null?null:a.today_return/100,flow_adj_daily_return:n(a.today_return)==null?null:a.today_return/100})});
 const total={total_asset:h.nav,principal:h.principal,total_pnl:h.cum,return_pct:h.return_pct,market_pnl:h.day,net_cash_flow:h.flow,daily_return:h.day_return==null?null:h.day_return/100,flow_adj_return:h.day_return==null?null:h.day_return/100,flow_adj_daily_return:h.day_return==null?null:h.day_return/100};upsert('TOTAL',total);
 D.human.latest_performance={...total,date:day,account:'TOTAL',sync_kst:CANON.observed_at};D.human.performance=rows;
}

function installCanonicalFunctions(){
 window.latestAccountRows=function(){const base=ORIGINAL.latestAccountRows?ORIGINAL.latestAccountRows()||{}:{};if(!CANON)return base;const out={...base};['TOSS','ISA','PENSION','IRP'].forEach(id=>{const c=CANON.accounts[id]||{};out[id]={...(base[id]||{}),account:id,total_asset:n(c.nav),principal:n(c.principal),market_pnl:n(c.today_pnl),net_cash_flow:n(c.net_flow),daily_return:n(c.today_return)!=null?z(c.today_return)/100:null,flow_adj_return:n(c.today_return)!=null?z(c.today_return)/100:null,data_state:c.quality,sync_kst:CANON.observed_at};});return out;};
 window.buildTodayAccounting=function(){const accts={},ids=['TOSS','ISA','PENSION','IRP'],sum=M.aggregate(CANON.accounts,ids);ids.forEach(id=>{const c=CANON.accounts[id]||{},p=n(c.today_pnl),f=n(c.net_flow),prev=M.previous(c),nav=n(c.nav),chg=nav!=null&&prev!=null?nav-prev:null;accts[id]={account:id,current_nav:nav,actual_nav:nav,previous_nav:prev,nav_change:chg,actual_nav_change:chg,live_nav_change:chg,net_cash_flow:f,live_pnl:p,investment_pnl:p,daily_return:n(c.today_return),data_state:c.today_pnl_quality||c.quality,sync_kst:CANON.observed_at}});const change=sum.nav!=null&&sum.previous!=null?sum.nav-sum.previous:null;return {accounts:accts,current_nav:sum.nav,actual_nav:sum.nav,nav_change:change,actual_nav_change:change,live_nav_change:change,net_cash_flow:sum.flow,live_pnl:sum.day,investment_pnl:sum.day,previous_nav:sum.previous,daily_return:sum.day_return==null?null:sum.day_return/100,explained_gap:null,live_reconciliation_gap:null,performance_day:CANON.performance_day||null};};
 window.buildUnifiedAccountSnapshot=function(){const c=clone(CANON);Object.values(c.accounts).forEach(x=>{x.today_change=x.today_pnl;x.session_change=x.today_pnl;x.extended_change=CANON.performance_day?null:0;x.session_return=x.today_return;x.session_quality=x.quality;x.position_count=(x.positions||[]).length;x.cash=M.cash(x);});c.total.session_change=c.total.today_pnl;c.total.extended_change=CANON.performance_day?null:0;c.total.session_return=null;c.total.unique_ticker_count=new Set(Object.values(c.accounts).flatMap(x=>(x.positions||[]).map(p=>sym(p.ticker)).filter(Boolean))).size;return c;};
 window.buildUnifiedPortfolioPositions=function(){if(!CANON)return [];return REGISTRY.flatMap(r=>((CANON.accounts[r.id]||{}).positions||[]).map(p=>({...p,account:r.id,account_type:r.id,current_price:z(p.current_price||p.price),market_value:z(p.market_value||p.value_krw||p.value),data_state:p.data_state||((CANON.accounts[r.id]||{}).quality),price_source:p.price_source||((CANON.accounts[r.id]||{}).source)})));};
 window.buildRegularSessionMetrics=function(){const accounts={},positions=[];REGISTRY.forEach(r=>{const c=CANON.accounts[r.id]||{};let priced=0,total=0;(c.positions||[]).forEach(p=>{if(String(p.record_type||'POSITION').toUpperCase()!=='POSITION')return;total++;const cur=z(p.current_price||p.price),prev=z(p.prev_close),qty=z(p.qty),fx=String(p.currency||'KRW').toUpperCase()==='USD'?(z(p.fx)||z(c.fx)||z(((LAST_LIVE.accounts||{}).AI||{}).fx_krw_per_usd)||1):1,ok=cur>0&&prev>0&&qty>0;if(ok)priced++;positions.push({account:r.id,ticker:p.ticker,name:p.name,qty,baseline_price:prev,regular_mark:cur,regular_pnl:ok?qty*(cur-prev)*fx:0,extended_pnl:0,session_pnl:ok?qty*(cur-prev)*fx:0,quality:ok?'FULL':'REFERENCE',quote_timestamp:p.live_price_timestamp||CANON.observed_at,quote_source:p.price_source||c.source,base_fx:fx})});let q=['MODELED_LIVE','MODEL_LIVE','USER_VERIFIED_CURRENT','LIVE'].includes(c.quality)?'FULL':c.quality;accounts[r.id]={regular_pnl:CANON.performance_day?null:n(c.today_pnl),extended_pnl:CANON.performance_day?null:0,session_pnl:n(c.today_pnl),quality:q,priced,positions:total,session_label:c.source};});return {accounts,positions,context:{source:'CANONICAL_V5',observed_at:CANON.observed_at}};};
 if(ORIGINAL.openTradePerformanceDetail&&!window.__ctTradeDetailWrapped){window.openTradePerformanceDetail=function(t,acct,currentPrice,perf,rankLabel){let cp=n(currentPrice);if((cp==null||cp<=0)&&CANON){const id=String(acct||t&&t.account||'').toUpperCase(),p=((CANON.accounts[id]||{}).positions||[]).find(x=>sym(x.ticker)===sym(t&&t.ticker));cp=n(p&&p.current_price)||n(p&&p.price)||cp;}return ORIGINAL.openTradePerformanceDetail(t,acct,cp,perf,rankLabel)};window.__ctTradeDetailWrapped=true;}
}

function authoritativeFiveAccountNav(){
 const live=LAST_LIVE||window.__JJOONI_LIVE_PAYLOAD||{};
 const producer=n(live.total_nav??live.total_nav_krw);
 if(producer!=null&&isFiveAccountNavSource(live.total_nav_source,live))return {nav:producer,source:String(live.total_nav_source||''),kind:'PRODUCER'};
 const canonical=n(CANON?.total?.nav);
 return canonical!=null?{nav:canonical,source:String(CANON?.total?.nav_source||'CANONICAL'),kind:'CANONICAL'}:null;
}

function replaceWonAfterLabel(el,label,nav){
 if(!el)return false;
 const txt=String(el.textContent||'');
 if(!txt.includes(label))return false;
 const next=txt.replace(/₩\s*[\d,]+(?:\.\d+)?/,won(nav));
 if(next===txt)return false;
 el.textContent=next;el.dataset.ctFiveAccountNav='1';return true;
}

function patchAllFiveAccountTotalSurfaces(){
 const truth=authoritativeFiveAccountNav();if(!truth)return 0;
 const nav=truth.nav,fmt=won(nav);let patched=0;
 const mobile=document.querySelector('#ctMobileNetSummaryV4 .ctNetValue');
 if(mobile&&String(mobile.textContent||'').trim()!==fmt){mobile.textContent=fmt;mobile.dataset.ctFiveAccountNav='1';patched++}
 const mobileBox=document.getElementById('ctMobileNetSummaryV4');
 if(mobileBox){mobileBox.dataset.navAuthority='PRODUCER_'+truth.source;mobileBox.dataset.fiveAccountNav='1'}

 for(const sel of ['.ctP8Total','.ctA8Total']){
  document.querySelectorAll(sel).forEach(el=>{if(replaceWonAfterLabel(el,'총자산',nav))patched++});
 }
 const roots=[document.getElementById('panel-overview'),document.getElementById('panel-accounts'),document.getElementById('panel-performance'),document.getElementById('panel-compare')].filter(Boolean);
 for(const root of roots){
  const labels=[...root.querySelectorAll('.ctOvLabel,.label,div,span,small,b,strong')].filter(e=>{
   if(e.children&&e.children.length)return false;
   if(e.closest&&e.closest('.ctAcct'))return false;
   const t=String(e.textContent||'').trim().replace(/\s+/g,' ');
   return /^(?:총자산\s*[·•]\s*[45]계좌|전체\s*[45]계좌\s*NAV|현재\s*총자산\s*\(4계좌\s*NAV\))$/i.test(t);
  });
  labels.forEach(label=>{
   let box=label.parentElement;
   for(let i=0;box&&i<5;i++,box=box.parentElement){
    if(box.classList&&box.classList.contains('ctAcct'))break;
    const vals=[...box.querySelectorAll('div,span,b,strong')].filter(e=>e.children.length===0&&e!==label&&/^[-+]?₩\s*[\d,]+(?:\.\d+)?(?:원)?$/.test(String(e.textContent||'').trim()));
    if(vals.length){
     vals.sort((a,b)=>(parseFloat(getComputedStyle(b).fontSize)||0)-(parseFloat(getComputedStyle(a).fontSize)||0));
     const v=vals[0];if(String(v.textContent||'').trim()!==fmt){v.textContent=fmt;v.dataset.ctFiveAccountNav='1';patched++}
     break;
    }
   }
  });
 }
 window.__JJOONI_SIX_ACCOUNT_NAV_V46={state:'ACTIVE',version:'46.0',nav,source:truth.source,kind:truth.kind,patched,updated_at:new Date().toISOString()};
 return patched;
}

function updateOverviewTotalNav(){
 // Only one verified NAV authority for the entire overview patch pass.
 const truth=authoritativeFiveAccountNav();if(!CANON||!truth)return;
 const root=document.getElementById('panel-overview')||document;
 const total=truth.nav,fmt=won(total),heading='현재 총자산 (4계좌 NAV)';
 const labels=[...root.querySelectorAll('.ctOvLabel,.label,div,span,small,b,strong')].filter(e=>{
   if(e.children&&e.children.length)return false;
   if(e.closest&&e.closest('.ctAcct'))return false;
   const t=String(e.textContent||'').trim().replace(/\s+/g,' ');
   return /^(현재\s*총자산(?:\s*\(NAV\))?|현재\s*총자산\s*\(4계좌\s*NAV\)|전체\s*[45]계좌\s*NAV|총\s*자산(?:\s*\(NAV\))?|총자산(?:\s*\(NAV\))?)$/i.test(t);
 });
 let patched=0;
 labels.forEach(label=>{
   let box=label;
   for(let i=0;box&&i<6;i++,box=box.parentElement){
     if(box.classList&&box.classList.contains('ctAcct'))break;
     const direct=box.querySelector&&box.querySelector('.ctOvValue,.value,.v2Value,[class*="Value"],[class*="value"]');
     if(direct&&direct!==label){
       if(String(direct.textContent||'').trim()!==fmt)direct.textContent=fmt;
       if(String(label.textContent||'')!==heading)label.textContent=heading;
       direct.dataset.ctFiveAccountNav='1';
       patched++;break;
     }
     const leaves=box.querySelectorAll?[...box.querySelectorAll('div,span,b,strong')].filter(e=>e.children.length===0&&e!==label&&/^[-+]?₩?[\d,]+(?:\.\d+)?원?$/.test(String(e.textContent||'').trim())):[];
     if(leaves.length){
       leaves.sort((a,b)=>(parseFloat(getComputedStyle(b).fontSize)||0)-(parseFloat(getComputedStyle(a).fontSize)||0));
       const v=leaves[0];
       if(String(v.textContent||'').trim()!==fmt)v.textContent=fmt;
       if(String(label.textContent||'')!==heading)label.textContent=heading;
       v.dataset.ctFiveAccountNav='1';
       patched++;break;
     }
   }
 });
 const strip=document.getElementById('ctTodayNetStrip');
 if(strip){
   const parts=REGISTRY.map(r=>r.label+' '+won((CANON.accounts[r.id]||{}).nav));
   strip.dataset.ctFiveAccountNav='1';
   strip.title='4계좌 합산: '+parts.join(' · ');
 }
 window.__JJOONI_OVERVIEW_5NAV_V45={state:patched?'ACTIVE':'WAITING_TARGET',version:'44.0',nav:total,account_count:REGISTRY.length,accounts:Object.fromEntries(REGISTRY.map(r=>[r.id,n((CANON.accounts[r.id]||{}).nav)])),patched,updated_at:new Date().toISOString()};
}

function updateCards(){
 removeRetiredAccountUi();
 document.querySelectorAll('.ctAcct,.ctA8Card,.ctP8Card').forEach(card=>{const name=String(card.querySelector('.ctAcctName,.ctA8Name,.ctP8Name')?.textContent||'').trim();if(/^(?:TRI[- ]?POD|트라이팟)$/i.test(name))card.remove()});
 if(!CANON)return;const byName=name=>[...document.querySelectorAll('.ctAcct')].find(c=>String((c.querySelector('.ctAcctName')||{}).textContent||'').toLowerCase().includes(name.toLowerCase())),line=(card,id,html)=>{if(!card)return;let e=card.querySelector('#'+id);if(!e){e=document.createElement('div');e.id=id;e.style.cssText='grid-column:1/-1;font:800 9px/1.4 system-ui;margin-top:4px;padding-top:4px;border-top:1px dashed #e7ebf0;text-align:right;white-space:normal';card.appendChild(e)}if(e.innerHTML!==html)e.innerHTML=html};
 REGISTRY.forEach(r=>{const c=CANON.accounts[r.id]||{},card=byName(r.label==='TRI-POD'?'tri-pod':r.label.toLowerCase());if(!card)return;const nav=card.querySelector('.ctAcctNav'),navText=n(c.nav)!=null?won(c.nav):null;if(nav&&navText!=null&&nav.textContent!==navText)nav.textContent=navText;const displayDay=window.JjooniPerformanceDay?.daily(c),day=card.querySelector('.ctAcctTodayValue'),dayText=displayDay&&n(displayDay.pnl)!=null?signed(displayDay.pnl)+(n(displayDay.rate)!=null?' '+pct(displayDay.rate):''):n(c.today_pnl)==null?(n(c.holding_price_effect?.known_subtotal_krw)!=null&&c.holding_price_effect?.known_count>0?'가격변동 '+signed(c.holding_price_effect.known_subtotal_krw):'당일손익 —'):signed(c.today_pnl)+' '+pct(c.today_return);if(day&&day.textContent!==dayText)day.textContent=dayText;let extra='';if(r.id==='TOSS')extra=`예수금 KRW ${won(c.cash_krw)} · USD ${usd(c.cash_usd)} · <b style="color:#b45309">REF</b> · 오늘손익 ${displayDay&&n(displayDay.pnl)!=null?signed(displayDay.pnl):'자료 없음'}`;else if(['ISA','PENSION','IRP'].includes(r.id))extra=`예수금 ${won(c.cash_krw)} · <b style="color:#175cd3">MODEL LIVE</b> · 오늘손익 ${displayDay&&n(displayDay.pnl)!=null?signed(displayDay.pnl):'자료 없음'} · 순입출금 ${n(c.net_flow)==null?'—':signed(c.net_flow)}`;else if(r.id==='TRIPOD')extra=`TQQQ ${z(((LAST_LIVE.accounts||{}).TRIPOD||{}).qty).toLocaleString()}주 · ${usd(c.current_price)} · ${pct(c.today_return)} · ${(c.signal||{}).regime||'—'} / ${(c.signal||{}).target||'—'}`;if(extra)line(card,'ctCanonical'+r.id,extra)});
 let strip=document.getElementById('ctTodayNetStrip');if(!strip){const anchor=document.getElementById('overviewAccounts');if(anchor){strip=document.createElement('div');strip.id='ctTodayNetStrip';strip.style.cssText='margin:6px 0 10px;padding:9px 12px;border:1px solid #e5eaf0;border-radius:12px;background:#fff;font:800 10px/1.45 system-ui;color:#344054';anchor.parentNode.insertBefore(strip,anchor)}}if(strip){const effect=CANON.performance_day?.price_effect,priceScope=n(CANON.total.today_pnl)==null&&effect?.known_count>0;const html=priceScope?`4계좌 자산 <b>${won(CANON.total.nav)}</b> · 오늘 보유가격 변동 <b class="${effect.known_subtotal_krw<0?'loss':'gain'}">${signed(effect.known_subtotal_krw)}</b> · ${effect.known_count}/${effect.position_count}종목 · 매매·현금흐름 제외`:`4계좌 SSOT · NAV <b>${won(CANON.total.nav)}</b> · 오늘 투자손익 <b>${signed(CANON.total.today_pnl)}</b> · 순입출금 <b>${CANON.total.flow_complete?signed(CANON.total.net_flow):'PARTIAL'}</b> · 오늘 순증 <b>${CANON.total.flow_complete?signed(CANON.total.today_change):'검증중'}</b>`;if(strip.innerHTML!==html)strip.innerHTML=html;}
}

function updateHero(){if(!CANON)return;const h=document.querySelector('.ctOvPrimary');if(!h)return;const label=h.querySelector('.ctOvLabel'),big=document.getElementById('overviewNavChange'),ret=document.getElementById('overviewDailyReturn'),pe=CANON.performance_day?.price_effect,usePrice=n(CANON.total.today_pnl)==null&&pe?.known_count>0&&n(pe.known_subtotal_krw)!=null,labelText=usePrice?`오늘 보유종목 가격변동 (${pe.known_count}/${pe.position_count}종목)`:`4계좌 오늘 투자손익 (${CANON.total.known_today_count}/${CANON.total.account_count})`,bigText=signed(usePrice?pe.known_subtotal_krw:CANON.total.today_pnl),retText=usePrice?'현재 보유수량 기준':CANON.total.today_complete?'FULL':'PARTIAL';if(label&&label.textContent!==labelText)label.textContent=labelText;if(big&&big.textContent!==bigText)big.textContent=bigText;if(big){const value=usePrice?pe.known_subtotal_krw:CANON.total.today_pnl,kind=n(value)==null?'unknown':value<0?'loss':value>0?'gain':'neutral';big.dataset.ctTone=kind;big.classList.toggle('loss',kind==='loss');big.classList.toggle('gain',kind==='gain');big.style.setProperty('color',kind==='loss'?'#78b7ff':kind==='gain'?'#ff8395':'#e5edf8','important');}if(ret&&ret.textContent!==retText)ret.textContent=retText;let w=document.getElementById('ctHeroScopeWarning');if(!w){w=document.createElement('div');w.id='ctHeroScopeWarning';w.style.cssText='margin-top:5px;font:800 9px/1.35 system-ui;color:#ffb4bf';h.appendChild(w)}const sources=REGISTRY.map(r=>r.id+':'+((CANON.accounts[r.id]||{}).today_pnl_quality||'UNKNOWN')).join(' · '),wt=usePrice?'현재 수량·현재 환율 기준 · 계좌 전체 투자손익 별도 대사':(CANON.total.today_complete?'당일 P&L 4계좌 연결':'당일 P&L 미연결 '+CANON.total.missing_today.join(','))+' · '+sources;if(w.textContent!==wt)w.textContent=wt;}
function fixLegacyBadges(){const l=document.getElementById('ctLiveBadge');if(l)l.style.display='none';document.querySelectorAll('.live').forEach(e=>{if(e.id!=='ctEncryptedLiveBadge')e.style.display='none'})}

function removeRetiredAccountUi(){
 const oldAi='AI'+' BOT',oldAuto='AUTO'+'BOT';
 document.querySelectorAll('[data-account="AI"],[data-account-id="AI"],[data-account-code="AI"]').forEach(e=>e.remove());
 [...document.querySelectorAll('.ctAcct')].forEach(card=>{const name=String((card.querySelector('.ctAcctName')||{}).textContent||'').trim().toUpperCase();if(name===oldAi)card.remove()});
 [...document.querySelectorAll('.tab')].forEach(tab=>{const text=String(tab.textContent||'').trim().toUpperCase();if(text.includes(oldAuto)||text===oldAi){const id=tab.dataset&&tab.dataset.tab;tab.remove();if(id){const panel=document.getElementById('panel-'+id);if(panel)panel.remove()}}});
}

function ensureWatchlistUi(){
 const tabs=document.querySelector('.tabs');if(!tabs)return;let tab=tabs.querySelector('[data-tab="watchlist"]');if(!tab){tab=document.createElement('div');tab.className='tab';tab.dataset.tab='watchlist';tab.textContent='시황/워치';tabs.appendChild(tab)}
 let panel=document.getElementById('panel-watchlist');if(!panel){panel=document.createElement('div');panel.id='panel-watchlist';panel.className='tabPanel';const root=document.querySelector('.app')||document.querySelector('.container')||document.body;root.appendChild(panel)}
 tab.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===tab));document.querySelectorAll('.tabPanel').forEach(x=>x.classList.remove('on'));panel.classList.add('on');renderWatchlist();};
}

function watchRows(wl,market){
 const source=market==='KR'?(wl.kr||[]):(wl.us||[]),at=M.parseMs(wl.sync_kst),basis=M.parseMs(LAST_LIVE?.generated_kst||LAST_LIVE?.observed_at),stale=at==null||basis==null||basis-at>7*86400000;
 const rows=new Map(source.map(x=>[sym(x.ticker),{...x,is_held:false,account:'',quote_live:!stale&&x.quote_live===true,quote_label:'참고값',...(stale?{day_return_pct:null,ret_5d_pct:null,ret_10d_pct:null,ret_20d_pct:null}:{})}]));
 for(const id of M.IDS){const a=CANON?.accounts?.[id]||{};for(const p of M.positions(a)){
  if(String(p.record_type||'').toUpperCase()==='FUND'||/^F\d+$/i.test(sym(p.ticker)))continue;
  const c=M.currency(p);if((market==='US')!==(c==='USD'))continue;
  const key=sym(p.ticker||p.symbol),old=rows.get(key)||{},price=n(p.current_price??p.price),prev=n(p.prev_close);
  rows.set(key,{...old,ticker:key,name:p.name||old.name||key,current_price:price,day_return_pct:price>0&&prev>0?100*(price/prev-1):null,is_held:true,account:[...(old.account?old.account.split(' / '):[]),id].join(' / '),quote_live:price!=null,quote_label:'계좌 원본'});
 }}return {rows:[...rows.values()],stale};
}
function renderWatchlist(){
 const panel=document.getElementById('panel-watchlist');if(!panel)return;const wl=LAST_LIVE?.watchlist||{},market=window.__ctWlMarket||'KR',sortKey=window.__ctWlSort||'day_return_pct',view=watchRows(wl,market),rows=view.rows.sort((a,b)=>(n(b[sortKey])!=null)-(n(a[sortKey])!=null)||(n(b[sortKey])??0)-(n(a[sortKey])??0)),periods=[['day_return_pct','1D'],['ret_5d_pct','5D'],['ret_10d_pct','10D'],['ret_20d_pct','20D']];
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),fmtPrice=x=>market==='KR'?won(x):usd(x),cls=v=>n(v)==null?'':v>0?'pos':v<0?'neg':'',sync=String(wl.sync_kst||'').replace('T',' ').slice(0,16);
 panel.innerHTML=`<div class="ctWlHead"><div><div class="ctWlTitle">시황 워치리스트</div><div class="ctWlSub">보유 여부·가격은 현재 계좌 원본 기준 · 관심종목 참고값과 기간 수익률은 별도 기준</div></div><div class="ctWlControls"><button class="ctWlBtn ${market==='KR'?'on':''}" data-wm="KR">한국장</button><button class="ctWlBtn ${market==='US'?'on':''}" data-wm="US">미국장</button>${periods.map(([k,l])=>`<button class="ctWlBtn ${sortKey===k?'on':''}" data-ws="${k}" aria-pressed="${sortKey===k}">${l}순</button>`).join('')}</div></div><div class="ctWlCard"><div class="ctWlMeta"><span>${market==='KR'?'한국장':'미국장'} · ${rows.length}종목</span><span>관심종목 기준 ${esc(sync||'미확인')} ${view.stale?'· 과거 참고값 · 기간 수익률 검증 대기':''}</span></div>${rows.map((x,i)=>`<div class="ctWlRow"><div class="ctWlRank">${i+1}</div><div><div class="ctWlName">${esc(x.name||x.ticker)}</div><div class="ctWlTicker">${esc(x.ticker)}</div><div class="ctWlBadges">${x.is_held?`<span class="ctWlTag held">보유 · ${esc(x.account)}</span>`:''}<span class="ctWlTag">${esc(x.quote_label)}</span></div></div><div class="ctWlPrice">${x.is_held?'원본':'참고'} ${fmtPrice(x.current_price)}</div>${periods.map(([k,l])=>`<div class="ctWlRet ${cls(x[k])}" data-period="${l.toLowerCase()}" data-selected="${k===sortKey?'1':'0'}"><small>${l}</small>${pct(x[k])}</div>`).join('')}</div>`).join('')||'<p>표시 가능한 자료가 없습니다.</p>'}</div>`;
 panel.querySelectorAll('[data-wm]').forEach(b=>b.onclick=()=>{window.__ctWlMarket=b.dataset.wm;renderWatchlist()});panel.querySelectorAll('[data-ws]').forEach(b=>b.onclick=()=>{window.__ctWlSort=b.dataset.ws;renderWatchlist()});
}

let OVERVIEW_NAV_PATCH_QUEUED=false;
function queueOverviewTotalNav(){
 if(OVERVIEW_NAV_PATCH_QUEUED)return;
 OVERVIEW_NAV_PATCH_QUEUED=true;
 setTimeout(()=>{OVERVIEW_NAV_PATCH_QUEUED=false;updateOverviewTotalNav();patchAllFiveAccountTotalSurfaces()},35);
}
try{new MutationObserver(muts=>{if(!CANON)return;for(const m of muts){const t=m.target&&m.target.nodeType===3?m.target.parentElement:m.target;if(t&&t.closest&&t.closest('#panel-overview')){queueOverviewTotalNav();break}}}).observe(document.documentElement,{subtree:true,childList:true,characterData:true})}catch(_){}

function renderAll(){ensureWatchlistUi();updateCards();updateOverviewTotalNav();patchAllFiveAccountTotalSurfaces();updateHero();fixLegacyBadges();injectResponsiveCss();const wp=document.getElementById('panel-watchlist');if(wp&&wp.classList.contains('on'))renderWatchlist();setTimeout(patchAllFiveAccountTotalSurfaces,60);setTimeout(patchAllFiveAccountTotalSurfaces,220);}

function applyLive(live){
 if(!live||!['JJOONI_CT_LIVE_V3','JJOONI_CT_LIVE_V4','JJOONI_CT_LIVE_V5'].includes(String(live.schema||'')))throw new Error('LIVE_SCHEMA_MISMATCH');if(typeof D==='undefined')throw new Error('CONTROL_TOWER_DATA_MISSING');
 const incoming=M.parseMs(live.generated_kst||live.observed_at),previous=M.parseMs(LAST_LIVE?.generated_kst||LAST_LIVE?.observed_at);if(incoming==null||incoming>Date.now()+120000)throw new Error('INVALID_SNAPSHOT_TIME');if(previous!=null&&incoming<previous)throw new Error('SNAPSHOT_ROLLBACK_REJECTED');
 // Polling an unchanged envelope must not fan out a full-page redraw. Include
 // the quote sidecar so corrected quotes with the same snapshot are applied.
 const signature=JSON.stringify([live,TRADE_QUOTES]);
 if(signature!==lastAppliedSignature){
 const candidate=makeCanonical(live);if(candidate.total.nav==null)throw Error('INCOMPLETE_NAV_SNAPSHOT');LAST_LIVE=live;window.__JJOONI_LIVE_PAYLOAD=live;mergePositions(live);CANON=candidate;window.__JJOONI_CANONICAL_SSOT=CANON;try{const positions=REGISTRY.flatMap(r=>M.positions(CANON.accounts[r.id]||{}).map(p=>({symbol:String(p.ticker||p.symbol||''),name:String(p.name||'')})));localStorage.setItem('jjooni_private_earnings_symbols_v1',JSON.stringify({as_of:CANON.observed_at,positions}))}catch(_){};mergeTrades(live);syncTradeCurrentPrices();syncLegacyMirrors();installCanonicalFunctions();renderAll();try{document.dispatchEvent(new CustomEvent('jjooni:live-applied',{detail:{snapshot_id:live.snapshot_id||null,observed_at:live.observed_at||null}}))}catch(_){};
 lastAppliedSignature=signature;
 }
 const ts=Date.parse(String(live.observed_at||'')),age=Number.isFinite(ts)?Date.now()-ts:Infinity,t=String(live.observed_at||'').replace('T',' ').slice(5,16),miss=CANON.total.missing_today.join(',')||'none';
 if(M.freshness(live).state==='STALE')setBadge('SSOT STALE · '+t,'warn','Producer next-update deadline exceeded. Missing daily P&L: '+miss);
 else setBadge('SSOT '+CANON.total.known_today_count+'/'+CANON.total.account_count+' · '+t,CANON.total.today_complete?'good':'warn','Canonical feed drives overview, performance, account drilldowns, trade review, TRI-POD and watchlist. Missing daily P&L: '+miss);
}

// One in-flight encrypted read is shared by open/resume/manual/recovery.
const CONNECTION=window.__JJOONI_FEED_CONNECTION={state:'IDLE',attempts:0,consecutive_failures:0,last_error:null,last_success_at:null};
let refreshFlight=null,lastRecoveryRead=0;
function refresh(){
 if(refreshFlight)return refreshFlight;
 refreshFlight=readEncryptedFeed().finally(()=>{refreshFlight=null});
 return refreshFlight;
}
async function readEncryptedFeed(){CONNECTION.state='CONNECTING';CONNECTION.attempts++;try{const pw=sessionStorage.getItem('jjooni_ct_session_pw');if(!pw)throw Error('SESSION_CREDENTIAL_UNAVAILABLE');const kv=await loadGviz();if(!String(kv.SCHEMA||'').startsWith('JJOONI_CT_LIVE_ENCRYPTED_'))throw new Error('ENVELOPE_SCHEMA_MISMATCH');try{TRADE_QUOTES=JSON.parse(kv.TRADE_QUOTES_JSON||'{}')}catch(_){TRADE_QUOTES={}};window.__JJOONI_COST_SIDECAR=null;let encoded=kv.ENCRYPTED_PAYLOAD||'';if(kv.ENVELOPE_CHUNK_COUNT){const count=Number(kv.ENVELOPE_CHUNK_COUNT);if(!Number.isInteger(count)||count<1||count>64)throw Error('CHUNK_COUNT_INVALID');encoded=Array.from({length:count},(_,i)=>{const part=kv['ENCRYPTED_PAYLOAD_'+String(i).padStart(3,'0')];if(typeof part!=='string'||!part)throw Error('ENVELOPE_CHUNK_MISSING');return part}).join('')}const live=await decryptEnvelope(JSON.parse(encoded||'{}'),pw);if(kv.SNAPSHOT_ID&&kv.SNAPSHOT_ID!==live.snapshot_id)throw Error('ENVELOPE_SNAPSHOT_MISMATCH');applyLive(live);CONNECTION.state='READY';CONNECTION.consecutive_failures=0;CONNECTION.last_error=null;CONNECTION.last_success_at=new Date().toISOString();if(window.__JJOONI_ENTRY_DIAGNOSTICS?.phase==='CONNECTING_ACCOUNTS')window.__JJOONI_ENTRY_DIAGNOSTICS.phase='ACCOUNTS_READY';}catch(e){
 const message=String(e&&e.message||e).slice(0,180),blocked=e?.name==='OperationError'||/SCHEMA_MISMATCH|CHUNK_COUNT_INVALID|SNAPSHOT_MISMATCH|SNAPSHOT_ROLLBACK_REJECTED|INVALID_SNAPSHOT_TIME|INCOMPLETE_NAV_SNAPSHOT|SESSION_CREDENTIAL_UNAVAILABLE/.test(message);
 CONNECTION.state=blocked?'BLOCKED':CANON?'DEGRADED':'RETRYING';CONNECTION.consecutive_failures++;CONNECTION.last_error=message;
 setBadge(blocked?'SSOT BLOCKED':'SSOT RETRY',blocked?'bad':'warn',message);console.warn('CT account feed',e);
}}
function requestRefresh(reason){
 if(refreshFlight)return refreshFlight;
 if(document.hidden)return Promise.resolve();
 const now=Date.now();
 if(now-lastRecoveryRead<5000)return Promise.resolve();
 lastRecoveryRead=now;
 return refresh();
}
window.__JJOONI_LIVE_BRIDGE={refresh,requestRefresh};

function renderRefreshStatus(){
 const live=window.__JJOONI_LIVE_PAYLOAD||{},facts=M.freshness(live),pending=window.__JJOONI_FAST_ACCESS_REFRESH_V1||{};
 let box=document.getElementById('ctLiveRefreshStatus');if(!box){box=document.createElement('div');box.id='ctLiveRefreshStatus';box.style.cssText='margin:8px 0;padding:9px 12px;border:1px solid #dce5ef;border-radius:10px;background:#fff;display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px;color:#344054';const top=document.querySelector('.top');if(top?.parentNode)top.after(box);else (document.querySelector('.app')||document.body).prepend(box);const label=document.createElement('span');label.className='ctRefreshFacts';const button=document.createElement('button');button.type='button';button.textContent='계좌·시세 최신화';button.style.cssText='padding:7px 11px;border:0;border-radius:7px;background:#1459a6;color:white;cursor:pointer';button.onclick=async()=>{await triggerFastAccessRefresh('manual');await refresh();renderRefreshStatus()};box.append(label,button)}
 const at=live.generated_kst||live.observed_at,ms=M.parseMs(at),time=ms==null?'확인 필요':new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(ms));
 box.querySelector('.ctRefreshFacts').textContent='계좌·시세 원본 '+time+' · '+facts.text+(pending.state==='REFRESHING'?' · 새 데이터 수집 중':pending.state==='REFERENCE'?' · 이번 갱신 요청 실패 — 마지막 원본 유지':pending.state==='PARTIAL'?(pending.last_result?.errors?.master_structure?' · 보유구성 확인 실패 · 이전 보유구성 사용':pending.last_result?.errors?.tripod_signal?' · 일부 갱신 제한: TRI-POD 신호 재계산 실패 · 신호 기준일 확인 필요':' · 일부 자료 갱신 실패 · 해당 자료는 직전 원본 유지'):'')+' · 화면은 1분마다 확인';
 box.title='원본 스냅샷: '+String(live.snapshot_id||'미확인');const button=box.querySelector('button');button.disabled=pending.state==='REFRESHING';button.textContent=button.disabled?'수집 중…':'계좌·시세 최신화';
}
const FAST_REFRESH_URL='https://jjooni-ct-fast-apgynr7pea-du.a.run.app';
const FAST_REFRESH_MIN_GAP_MS=45000;
let FAST_REFRESH_BUSY=false,FAST_REFRESH_LAST=0,FAST_REFRESH_FLIGHT=null;
window.__JJOONI_FAST_ACCESS_REFRESH_V1={version:'1.0',state:'READY',last_trigger:null,last_result:null};
async function fastProof(password,bucket){
 const enc=new TextEncoder(),key=await crypto.subtle.importKey('raw',enc.encode(password),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const sig=new Uint8Array(await crypto.subtle.sign('HMAC',key,enc.encode('ct-fast:'+bucket)));
 return [...sig].map(x=>x.toString(16).padStart(2,'0')).join('');
}
function triggerFastAccessRefresh(reason){
 if(FAST_REFRESH_FLIGHT)return FAST_REFRESH_FLIGHT;
 FAST_REFRESH_FLIGHT=collectFastAccessRefresh(reason).finally(()=>{FAST_REFRESH_FLIGHT=null});
 return FAST_REFRESH_FLIGHT;
}
async function collectFastAccessRefresh(reason){
 const now=Date.now();if(FAST_REFRESH_BUSY||(reason!=='manual'&&now-FAST_REFRESH_LAST<FAST_REFRESH_MIN_GAP_MS))return;
 const pw=sessionStorage.getItem('jjooni_ct_session_pw');if(!pw)return;
 FAST_REFRESH_BUSY=true;FAST_REFRESH_LAST=now;window.__JJOONI_FAST_ACCESS_REFRESH_V1.state='REFRESHING';renderRefreshStatus();window.__JJOONI_FAST_ACCESS_REFRESH_V1.last_trigger={reason:reason||'access',at:new Date().toISOString()};
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),45000);
 try{
  const bucket=Math.floor(Date.now()/1000/30),proof=await fastProof(pw,bucket);
  const res=await fetch(FAST_REFRESH_URL+'/refresh',{method:'POST',mode:'cors',cache:'no-store',signal:ctrl.signal,headers:{'X-CT-Epoch':String(bucket),'X-CT-Proof':proof,'X-CT-Force':reason==='manual'?'true':'false'}});
  if(!res.ok)throw new Error('FAST_HTTP_'+res.status);
  const out=await res.json();if(!['PASS','PARTIAL','SKIP_RECENT'].includes(String(out.status||'')))throw new Error('FAST_STATUS_'+String(out.status||'UNKNOWN'));
  window.__JJOONI_FAST_ACCESS_REFRESH_V1.state=(out.status==='PARTIAL'||Object.keys(out.errors||{}).length)?'PARTIAL':'APPLIED';window.__JJOONI_FAST_ACCESS_REFRESH_V1.last_result={status:out.status,snapshot_id:out.snapshot_id||null,duration_ms:out.duration_ms||null,errors:out.errors||{}};
  setTimeout(refresh,400);setTimeout(refresh,1800);setTimeout(refresh,4200);
 }catch(e){window.__JJOONI_FAST_ACCESS_REFRESH_V1.state='REFERENCE';window.__JJOONI_FAST_ACCESS_REFRESH_V1.last_result={status:'REFERENCE',error:String(e&&e.message||e)};console.warn('CT FAST access refresh',e)}
 finally{clearTimeout(timer);FAST_REFRESH_BUSY=false;renderRefreshStatus()}
}

window.__JJOONI_LIVE_BRIDGE.refreshAccounts=async()=>{
 await triggerFastAccessRefresh('manual');await refresh();
 const state=window.__JJOONI_FAST_ACCESS_REFRESH_V1;
 if(state.state==='REFERENCE'||state.last_result?.errors?.master_structure)throw Error('보유구성 원본 최신화 실패');
 if(CONNECTION.state!=='READY')throw Error('최신 계좌 원본 연결 실패');
};

injectResponsiveCss();ensureWatchlistUi();refresh();document.addEventListener('jjooni:live-applied',renderRefreshStatus);renderRefreshStatus();triggerFastAccessRefresh('open');setInterval(()=>{if(!document.hidden){refresh();renderRefreshStatus();if(M.freshness(window.__JJOONI_LIVE_PAYLOAD||{}).state==='STALE')triggerFastAccessRefresh('stale-visible')}},REFRESH_MS);document.addEventListener('visibilitychange',()=>{if(!document.hidden){refresh();triggerFastAccessRefresh('resume')}});
})();

/* CT_UI_STATE_WATCHLIST_V1 */
(function(){
 'use strict';
 const KEY='jjooni_ct_active_tab_v1';
 const LABELS={overview:'OVERVIEW',accounts:'보유분석',compare:'성과분석',performance:'계좌성과',tripod:'TRI-POD',decision:'의사결정',trades:'거래내역',quality:'데이터품질',watchlist:'WATCHLIST',cost:'COST'};
 let restoring=false;

 function ensureStyle(){
   if(document.getElementById('ctUiStateStyle'))return;
   const st=document.createElement('style');st.id='ctUiStateStyle';st.textContent='#ctWatchlistSectionHead{padding:14px 10px 5px;color:#8fa4bb;font:800 9px/1 system-ui;letter-spacing:.12em;text-transform:uppercase;pointer-events:none}@media(max-width:767px){#ctWatchlistSectionHead{display:none!important}}';document.head.appendChild(st);
 }

 function ensureWatchHead(){
   const tab=document.querySelector('.tab[data-tab="watchlist"]');
   if(!tab||!tab.parentNode)return false;
   if(!document.getElementById('ctWatchlistSectionHead')){
     const h=document.createElement('div');h.id='ctWatchlistSectionHead';h.textContent='WATCHLIST';
     tab.parentNode.insertBefore(h,tab);
   }
   return true;
 }

 function pageHeading(){
   let h=document.querySelector('[data-ct-context-heading="1"]');
   if(h)return h;
   const candidates=[...document.querySelectorAll('h1,h2,.pageTitle,.page-title,.sectionTitle,.section-title')];
   h=candidates.find(x=>String(x.textContent||'').trim().toUpperCase()==='OVERVIEW');
   if(h)h.dataset.ctContextHeading='1';
   return h||null;
 }

 function syncHeading(name){
   const h=pageHeading();
   if(h&&LABELS[name])h.textContent=LABELS[name];
 }

 function save(name){
   if(!name)return;
   try{sessionStorage.setItem(KEY,name)}catch(_){}
   syncHeading(name);
 }

 function activate(name){
   if(restoring||!name)return false;
   const tab=document.querySelector('.tab[data-tab="'+CSS.escape(name)+'"]');
   if(!tab)return false;
   restoring=true;
   try{
     tab.click();
     setTimeout(()=>{
       const panel=document.getElementById('panel-'+name);
       if(panel&&!panel.classList.contains('on')){
         document.querySelectorAll('.tabPanel').forEach(x=>x.classList.remove('on'));
         panel.classList.add('on');
       }
       document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===tab));
       syncHeading(name);
       restoring=false;
     },30);
   }catch(_){restoring=false;return false}
   return true;
 }

 document.addEventListener('click',e=>{
   const t=e.target&&e.target.closest?e.target.closest('.tab[data-tab]'):null;
   if(t&&!restoring)save(t.dataset.tab);
 },true);

 function restore(){
   ensureStyle();ensureWatchHead();
   let name='overview';
   try{name=sessionStorage.getItem(KEY)||'overview'}catch(_){}
   if(activate(name))return true;
   return false;
 }

 let tries=0;
 const timer=setInterval(()=>{
   ensureStyle();ensureWatchHead();
   if(restore()||++tries>24)clearInterval(timer);
 },125);
 setTimeout(restore,0);
 setTimeout(restore,600);
 setTimeout(restore,1600);
})();


/* CT_COST_BRIDGE_LOADER_V1 */
(function(){
 if(document.getElementById('ctCostBridgeScript'))return;
 const x=document.createElement('script');
 x.id='ctCostBridgeScript';
 x.src='cost-bridge.js?v=2&_='+encodeURIComponent(window.__JJOONI_UI_RELEASE||'20261025-r5');
 x.async=true;
 (document.head||document.documentElement).appendChild(x);
})();
