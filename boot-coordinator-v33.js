(function(){
'use strict';
if(typeof window!=='object'||typeof document!=='object')return;
if(window.__JJOONI_BOOT_COORDINATOR_V33)return;

const S={version:'34.1',state:'WAITING_FOR_LIVE',started_at:new Date().toISOString(),pulses:0,last_diag:null};
window.__JJOONI_BOOT_COORDINATOR_V33=S;

function factsReady(){return !!(window.__JJOONI_CANONICAL_SSOT&&window.__JJOONI_LIVE_PAYLOAD)}
function lineageReady(){
 const g=window.__JJOONI_LINEAGE_GUARD;
 return !!(g&&String(g.version||'').length&&g.policy);
}
function verifiedReady(){return factsReady()&&lineageReady()}
function scriptLoaded(name){return [...document.scripts].some(s=>String(s.src||'').includes(name))}
function bridgeDiag(){
 const feed=window.__JJOONI_FEED_CONNECTION,b=document.getElementById('ctEncryptedLiveBadge');
 const text=String(b?.textContent||'').trim(),title=String(b?.title||'').trim();
 if(feed?.state==='BLOCKED'||b?.dataset?.ctConnectionState==='BLOCKED'||/SSOT BLOCKED/.test(text))return {kind:'blocked',message:feed?.last_error||title||text};
 if(feed?.state==='RETRYING'||feed?.state==='DEGRADED'||b?.dataset?.ctConnectionState==='RETRYING')return {kind:'retrying',message:feed?.last_error||'계좌 연결 재시도 중'};
 // A legacy WAIT label (and its stale tooltip) is not proof of an auth failure.
 if(/WAIT|대기/i.test(text))return {kind:'retrying',message:title||'계좌 연결 대기'};
 return {kind:'pending',message:null};
}
function ensureShield(){
 let s=document.getElementById('ctUiBootShieldV14');
 if(!s){
  s=document.createElement('div');s.id='ctUiBootShieldV14';
  s.style.cssText='position:fixed;inset:0;z-index:100200;display:grid;place-items:center;padding:24px;background:rgba(244,247,251,.97);backdrop-filter:blur(4px);font-family:system-ui,-apple-system,sans-serif;color:#10233d;text-align:center';
  s.innerHTML='<div style="width:min(100%,430px);box-sizing:border-box;padding:24px;border:1px solid #d7e1ec;border-radius:18px;background:#fff;box-shadow:0 18px 60px #10233d22"><div style="font-size:12px;font-weight:900;letter-spacing:.08em;color:#60758d">CONTROL TOWER · VERIFIED BOOT</div><div id="ctUiBootTitleV14" style="margin-top:8px;font-size:20px;font-weight:900">실시간 데이터 연결 중</div><div id="ctUiBootTextV14" style="margin-top:8px;font-size:13px;line-height:1.55;color:#66788b">검증된 SSOT가 준비되면 화면 모듈을 시작합니다.</div><button id="ctUiBootReloadV14" type="button" style="display:none;margin:16px auto 0;padding:10px 14px;border:0;border-radius:10px;background:#0b3b70;color:#fff;font-weight:850;cursor:pointer">새로고침</button></div>';
  document.body.appendChild(s);
 }
 return s;
}
function paint(text,failed){
 const s=ensureShield(),t=s.querySelector('#ctUiBootTitleV14'),x=s.querySelector('#ctUiBootTextV14'),b=s.querySelector('#ctUiBootReloadV14');
 if(t)t.textContent=failed?'계좌 연결 확인이 필요합니다':'실시간 데이터 연결 중';
 S.last_paint_failed=!!failed;S.last_message=text;
 if(x)x.textContent=text;
 if(b){b.style.display=failed?'inline-block':'none';b.onclick=()=>location.reload()}
}
function nudge(){
 S.pulses++;
 // Recovery requests only the encrypted feed. A synthetic visibility event
 // also wakes master sync, quote refresh and every legacy UI observer.
 window.__JJOONI_LIVE_BRIDGE?.requestRefresh?.('boot-recovery');
 // Existing verified SSOT should open first. FAST refresh is a post-open freshness
 // improvement, not a prerequisite for rendering the dashboard.
 if(S.pulses>8){try{window.__JJOONI_CT_FAST?.kick?.()}catch(_){}}
}
function startVerifiedUi(){
 if(S.state==='UI_LOADING'||S.state==='ACTIVE'||S.state==='UI_LOADER_STARTED')return;
 S.state='UI_LOADING';S.last_diag=null;S.last_paint_failed=false;if(window.__JJOONI_ENTRY_DIAGNOSTICS)window.__JJOONI_ENTRY_DIAGNOSTICS.phase='LOADING_UI';S.live_ready_at=new Date().toISOString();
 window.__JJOONI_LIVE_READY=true;
 const ss=document.getElementById('ctSsotSafetyShield');if(ss)ss.remove();
 const old=document.getElementById('ctUiBootShieldV14');if(old)old.remove();
 window.__JJOONI_UI_BOOT_V14=null;
 const s=document.createElement('script');
 s.id='ctVerifiedUiLoaderV33';
 document.getElementById('ctVerifiedUiLoaderV33')?.remove();
 s.src='trade-review-loader.js?v=14.37-broker-evidence&_='+encodeURIComponent(window.__JJOONI_UI_RELEASE||'20261025-r5');
 s.async=false;
 s.onload=()=>{S.state='UI_LOADER_STARTED';S.ui_loader_at=new Date().toISOString()};
 s.onerror=()=>{S.state='UI_LOADER_LOAD_FAILED';S.failed_at=new Date().toISOString();paint('UI 로더 파일을 불러오지 못했습니다. 새로고침 없이 재시도합니다.',true);setTimeout(startVerifiedUi,1500)};
 (document.head||document.documentElement).appendChild(s);
}

// This coordinator is the only owner allowed to (re)start the UI loader.
S.retry=()=>{
 if(!verifiedReady()||window.__JJOONI_UI_BOOT_V14?.state==='ACTIVE')return false;
 if(window.__JJOONI_UI_BOOT_V14?.state==='BLOCKED')S.state='WAITING_FOR_LIVE';
 startVerifiedUi();return true;
};

// Only the verified coordinator starts the UI loader. No fabricated ACTIVE hold.
paint('저장된 검증 SSOT를 먼저 연결합니다. 최신 FAST 갱신은 화면 진입 후 이어집니다.',false);

let lastPaint=0;
const timer=setInterval(()=>{
 if(verifiedReady()){
  clearInterval(timer);startVerifiedUi();return;
 }
 const now=Date.now();
 if(now-lastPaint>2000){
  lastPaint=now;
  const sec=Math.max(0,Math.round((now-Date.parse(S.started_at))/1000));
  if(!factsReady()){
   const lg=scriptLoaded('lineage-guard.js'),lb=scriptLoaded('live-bridge.js'),diag=bridgeDiag();S.last_diag=diag.message;
   window.__JJOONI_BOOT_DIAG={sec,lineage_script:lg,live_bridge_script:lb,bridge_error:diag.kind==='pending'?null:diag.message,at:new Date().toISOString()};
   if(diag.kind==='blocked'){paint('계좌 원본 검증에 실패했습니다. 다시 연결해 주세요.',true)}
   else if(diag.kind==='retrying'){paint(sec<30?'계좌 연결을 다시 시도하고 있습니다. 승인된 기기 정보는 유지됩니다.':'계좌 연결이 지연되고 있습니다. 다시 연결하거나 네트워크를 확인해 주세요.',sec>=30)}
   else if(sec>=6&&!lg){paint('LINEAGE GUARD 스크립트가 시작되지 않았습니다. · '+sec+'초',true)}
   else if(sec>=8&&lg&&!lb){paint('LIVE BRIDGE 스크립트가 시작되지 않았습니다. · '+sec+'초',true)}
   else paint('SSOT 읽기/복호화 · '+sec+'초 · bridge='+(lb?'ON':'WAIT')+' · lineage='+(lg?'ON':'WAIT'),false);
  }else if(!lineageReady()){
   window.__JJOONI_BOOT_DIAG={sec,lineage_script:scriptLoaded('lineage-guard.js'),live_bridge_script:scriptLoaded('live-bridge.js'),bridge_error:bridgeDiag().message,at:new Date().toISOString()};
   paint('SSOT는 도착했지만 LINEAGE GUARD 확인 대기 · '+sec+'초',sec>=8);
  }else paint('UI 준비 · '+sec+'초',false);
 }
 nudge();
},900);

document.addEventListener('jjooni:live-applied',()=>{if(verifiedReady()){clearInterval(timer);startVerifiedUi()}},{passive:true});
})();
