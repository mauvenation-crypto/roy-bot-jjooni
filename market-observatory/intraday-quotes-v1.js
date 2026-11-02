(function(root){
'use strict';
const ENDPOINT='https://jjooni-ct-fast-apgynr7pea-du.a.run.app/observatory/quotes';
const KEYS=new Set(['NASDAQ100','NASDAQCOMPOSITE','SP500','DOW','RUSSELL2000','VIX','KOSPI','KOSDAQ','USDKRW','USDJPY','JPYKRW','DXY','WTI','BRENT','NATGAS','GOLD','SILVER','COPPER','BTCUSD','ETHUSD']);
function valid(row,key,now=Date.now()){
 return !!row&&KEYS.has(key)&&row.key===key&&typeof row.value==='number'&&Number.isFinite(row.value)&&row.value>0&&Number.isFinite(Date.parse(row.observed_at))&&Date.parse(row.observed_at)<=now+120000;
}
function merge(previous,payload,now=Date.now()){
 if(payload?.schema!=='JJOONI_OBSERVATORY_QUOTES_V1'||!payload.quotes)throw Error('INVALID_QUOTES_RESPONSE');
 const quotes={...previous};
 for(const [key,row] of Object.entries(payload.quotes)){
  if(!valid(row,key,now))continue;
  if(quotes[key]&&Date.parse(quotes[key].observed_at)>Date.parse(row.observed_at))continue;
  // Recompute against the provided baseline; missing values never become zero.
  const base=typeof row.previous_close==='number'&&Number.isFinite(row.previous_close)&&row.previous_close>0?row.previous_close:null;
  quotes[key]={...row,previous_close:base,change_pct:base==null?null:(row.value/base-1)*100};
 }
 return quotes;
}
function quality(row,now=Date.now()){
 const stale=['REGULAR','CONTINUOUS'].includes(row?.market_state)&&now-Date.parse(row?.observed_at)>1200000;
 return row?.refresh_status==='RETAINED'?'이전 관측 유지':stale||row?.quality==='STALE'?'관측 지연':row?.market_state==='CLOSED'?'최근 마감 관측':'장중 관측 · 지연 가능';
}
function select(row,publishedAt,now=Date.now()){
 if(!row||!valid(row,row.key,now))return null;
 if(Number.isFinite(Date.parse(publishedAt))&&Date.parse(publishedAt)>Date.parse(row.observed_at))return null;
 return row;
}
const api={ENDPOINT,valid,merge,quality,select};
if(typeof module==='object'&&module.exports){module.exports=api;return}
if(!root.document)return;
let quotes={},pending=null;
const state={version:'1.0',status:'WAITING',result:null,paintSummary,get:(key,publishedAt)=>{const q=select(quotes[key],publishedAt);if(!q)return null;const row=state.status==='FAILED'?{...q,refresh_status:'RETAINED'}:q;return {...row,display_status:quality(row)}},refresh};
root.__JJOONI_OBSERVATORY_QUOTES=state;
function paintSummary(){
 const host=document.getElementById?.('overviewKpis');if(!host)return;
 for(const cell of host.querySelectorAll('.kpi')){
  const label=cell.querySelector('small'),value=cell.querySelector('b'),key=label?.textContent.split(' · ')[0];
  const q=state.get(key);if(!q||!value)continue;
  const text=q.value.toLocaleString('ko-KR',{maximumFractionDigits:2});
  if(value.textContent!==text)value.textContent=text;
  const title=key+' · '+(q.refresh_status==='RETAINED'?'이전 관측':'최근 시세');if(label.textContent!==title)label.textContent=title;
 }
}
async function refresh(force=false){
 if(pending)return pending;
 state.status='CHECKING';
 pending=(async()=>{
  try{
   const response=await fetch(ENDPOINT+(force?'?force=1':''),{cache:'no-store',credentials:'omit',signal:AbortSignal.timeout(22000)});
   if(!response.ok)throw Error('QUOTE_HTTP_'+response.status);
   const result=await response.json();quotes=merge(quotes,result);
   if(!Object.keys(quotes).length)throw Error('NO_VALID_QUOTES');
   state.result=result;state.status=result.status==='COMPLETE'?'COMPLETE':'PARTIAL';
   root.__JJOONI_LATEST_BOARD?.render?.();
   document.dispatchEvent(new CustomEvent('jjooni:observatory-quotes-updated'));
   return result;
  }catch(error){
   state.status='FAILED';state.error=String(error.message||error);
   const message=document.getElementById?.('obsNowMessage');
   if(message){message.dataset.state='FAILED';message.textContent='현재 시세 API 조회 실패 · 마지막 검증값 유지 · 지금 최신화로 재시도할 수 있습니다.'}
   root.__JJOONI_LATEST_BOARD?.render?.();
   throw error
  }
  finally{pending=null}
 })();return pending;
}
// One cached read on open. Further source collection belongs to the user's
// explicit button, with server-side coalescing; no new polling or scheduler.
refresh(false).catch(()=>{});
})(typeof window==='object'?window:globalThis);
