(function(root){
'use strict';
function marketClock(data){return [data?.generated_kst,data?.supplemental_refreshed_kst,data?.us_rates_refreshed_kst,data?.kr_rates_refreshed_kst,data?.crypto_enriched_kst].filter(x=>Number.isFinite(Date.parse(x))).sort((a,b)=>Date.parse(b)-Date.parse(a))[0]||null}
function revision(data){return JSON.stringify([data?.generated_kst,data?.supplemental_refreshed_kst,data?.kr_rates_refreshed_kst,data?.crypto_enriched_kst,data?.us_rates_refreshed_kst,Object.entries(data?.series||{}).map(([k,rows])=>[k,rows.at(-1)]),data?.latest,data?.crypto_market,data?.tripod_latest,data?.cross_market_freshness_quality])}
function canApply(current,next){return !!next&&next.schema==='JJOONI_MARKET_OBSERVATORY_V1'&&!!next.series&&!!next.latest&&Number.isFinite(Date.parse(marketClock(next)))&&String(next.us_completed_session_date||'')>=String(current?.us_completed_session_date||'')&&Date.parse(marketClock(next))>=Date.parse(marketClock(current)||0)}
function retainHistory(current,next){if(!current?.history_loaded)return next;const series={...next.series};for(const [key,rows]of Object.entries(current.series||{})){const map=new Map(rows.map(r=>[r.date,r]));for(const row of next.series[key]||[])map.set(row.date,row);series[key]=[...map.values()].sort((a,b)=>a.date.localeCompare(b.date))}return {...next,series,history_loaded:true,history_sampling:current.history_sampling,history_base_generated_kst:current.history_base_generated_kst}}
const api={marketClock,revision,canApply,retainHistory};
if(typeof module==='object'&&module.exports){module.exports=api;return}
if(!root.document)return;
let pending=null,lastAttempt=0,lastRevision=null;
const state={version:'1.0',status:'WAITING',interval_ms:60000,refresh};root.__JJOONI_OBSERVATORY_MARKET_REFRESH=state;
function note(text){const e=document.getElementById('obsCollectMessage');if(e&&!root.__JJOONI_DATA_REFRESH?.pending)e.textContent=text}
async function refresh(force=false){
 if(pending)return pending;
 if(!force&&(document.hidden||Date.now()-lastAttempt<55000))return;
 if(typeof DATA==='undefined'||!DATA)return;
 if(lastRevision===null&&!force){lastRevision=revision(DATA);lastAttempt=Date.now();state.status='READY';return false}
 lastAttempt=Date.now();lastRevision??=revision(DATA);state.status='CHECKING';
 pending=(async()=>{try{
  // Revalidate the ETag instead of downloading a cache-busted 30Y payload each minute.
  let next;for(const path of ['./data/observatory-recent.json','./data/observatory.json']){try{const r=await fetch(force?path+'?refresh='+Date.now():path,{cache:force?'no-store':'no-cache',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('HTTP '+r.status);const candidate=await r.json();if(!canApply(DATA,candidate))throw Error('INVALID_OR_OLDER_MARKET_SNAPSHOT');next=candidate;break}catch(error){if(path.endsWith('/observatory.json'))throw error}}
  if(!canApply(DATA,next))throw Error('INVALID_OR_OLDER_MARKET_SNAPSHOT');
  const key=revision(next);state.checked_at=new Date().toISOString();state.market_collected_at=marketClock(next);
  if(key===lastRevision){state.status='UNCHANGED';if(force)note('게시값 확인 완료 · 새로 게시된 시장 데이터 없음 · 신규 원천 수집은 실행하지 않았습니다.');return false}
  // Do not move a chart while the user is inspecting an expanded view.
  if(document.querySelector('#obsFullChart.on,dialog[open]')){state.status='DEFERRED_DIALOG';return false}
  DATA=retainHistory(DATA,next);lastRevision=key;state.status='UPDATED';state.applied_at=new Date().toISOString();
  if(typeof render==='function')render();document.dispatchEvent(new CustomEvent('jjooni:observatory-market-updated',{detail:{generated_kst:next.generated_kst,market_collected_at:marketClock(next)}}));
  note('최신 게시값 반영 · 시장 수집 '+String(marketClock(next)).replace('T',' ').slice(0,16)+' KST · 원천별 기준일은 각 항목에 표시됩니다.');return true;
 }catch(e){state.status='RETRY';state.error=String(e.message||e);note('최신 게시값 조회 재시도 중 · 마지막 확인 자료 유지');return false}finally{pending=null}})();return pending;
}
setInterval(()=>refresh(),state.interval_ms);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh(true)});root.addEventListener('pageshow',event=>refresh(!!event?.persisted));
// Also cover a tab restored from the mobile browser back-forward cache.
const start=setInterval(()=>{if(typeof DATA!=='undefined'&&DATA){clearInterval(start);lastRevision=revision(DATA);lastAttempt=Date.now();state.status='READY'}},200);
})(typeof window==='object'?window:globalThis);
