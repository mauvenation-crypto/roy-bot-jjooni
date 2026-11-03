
(function(){
'use strict';
if(typeof window!=='object'||typeof document!=='object')return;

// Explicit application bootstrap; metrics stays a pure calculation module.
window.__JJOONI_VERIFIED_BOOT_OWNER=true;
if(!window.__JJOONI_BOOT_COORDINATOR_BOOTSTRAPPED){
 window.__JJOONI_BOOT_COORDINATOR_BOOTSTRAPPED=true;
 const c=document.createElement('script');
 c.src='boot-coordinator-v33.js?v=33.1-broker-evidence&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
 c.async=false;
 c.onerror=()=>{console.warn('CT boot coordinator load failed')};
 (document.head||document.documentElement).appendChild(c);
}

// Stability boundary: public-market sidecar contains no account/order data and
// therefore can refresh market/TRI-POD daily facts independently of private KIS.
if(!window.__JJOONI_PUBLIC_MARKET_SIDECAR_BOOTSTRAPPED){
 window.__JJOONI_PUBLIC_MARKET_SIDECAR_BOOTSTRAPPED=true;
 const p=document.createElement('script');
 p.src='public-market-sidecar-v36.js?v=36.0&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
 p.async=false;
 p.onerror=()=>console.warn('CT public market sidecar load failed');
 (document.head||document.documentElement).appendChild(p);
}

// Read-only market/VIX presentation guard.
if(!window.__JJOONI_TRIPOD_VIX_AUTHORITY_BOOTSTRAPPED){
 window.__JJOONI_TRIPOD_VIX_AUTHORITY_BOOTSTRAPPED=true;
 const v=document.createElement('script');
 v.src='consultant-tab-hotfix-v31.js?v=31.6&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
 v.async=false;
 v.onerror=()=>console.warn('CT market/VIX presentation guard load failed');
 (document.head||document.documentElement).appendChild(v);
}

// Toss account-basis authority: current total asset must match the same
// canonical NAV used by the Control Tower overview. Historical NAV stays a
// performance-basis field and is never presented as the current total asset.
if(!window.__JJOONI_TOSS_ACCOUNT_BASIS_BOOTSTRAPPED){
 window.__JJOONI_TOSS_ACCOUNT_BASIS_BOOTSTRAPPED=true;
 const t=document.createElement('script');
 t.src='toss-account-basis-v43.js?v=43.3-compact&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
 t.async=false;
 t.onerror=()=>console.warn('CT Toss account-basis authority load failed');
 (document.head||document.documentElement).appendChild(t);
}

// Fresh mixed-benchmark excess return. This card is a same-day analytic and
// must not depend on the stale historical PB ledger.
if(!window.__JJOONI_BENCHMARK_EXCESS_BOOTSTRAPPED){
 window.__JJOONI_BENCHMARK_EXCESS_BOOTSTRAPPED=true;
 const b=document.createElement('script');
 b.src='benchmark-excess-v1.js?v=1.1&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
 b.async=false;
 b.onerror=()=>console.warn('CT benchmark excess surface load failed');
 (document.head||document.documentElement).appendChild(b);
}

// Investor-flow surface: renders market-wide KOSPI/KOSDAQ flow separately
// from per-stock KIS estimate slots and consumes the server-side regime SSOT.
if(!window.__JJOONI_INVESTOR_FLOW_BOOTSTRAPPED){
 window.__JJOONI_INVESTOR_FLOW_BOOTSTRAPPED=true;
 const f=document.createElement('script');
 f.src='investor-flow-v1.js?v=1.0&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
 f.async=false;
 f.onerror=()=>console.warn('CT investor flow surface load failed');
 (document.head||document.documentElement).appendChild(f);
}

// Stability-first TRI-POD daily surface. The decrypted legacy card is historical
// and remains quarantined unless a complete verified daily signal is available.
if(!window.__JJOONI_TRIPOD_DAILY_GUARD_BOOTSTRAPPED){
 window.__JJOONI_TRIPOD_DAILY_GUARD_BOOTSTRAPPED=true;
 const d=document.createElement('script');
 d.src='tripod-daily-freshness-v35.js?v=35.1&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
 d.async=false;
 d.onerror=()=>console.warn('CT TRI-POD daily freshness guard load failed');
 (document.head||document.documentElement).appendChild(d);
}

if(window.__JJOONI_CT_FAST_BOOTSTRAPPED)return;
window.__JJOONI_CT_FAST_BOOTSTRAPPED=true;
const s=document.createElement('script');
s.src='fast-refresh-v32.js?v=1&_='+(window.__JJOONI_UI_RELEASE||'20261025-r3');
s.async=true;
s.onerror=()=>console.warn('CT FAST client load failed');
(document.head||document.documentElement).appendChild(s);
})();