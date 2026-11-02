(function(root){
'use strict';
const REPO='mauveplace/jjooni-control-tower';
const WORKFLOW='market-observatory-supplemental-freshness.yml';
const RUN_URL=`https://github.com/${REPO}/actions/workflows/${WORKFLOW}`;
const API=`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&branch=main&per_page=10`;
const RECEIPT='./data/refresh-receipt.json';
const KEY='JJOONI_OBSERVATORY_REFRESH_REQUEST_V1';
const MAX_WAIT=20*60*1000;
function selectRun(runs,since){return (runs||[]).filter(r=>r.event==='workflow_dispatch'&&r.head_branch==='main'&&Date.parse(r.created_at)>=since).sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at))[0]||null;}
function stateFor(run,receipt){
  if(!run)return {state:'WAITING',text:'실행 대기 · 열린 GitHub 화면에서 Run workflow → Run workflow를 눌러 주세요.'};
  const published=receipt&&String(receipt.run_id)===String(run.id);
  if(published){const failed=Object.values(receipt.sources||{}).some(v=>v!=='success')||receipt.quality?.source_health==='DEGRADED';return {state:failed?'PARTIAL':'PUBLISHED',text:failed?'일부 원천 실패 또는 지연 · 성공한 데이터는 게시되었습니다.':'수집 결과가 게시되었습니다.',published:true};}
  if(run.status!=='completed')return {state:'RUNNING',text:run.status==='queued'?'수집 실행 대기열 · 잠시 기다려 주세요.':'데이터 수집·검증·게시 중…'};
  if(run.conclusion==='success')return {state:'DEPLOYING',text:'수집 완료 · 화면에 게시될 때까지 확인 중…'};
  return {state:'FAILED',text:'수집 또는 게시 실패 · 기존 데이터를 유지합니다. 실행 기록에서 실패 단계를 확인하세요.'};
}
const contract={selectRun,stateFor,RUN_URL,API};
if(typeof module!=='undefined'&&module.exports){module.exports=contract;return;}
if(!root.document)return;
const doc=root.document;
let pending=null,timer=null,busy=false,readBusy=false,button,message,links,readButton;
function save(){try{pending?sessionStorage.setItem(KEY,JSON.stringify(pending)):sessionStorage.removeItem(KEY);}catch(_){}}
function display(state,text){message.textContent=text;message.dataset.state=state;button.textContent=pending?'시장 수집 실행 화면 열기':'시장 원천 수집 열기';}
function stop(){if(timer)clearTimeout(timer);timer=null;pending=null;save();button.textContent='시장 원천 수집 열기';}
async function json(url,optional=false){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(12000),headers:url.startsWith('https://api.github.com/')?{Accept:'application/vnd.github+json'}:{}});if(optional&&r.status===404)return null;if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}
function reloadView(){try{sessionStorage.setItem('JJOONI_OBSERVATORY_AUTO_REFRESH_V1',JSON.stringify({tab:doc.querySelector('#tabs button.on')?.dataset.tab||'overview',scrollY:root.scrollY||0,savedAt:Date.now()}));}catch(_){}root.location.reload();}
async function poll(){
  if(!pending||busy)return;
  if(Date.now()-pending.started>MAX_WAIT){stop();display('TIMEOUT','확인 시간 초과 · 실행 기록을 확인해 주세요. 완료로 처리하지 않았습니다.');return;}
  busy=true;
  try{
    const [runs,receipt]=await Promise.allSettled([json(API),json(RECEIPT+'?cb='+Date.now(),true)]);
    if(runs.status==='rejected')throw runs.reason;
    const run=selectRun(runs.value.workflow_runs,pending.started);
    const result=stateFor(run,receipt.status==='fulfilled'?receipt.value:null);
    if(run){links.href=`https://github.com/${REPO}/actions/runs/${Number(run.id)}`;links.textContent='수집 실행 기록 ↗';}
    display(result.state,result.text);
    if(result.published){const note=result.text;stop();try{sessionStorage.setItem(KEY+'_RESULT',note);}catch(_){}reloadView();return;}
    if(result.state==='FAILED'){stop();return;}
  }catch(error){display('CHECK_FAILED','진행 상태 확인 실패 · 기존 데이터 유지. 실행 기록에서 확인할 수 있습니다.');}
  finally{busy=false;if(pending)timer=setTimeout(poll,45000);}
}
function start(){
  // GitHub hosts authentication. No access token is embedded or stored here.
  root.open(RUN_URL,'_blank','noopener,noreferrer');
  if(pending)return;
  pending={started:Date.now()};save();display('WAITING',stateFor(null,null).text);poll();
}
async function readPublished(){
  if(readBusy)return;
  readBusy=true;readButton.disabled=true;readButton.textContent='게시값 확인 중…';
  if(!pending)display('CHECKING','시장·경제일정 게시값 확인 중 · 신규 원천 수집은 실행하지 않습니다.');
  const tasks=[Promise.resolve().then(()=>{
    const live=root.__JJOONI_OBSERVATORY_MARKET_REFRESH;
    if(!live)throw Error('MARKET_READER_UNAVAILABLE');
    return live.refresh(true).then(updated=>{if(live.status==='RETRY')throw Error('MARKET_READ_FAILED');return updated});
  }),Promise.resolve().then(async()=>{
    if(typeof CAL==='undefined'||!CAL)await loadCalendar();
    const ui=root.__JJOONI_OBSERVATORY_UI;
    if(!ui||!await ui.refresh_calendar(true))throw Error('CALENDAR_READ_FAILED');
    return true;
  })];
  try{
    const results=await Promise.allSettled(tasks);
    const failed=results.flatMap((r,i)=>r.status==='rejected'?[i===0?'시장':'경제일정']:[]);
    const market=root.__JJOONI_OBSERVATORY_MARKET_REFRESH;
    const same=market?.status==='UNCHANGED';
    if(!pending)display(failed.length?'READ_PARTIAL':'READ_COMPLETE',failed.length?`${failed.join('·')} 게시값 조회 실패 · 성공한 자료는 반영, 실패한 자료는 직전 값 유지`:`게시값 확인 완료 · ${same?'시장에 새 게시값 없음':'시장 최신 게시값 확인'} · 경제일정 확인 완료 · 신규 원천 수집은 실행하지 않았습니다.`);
  }finally{readBusy=false;readButton.disabled=false;readButton.textContent='게시값 다시 확인';}
}
let nowBusy=false,nowButton,nowMessage;
async function forceNow(){
 if(nowBusy)return;
 nowBusy=true;nowButton.disabled=true;nowButton.textContent='현재 시세 조회 중…';nowMessage.textContent='지수·환율·원자재·가상자산 원천 조회 중 · 마지막 검증값 유지';
 try{
  const runtime=root.__JJOONI_OBSERVATORY_QUOTES;
  if(!runtime)throw Error('QUOTE_READER_NOT_READY');
  const result=await runtime.refresh(true);
  const count=result.fetched_count||0,total=result.expected_count||20,kept=Object.values(result.quotes||{}).filter(q=>q.refresh_status==='RETAINED').length;
  nowMessage.dataset.state=result.status;
  nowMessage.textContent=(result.cached?'최근 서버 조회 결과 확인':'시세 조회 완료')+' · '+count+'/'+total+'개 원천 응답'+(kept?' · '+kept+'개 이전 관측 유지':'')+(result.status!=='COMPLETE'?' · 일부 조회 실패':'')+' · 실제 시세 기준 시각은 각 카드에 표시';
 }catch(error){
  nowMessage.dataset.state='FAILED';nowMessage.textContent='현재 시세 조회 실패 · 마지막 값 유지 · 잠시 후 다시 눌러 주세요. 완료로 처리하지 않았습니다.';
  const published=root.__JJOONI_OBSERVATORY_MARKET_REFRESH;
  if(published){
   try{const updated=await published.refresh(true);if(published.status!=='RETRY'){
    nowMessage.dataset.state='API_FAILED_PUBLISHED';
    nowMessage.textContent='시세 API 조회 실패 · '+(updated?'최신 게시값을 대신 반영했습니다.':'게시값 재확인 · 새 게시값 없음.')+' 신규 원천 조회 완료가 아니며 코인별 관측 시각을 확인하세요.';
   }}catch(_){}
  }
 }
 finally{nowBusy=false;nowButton.disabled=false;nowButton.textContent='지금 최신화'}
}
function init(){
  const head=doc.querySelector('header.top');if(!head)return;
  const primary=doc.createElement('div');primary.className='obsNowControls';primary.innerHTML='<button id="obsForceRefresh" type="button">지금 최신화</button><div><div id="obsNowMessage" role="status" aria-live="polite">현재 시세는 카드의 관측 시각을 확인하세요.</div><small>지수·환율·원자재·가상자산 조회 · 지연 가능 · 공식 금리·경제지표는 발표 기준</small></div>';head.appendChild(primary);nowButton=primary.querySelector('#obsForceRefresh');nowMessage=primary.querySelector('#obsNowMessage');nowButton.addEventListener('click',forceNow);
  const host=doc.createElement('div');host.className='obsCollectControls';
  host.innerHTML='<div class="obsCollectActions"><button type="button" id="obsCollectRefresh">시장 원천 수집 열기</button><button type="button" id="obsReadPublished">게시값 다시 확인</button><a data-run-link target="_blank" rel="noopener noreferrer">시장 실행 기록 ↗</a><a href="https://github.com/mauveplace/jjooni-control-tower/actions/workflows/economic-calendar-light-refresh.yml" target="_blank" rel="noopener noreferrer">경제일정 수집 열기 ↗</a></div><div id="obsCollectMessage" role="status" aria-live="polite">게시값 다시 확인: 시장·경제일정 재조회 · 원천 수집 열기: GitHub에서 Run workflow 실행 필요</div>';
  host.innerHTML='<details><summary style="cursor:pointer;min-height:44px;padding:10px 0;font-weight:700">데이터 관리 · 새로고침</summary>'+host.innerHTML+'</details>';
  head.appendChild(host);button=host.querySelector('#obsCollectRefresh');message=host.querySelector('#obsCollectMessage');links=host.querySelector('[data-run-link]');links.href=RUN_URL;readButton=host.querySelector('#obsReadPublished');
  button.addEventListener('click',start);readButton.addEventListener('click',readPublished);
  try{pending=JSON.parse(sessionStorage.getItem(KEY)||'null');const result=sessionStorage.getItem(KEY+'_RESULT');if(result){message.textContent=result+' 최신 게시 데이터를 다시 읽었습니다.';sessionStorage.removeItem(KEY+'_RESULT');}}catch(_){pending=null;}
  if(pending&&Number.isFinite(pending.started))poll();else pending=null;
  doc.addEventListener('visibilitychange',()=>{if(!doc.hidden&&pending){if(timer)clearTimeout(timer);poll();}});
  root.__JJOONI_DATA_REFRESH={version:'1.1',mode:'SCHEDULE_PLUS_PUBLIC_ON_DEMAND_QUOTES',forceNow,get pending(){return !!pending},start,poll};
}
const style=doc.createElement('style');style.textContent='.obsNowControls{display:flex;align-items:center;gap:12px;margin-top:12px}.obsNowControls>button{flex-shrink:0;min-height:48px;padding:10px 18px;background:#e6f0ff;color:#123f71;border:1px solid #e6f0ff;border-radius:10px;font:800 16px/1.4 system-ui;cursor:pointer}.obsNowControls>button:disabled{opacity:.65;cursor:wait}.obsNowControls>div{min-width:0}.obsNowControls small,#obsNowMessage{font-size:12px;line-height:1.5;color:#c2d3e8;overflow-wrap:anywhere}.obsNowControls small{display:block;margin-top:4px}#obsNowMessage[data-state=FAILED],#obsNowMessage[data-state=PARTIAL]{color:#ffd3aa}@media(max-width:599px){.obsNowControls{align-items:flex-start;flex-wrap:wrap}.obsNowControls>button{width:100%}}.obsCollectControls{margin-top:10px}.obsCollectActions{display:flex;flex-wrap:wrap;align-items:center;gap:7px}.obsCollectActions button,.obsCollectActions a{font:inherit;font-size:12px;font-weight:750;min-height:36px;border:1px solid #718faf;border-radius:8px;padding:7px 11px;color:#fff;background:#183959;cursor:pointer}.obsCollectActions #obsCollectRefresh{background:#e6f0ff;color:#123f71;border-color:#e6f0ff}.obsCollectActions a{background:transparent;text-decoration:none;display:inline-flex;align-items:center}#obsCollectMessage{font-size:11px;color:#c2d3e8;margin-top:6px;line-height:1.5}#obsCollectMessage[data-state=FAILED],#obsCollectMessage[data-state=CHECK_FAILED]{color:#ffd3aa}';doc.head.appendChild(style);
init();
})(typeof window!=='undefined'?window:globalThis);

