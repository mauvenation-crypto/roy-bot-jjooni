(function(){
'use strict';
if(window.__JJOONI_VERIFIED_BOOT_OWNER&&window.__JJOONI_LIVE_READY!==true)return;
if(['ACTIVE','WAITING_FOR_SSOT','LOADING_REQUIRED_UI'].includes(window.__JJOONI_UI_BOOT_V14?.state))return;

const head=document.head||document.documentElement;
const BOOT={state:'WAITING_FOR_SSOT',version:'14.36',started_at:new Date().toISOString(),loaded:[],failed:null,nav_owner:'TRADE_REVIEW_LOADER_V14',preload_token:String(window.__JJOONI_UI_RELEASE||'20261025-r3')};
window.__JJOONI_UI_BOOT_V14=BOOT;

const DEFERRED_LABELS=new Set(['decision-impact','manual-intraday']);
BOOT.optional_failures=[];
async function loadDeferred(modules){
 for(const [id,src,label] of modules){try{await loadRequired(id,src,label)}catch(error){BOOT.optional_failures.push({label,error:String(error.message||error)});console.warn('CT optional feature unavailable',label,error)}}
 BOOT.optional_completed_at=new Date().toISOString();
}
const LABELS={overview:'Overview',portfolio:'보유분석',compare:'성과분석',accounts:'계좌성과',performance:'계좌성과',tripod:'TRI-POD',decision:'의사결정',decisions:'의사결정',trades:'거래내역',quality:'데이터품질',watchlist:'시황/워치',cost:'COST'};
function ensureBootShield(){let s=document.getElementById('ctUiBootShieldV14');if(s)return s;s=document.createElement('div');s.id='ctUiBootShieldV14';s.style.cssText='position:fixed;inset:0;z-index:100200;display:grid;place-items:center;padding:24px;background:rgba(244,247,251,.97);backdrop-filter:blur(4px);font-family:system-ui,-apple-system,sans-serif;color:#10233d;text-align:center';s.innerHTML='<div style="width:min(100%,430px);box-sizing:border-box;padding:24px;border:1px solid #d7e1ec;border-radius:18px;background:#fff;box-shadow:0 18px 60px #10233d22"><div style="font-size:12px;font-weight:900;letter-spacing:.08em;color:#60758d">CONTROL TOWER · VERIFIED BOOT</div><div id="ctUiBootTitleV14" style="margin-top:8px;font-size:20px;font-weight:900">검증된 화면 구성 중</div><div id="ctUiBootTextV14" style="margin-top:8px;font-size:13px;line-height:1.55;color:#66788b">SSOT와 필수 UI 모듈을 순서대로 확인합니다.</div><button id="ctUiBootReloadV14" type="button" style="display:none;margin:16px auto 0;padding:10px 14px;border:0;border-radius:10px;background:#0b3b70;color:#fff;font-weight:850;cursor:pointer">새로고침</button></div>';document.body.appendChild(s);const b=s.querySelector('#ctUiBootReloadV14');if(b)b.onclick=()=>location.reload();return s}
function bootText(t){const s=ensureBootShield(),e=s.querySelector('#ctUiBootTextV14');if(e)e.textContent=t}
function fail(reason){if(window.__JJOONI_ENTRY_DIAGNOSTICS){window.__JJOONI_ENTRY_DIAGNOSTICS.phase='UI_RETRY_AVAILABLE';window.__JJOONI_ENTRY_DIAGNOSTICS.last_error='UI_MODULE_UNAVAILABLE'}BOOT.state='BLOCKED';BOOT.failed=String(reason||'UNKNOWN');BOOT.failed_at=new Date().toISOString();document.documentElement.dataset.ctBoot='blocked';const s=ensureBootShield(),t=s.querySelector('#ctUiBootTitleV14'),x=s.querySelector('#ctUiBootTextV14'),b=s.querySelector('#ctUiBootReloadV14');if(t)t.textContent='화면 구성을 차단했습니다';if(x)x.textContent='필수 모듈이 완전하게 로드되지 않아 혼합 버전 화면을 표시하지 않습니다. '+BOOT.failed;if(b)b.style.display='inline-block';console.error('CT UI BOOT BLOCKED',BOOT.failed)}
function waitFor(fn,timeout,label){return new Promise((resolve,reject)=>{const st=Date.now(),tick=()=>{let ok=false;try{ok=!!fn()}catch(_){}if(ok)return resolve(true);if(Date.now()-st>timeout)return reject(new Error(label+'_TIMEOUT'));setTimeout(tick,80)};tick()})}
function runtimeReady(label){
 if(label==='master-trade-bridge')return window.__JJOONI_CT_FAST?.version==='1.7';
 if(label==='market-context')return ['ACTIVE','WAITING'].includes(window.__JJOONI_MARKET_CONTEXT_V20?.state);
 if(label==='source-authority-guard')return window.__JJOONI_SOURCE_AUTHORITY_V24?.state==='ACTIVE';
 if(label==='position-completeness')return window.__JJOONI_POSITION_COMPLETENESS_V25?.state==='ACTIVE'&&String(window.__JJOONI_POSITION_COMPLETENESS_V25.version).startsWith('25.1');
 if(label==='trade-outcomes')return window.__JJOONI_TRADE_OUTCOMES_V26?.state==='ACTIVE';
 return null;
}
function bootUrl(src){return src+(src.includes('?')?'&':'?')+'_ctboot='+encodeURIComponent(BOOT.preload_token)}
function preloadModules(modules){
 for(const [id,src,label] of modules){
  if(runtimeReady(label)===true||document.getElementById(id))continue;
  const key='ctPreload_'+id;
  if(document.getElementById(key))continue;
  const l=document.createElement('link');l.id=key;l.rel='preload';l.as='script';l.href=bootUrl(src);l.dataset.ctBootPreload='1';head.appendChild(l);
 }
 BOOT.preloaded=modules.length;
 BOOT.preload_started_at=new Date().toISOString();
}
function loadRequired(id,src,label){return new Promise((resolve,reject)=>{
 let s=document.getElementById(id),settled=false;
 const finish=(err)=>{if(settled)return;settled=true;clearTimeout(timer);if(err){BOOT.failed_module={id,src,label};reject(err);return}if(s)s.dataset.ctBootLoaded='1';if(!BOOT.loaded.includes(label))BOOT.loaded.push(label);resolve(true)};
 const done=()=>{const ready=runtimeReady(label);if(ready===false)return finish(new Error(label+'_RUNTIME_NOT_READY'));finish()};
 const timer=setTimeout(()=>finish(new Error(label+'_LOAD_TIMEOUT')),15000);
 if(runtimeReady(label)===true||s?.dataset.ctBootLoaded==='1')return done();
 if(s){s.addEventListener('load',done,{once:true});s.addEventListener('error',()=>finish(new Error(label+'_LOAD_FAILED')),{once:true});return}
 s=document.createElement('script');s.id=id;s.src=bootUrl(src);s.async=false;s.onload=done;s.onerror=()=>finish(new Error(label+'_LOAD_FAILED'));head.appendChild(s);
})}

function canonicalizeNavigation(){
 const tabs=document.querySelector('.tabs');if(!tabs)return false;
 const primary=['overview','portfolio','accounts','tripod'],retired=new Set(['ai','autobot','ai_bot']),seen=new Set(),canonical=[];
 for(const t of Array.from(tabs.querySelectorAll('.tab[data-tab]'))){
  const key=String(t.dataset.tab||'').toLowerCase();
  if(retired.has(key)){t.remove();continue}
  if(LABELS[key]&&t.textContent!==LABELS[key])t.textContent=LABELS[key];
  const canonicalKey=key==='performance'&&tabs.querySelector('.tab[data-tab="accounts"]')?'accounts':key;
  if(seen.has(canonicalKey)){if(t.style.display!=='none'||t.style.getPropertyPriority('display')!=='important')t.style.setProperty('display','none','important');t.dataset.ctNavDuplicate='1';continue}
  seen.add(canonicalKey);canonical.push(t);t.removeAttribute('data-ct-nav-duplicate');
  // Old encrypted-shell timers write inline display:none!important. The shared
  // responsive stylesheet, not those timers, owns visibility on EVERY device.
  if(t.style.getPropertyValue('display'))t.style.removeProperty('display');
  if(t.hidden)t.hidden=false;
  const wanted=primary.includes(key)?'1':'0';if(t.dataset.primary!==wanted)t.dataset.primary=wanted;
 }
 const more=document.getElementById('ctMoreTab'),menu=document.getElementById('ctMoreMenu');
 if(more){if(more.style.getPropertyValue('display'))more.style.removeProperty('display')}
 if(menu){
  const secondary=canonical.filter(t=>!primary.includes(t.dataset.tab));
  const keys=new Set(secondary.map(t=>t.dataset.tab));
  for(const b of menu.querySelectorAll('button[data-tab]'))if(!keys.has(b.dataset.tab))b.remove();
  for(const t of secondary){
   let button=Array.from(menu.querySelectorAll('button[data-tab]')).find(b=>b.dataset.tab===t.dataset.tab);
   if(!button){button=document.createElement('button');button.type='button';button.dataset.tab=t.dataset.tab;menu.appendChild(button)}
   if(button.textContent!==t.textContent)button.textContent=t.textContent;
   button.onclick=()=>{t.click();menu.classList.remove('open');document.getElementById('ctMoreBackdropV4')?.classList.remove('open');more?.setAttribute('aria-expanded','false')};
  }
 }
 tabs.dataset.ctCanonicalNavOwner='TRADE_REVIEW_LOADER_V14';document.documentElement.dataset.ctNavOwner='v14';
 BOOT.nav_signature=canonical.filter(e=>getComputedStyle(e).display!=='none').map(e=>String(e.dataset.tab)+':'+String(e.textContent||'').trim()).join('|');return true;
}
function lockNavigation(){
 canonicalizeNavigation();const tabs=document.querySelector('.tabs');if(!tabs||tabs.dataset.ctNavObservedV14)return;
 tabs.dataset.ctNavObservedV14='1';let queued=false,observedMenu=null;
 const schedule=()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;canonicalizeNavigation();watchMenu()})};
 const observer=new MutationObserver(schedule);
 observer.observe(tabs,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class','style']});
 function watchMenu(){const menu=document.getElementById('ctMoreMenu');if(menu&&menu!==observedMenu){observedMenu=menu;observer.observe(menu,{subtree:true,childList:true,characterData:true})}}
 watchMenu();
 new MutationObserver(records=>{if(records.some(r=>[...r.addedNodes,...r.removedNodes].some(n=>n.id==='ctMoreMenu')))schedule()}).observe(document.body,{childList:true});
 window.addEventListener('resize',schedule,{passive:true});
}
async function boot(){ensureBootShield();document.documentElement.dataset.ctBoot='waiting-ssot';try{bootText('Canonical SSOT 연결을 기다리는 중입니다.');await waitFor(()=>window.__JJOONI_LIVE_READY===true&&window.__JJOONI_CANONICAL_SSOT&&window.__JJOONI_LIVE_PAYLOAD,30000,'SSOT_READY');BOOT.state='LOADING_REQUIRED_UI';document.documentElement.dataset.ctBoot='loading-ui';const modules=[
['ctFastRefreshV32Script','fast-refresh-v32.js?v=32.3','master-trade-bridge'],
['ctMarketStateBridgeV14Script','market-state-bridge.js?v=2.2','market-state'],
['ctUiRefactorV14Script','ui-refactor.js?v=1.12-stable-overview','ui-refactor'],
['ctDataIntegrityV4Script','data-integrity-v4.js?v=4','data-integrity'],
['ctSecurityNamesV1Script','security-names-held-v1.js?v=1.0','security-names'],
['ctTradeReviewV2Script','trade-review-v2.js?v=2.1','trade-review'],
['ctTradeReviewReadableV3Script','trade-review-readable-v3.js?v=3.2','trade-readable'],
['ctMobileStabilityV4Script','mobile-stability-v4.js?v=4.6-holdings','mobile-stability'],
['ctDecisionImpactV5Script','decision-impact-v5.js?v=5.2','decision-impact'],
['ctRealizedLedgerV7Script','realized-ledger-v7.js?v=7.3','realized-ledger'],
['ctTradeMoneyV6Script','trade-money-v6.js?v=6.2','trade-money'],
['ctTradeOutcomeV26Script','trade-review-outcomes-v26.js?v=26.8','trade-outcomes'],
['ctAccountSourceTruthV22Script','account-source-truth-v22.js?v=22.4-pnl-scope','account-source-truth'],
['ctHumanUiV6Script','human-ui-v6.js?v=6.6-price-proof','human-ui'],
['ctViewportBottomGuardV5Script','viewport-bottom-guard-v5.js?v=5','viewport-guard'],
['ctTabletRuntimeV8Script','tablet-runtime-v8.js?v=8.3','tablet-runtime'],
['ctTabletAccountsV8Script','tablet-accounts-v8.js?v=8.7-holdings','tablet-accounts'],
['ctRecentTradeMetricV9Script','recent-trade-metric-drilldown-v9.js?v=9.2','recent-trade-drill'],
['ctCanonicalValuationV13Script','canonical-valuation-fix-v13.js?v=13.1','valuation'],
['ctFxAttributionV16Script','fx-attribution-v16.js?v=16.2','fx-attribution'],
['ctMetricDrillV12Script','metric-drilldown-router-v12.js?v=12.4-holdings','metric-router'],
['ctDailyPerformanceAliasV23Script','daily-performance-alias-v23.js?v=23.1','daily-performance-alias'],
['ctRuntimeIntegrityV15Script','runtime-integrity-v15.js?v=15.6','runtime-integrity'],
['ctAccountIntegrityV17Script','account-integrity-v17.js?v=17.5','account-integrity'],
['ctIrpTradeUnitGuardV18Script','irp-trade-unit-guard-v18.js?v=18.0','irp-trade-unit-guard'],
['ctDrilldownReadabilityV19Script','drilldown-readability-v19.js?v=19.4','drilldown-readability'],
['ctMarketContextV20Script','market-context-v20.js?v=20.1-accounts-first','market-context'],
['ctPerformanceDayViewScript','performance-day-view.js?v=1.3-account-comparisons','performance-day-view'],
['ctOverviewConsistencyV21Script','overview-consistency-v21.js?v=21.10-stable-type','overview-consistency'],
['ctSourceAuthorityGuardV24Script','source-authority-guard-v24.js?v=24.4','source-authority-guard'],
['ctStrategyBooksV1Script','strategy-books-v1.js?v=2.13-broker-evidence','strategy-books'],
['ctManualIntradayV1Script','manual-intraday-v1.js?v=2.1-touch','manual-intraday'],
['ctPositionCompletenessV25Script','position-completeness-v25.js?v=25.1.3','position-completeness'],['ctTabletStabilityV37Script','tablet-stability-v37.js?v=37.12-nav-owner','tablet-stability']];preloadModules(modules.filter(x=>!DEFERRED_LABELS.has(x[2])));for(const [id,src,label] of modules.filter(x=>!DEFERRED_LABELS.has(x[2]))){bootText('필수 모듈 확인 · '+label);await loadRequired(id,src,label)}if(runtimeReady('source-authority-guard')!==true||runtimeReady('position-completeness')!==true||runtimeReady('trade-outcomes')!==true||runtimeReady('master-trade-bridge')!==true)throw Error('REQUIRED_DETAIL_RUNTIME_MISSING');await waitFor(()=>!!document.getElementById('ctResponsiveLayout')?.sheet,15000,'RESPONSIVE_STYLE');lockNavigation();if(!canonicalizeNavigation())throw new Error('CANONICAL_NAV_NOT_FOUND');BOOT.state='ACTIVE';if(window.__JJOONI_ENTRY_DIAGNOSTICS){window.__JJOONI_ENTRY_DIAGNOSTICS.phase='READY';window.__JJOONI_ENTRY_DIAGNOSTICS.last_error=null}BOOT.completed_at=new Date().toISOString();document.documentElement.dataset.ctBoot='ready';const shield=document.getElementById('ctUiBootShieldV14');if(shield)shield.remove();const ssotShield=document.getElementById('ctSsotSafetyShield');if(ssotShield&&window.__JJOONI_LIVE_READY===true)ssotShield.remove();console.info('CT UI BOOT ACTIVE',BOOT);setTimeout(()=>loadDeferred(modules.filter(x=>DEFERRED_LABELS.has(x[2]))),0)}catch(e){fail(e&&e.message||e)}}
boot();
})();
