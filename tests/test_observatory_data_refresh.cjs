const test=require('node:test');
const assert=require('node:assert/strict');
const {selectRun,stateFor,RUN_URL}=require('../market-observatory/data-refresh-v1.js');
const started=Date.parse('2026-10-14T21:00:00Z');
const run={id:42,event:'workflow_dispatch',head_branch:'main',created_at:'2026-10-14T21:00:10Z',status:'in_progress'};
test('opening GitHub is only waiting, never reports collection started',()=>{
  assert.equal(stateFor(null,null).state,'WAITING');
  assert.match(RUN_URL,/actions\/workflows\/market-observatory-supplemental-freshness.yml$/);
});
test('only manual main runs created after the request are selected',()=>{
  assert.equal(selectRun([{...run,id:1,event:'schedule'},{...run,id:2,head_branch:'feature'},{...run,id:3,created_at:'2026-10-14T20:59:59Z'},run],started).id,42);
  assert.equal(selectRun([run],started+60000),null);
});
test('completed collector waits for matching live publication receipt',()=>{
  const done={...run,status:'completed',conclusion:'success'};
  assert.equal(stateFor(done,null).state,'DEPLOYING');
  assert.equal(stateFor(done,{run_id:'41'}).state,'DEPLOYING');
  assert.equal(stateFor(done,{run_id:'42',sources:{market:'success'}}).state,'PUBLISHED');
});
test('one source failure is visible while independently published sources remain usable',()=>{
  assert.equal(stateFor(run,{run_id:'42',sources:{market:'success',kr_rates:'failure'}}).state,'PARTIAL');
  assert.equal(stateFor({...run,status:'completed',conclusion:'failure'},null).state,'FAILED');
});
test('queued and running jobs retain separate progress',()=>{
  assert.match(stateFor({...run,status:'queued'},null).text,/대기열/);
  assert.equal(stateFor(run,null).state,'RUNNING');
});

test('a successful process with stale source data is partial, never all-current',()=>{
  assert.equal(stateFor(run,{run_id:'42',sources:{fedwatch:'success'},quality:{source_health:'DEGRADED',degraded_sources:{fedwatch:'LAGGING'}}}).state,'PARTIAL');
});


const live=require('../market-observatory/live-market-refresh-v1.js');
const base={schema:'JJOONI_MARKET_OBSERVATORY_V1',generated_kst:'2026-10-21T04:24:29+09:00',us_completed_session_date:'2026-10-20',series:{NASDAQ100:[{date:'2026-10-20',value:100}]},latest:{NASDAQ100:100}};
test('supplemental collection advances display clock without falsifying source generation',()=>{
 const next={...base,supplemental_refreshed_kst:'2026-10-21T07:05:27+09:00'};
 assert.equal(live.marketClock(next),next.supplemental_refreshed_kst);assert.notEqual(live.revision(base),live.revision(next));assert.equal(next.generated_kst,base.generated_kst);
});
test('delayed or invalid responses never replace a newer market snapshot',()=>{
 const current={...base,supplemental_refreshed_kst:'2026-10-21T07:05:27+09:00'};
 assert.equal(live.canApply(current,base),false);assert.equal(live.canApply(base,current),true);
 assert.equal(live.canApply(current,{...current,us_completed_session_date:'2026-10-19'}),false);
 assert.equal(live.canApply(current,{...current,schema:'wrong'}),false);
});
test('refresh preserves hydrated long history while the new source corrects overlapping dates',()=>{
 const current={...base,history_loaded:true,series:{NASDAQ100:[{date:'2000-01-01',value:1},...base.series.NASDAQ100]}};
 const next={...base,series:{NASDAQ100:[{date:'2026-10-20',value:101}]},latest:{NASDAQ100:101}};
 const merged=live.retainHistory(current,next);assert.equal(merged.history_loaded,true);assert.deepEqual(merged.series.NASDAQ100,[{date:'2000-01-01',value:1},{date:'2026-10-20',value:101}]);assert.equal(current.series.NASDAQ100[1].value,100);
});

const vm=require('node:vm'),fs=require('node:fs');
test('published-value button reads market and calendar independently and always unlocks',async()=>{
 const source=fs.readFileSync(require.resolve('../market-observatory/data-refresh-v1.js'),'utf8');
 const code=source.slice(source.indexOf('async function readPublished()'),source.indexOf('\nfunction init()'));
 let marketCalls=0,calendarCalls=0,fail=false;const messages=[];
 const button={};const root={__JJOONI_OBSERVATORY_MARKET_REFRESH:{status:'UNCHANGED',refresh:async()=>{marketCalls++;if(fail)throw Error('offline');return false}},__JJOONI_OBSERVATORY_UI:{refresh_calendar:async force=>{assert.equal(force,true);calendarCalls++;return true}}};
 const context=vm.createContext({root,CAL:{},Promise,Error,readButton:button,display:(state,text)=>messages.push({state,text})});
 vm.runInContext('let readBusy=false,pending=null;'+code+';root.readPublished=readPublished;',context);
 await root.readPublished();assert.equal(marketCalls,1);assert.equal(calendarCalls,1);
 assert.equal(button.disabled,false);assert.equal(messages.at(-1).state,'READ_COMPLETE');assert.match(messages.at(-1).text,/새 게시값 없음/);
 fail=true;await root.readPublished();assert.equal(calendarCalls,2,'calendar still refreshes when the market reader fails');
 assert.equal(messages.at(-1).state,'READ_PARTIAL');assert.match(messages.at(-1).text,/시장 게시값 조회 실패/);assert.equal(button.disabled,false);
});

test('an open mobile tab updates without reload, retains nodes when unchanged and keeps last value on errors',async()=>{
 let paints=0,reads=0,fail=false;const listeners={},message={};const next={...base,supplemental_refreshed_kst:'2026-10-21T07:05:27+09:00',latest:{NASDAQ100:101}};
 const document={hidden:false,querySelector:()=>null,getElementById:()=>message,addEventListener:(n,f)=>listeners[n]=f,dispatchEvent:()=>{}};
 const context=vm.createContext({DATA:structuredClone(base),document,AbortSignal,Date,console,CustomEvent:class{},render:()=>paints++,setInterval:()=>1,clearInterval:()=>{},fetch:async()=>{reads++;if(fail)throw Error('offline');return {ok:true,json:async()=>structuredClone(next)}}});
 context.window=context;context.addEventListener=(n,f)=>listeners[n]=f;
 vm.runInContext(fs.readFileSync(require.resolve('../market-observatory/live-market-refresh-v1.js'),'utf8'),context);
 const runtime=context.__JJOONI_OBSERVATORY_MARKET_REFRESH;
 assert.equal(await runtime.refresh(true),true);assert.equal(context.DATA.latest.NASDAQ100,101);assert.equal(paints,1);
 assert.equal(await runtime.refresh(true),false);assert.equal(paints,1,'unchanged polling cannot rebuild chart nodes');
 fail=true;const confirmed=context.DATA;await runtime.refresh(true);assert.equal(context.DATA,confirmed);assert.equal(runtime.status,'RETRY');assert.ok(listeners.visibilitychange);assert.ok(listeners.pageshow);assert.equal(reads,4,'after the last-value poll fails, the recent source and full-history fallback must both be attempted');
});

test('same yield on a new observation date still changes the displayed revision',()=>{
 const next={...base,series:{NASDAQ100:[{date:'2026-10-21',value:100}]}};
 assert.notEqual(live.revision(base),live.revision(next));
});
test('independent rate collection advances the market clock',()=>{
 const next={...base,us_rates_refreshed_kst:'2026-10-21T08:00:00+09:00'};
 assert.equal(live.marketClock(next),next.us_rates_refreshed_kst);
 assert.equal(live.canApply(base,next),true);
});

test('crypto-only heartbeat advances clock and unchanged price with new provenance repaints',()=>{
 const next={...base,crypto_enriched_kst:'2026-10-21T08:00:00+09:00',crypto_market:{BTCUSD:{status:'LIVE',quote_as_of_kst:'2026-10-21T07:59:00+09:00'}}};
 assert.equal(live.marketClock(next),next.crypto_enriched_kst);
 assert.equal(live.canApply(base,next),true);
 assert.notEqual(live.revision(base),live.revision(next));
 const retry={...next,crypto_market:{BTCUSD:{...next.crypto_market.BTCUSD,status:'STALE'}}};
 assert.notEqual(live.revision(next),live.revision(retry));
});
