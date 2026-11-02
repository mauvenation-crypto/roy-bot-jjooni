const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const read=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');

test('manual refresh retries after automatic collection and allows the server collection budget',async()=>{
 const source=read('live-bridge.js');let calls=0;const timers=[];
 const context={window:{__JJOONI_LIVE_BRIDGE:{}},CONNECTION:{state:"READY"},Date,TextEncoder,AbortController,sessionStorage:{getItem:()=> 'test-only'},
  crypto:require('node:crypto').webcrypto,renderRefreshStatus(){},refresh(){},console,
  setTimeout(fn,ms){timers.push(ms);return timers.length},clearTimeout(){},
  fetch:async()=>{calls++;return {ok:true,json:async()=>({status:'PASS',snapshot_id:'new'})}}};
 vm.runInNewContext(source.slice(source.indexOf('const FAST_REFRESH_URL='),source.indexOf('\ninjectResponsiveCss();ensureWatchlistUi();refresh();'))+'window.collect=triggerFastAccessRefresh;',context);
 await context.window.collect('open');
 await context.window.collect('resume');assert.equal(calls,1,'automatic retries stay throttled');
 await context.window.collect('manual');assert.equal(calls,2,'explicit tap cannot silently do nothing');
 assert(timers.includes(45000),'cold request must cover read + collection + publication');
 assert.equal(context.window.__JJOONI_FAST_ACCESS_REFRESH_V1.state,'APPLIED');
 context.fetch=async()=>({ok:true,json:async()=>({status:'PARTIAL',snapshot_id:'partial',errors:{tripod_signal:'RuntimeError'}})});
 await context.window.collect('manual');
 assert.equal(context.window.__JJOONI_FAST_ACCESS_REFRESH_V1.state,'PARTIAL');
 assert.equal(context.window.__JJOONI_FAST_ACCESS_REFRESH_V1.last_result.errors.tripod_signal,'RuntimeError');
});

function feedRuntime(reader){
  const source=read('live-bridge.js');
  const start=source.indexOf('let refreshFlight=null');
  const end=source.indexOf('\nfunction renderRefreshStatus()',start);
  // Isolate scheduling from crypto/DOM rendering, retaining the production
  // single-flight and recovery throttling functions unchanged.
  const code=source.slice(start,end).replace(/async function readEncryptedFeed\(\)\{.*\}\nfunction requestRefresh/s,
    'async function readEncryptedFeed(){return reader()}\nfunction requestRefresh');
  let now=100000;
  const context={window:{},document:{hidden:false},reader,Promise,Date:{now:()=>now}};
  vm.runInNewContext(code,context);
  return {api:context.window.__JJOONI_LIVE_BRIDGE,document:context.document,advance:ms=>{now+=ms}};
}

test('manual, resume and recovery consumers share the same pending feed read',async()=>{
  let calls=0,complete;
  const r=feedRuntime(()=>{calls++;return new Promise(resolve=>{complete=resolve})});
  const first=r.api.refresh();
  assert.equal(r.api.refresh(),first);
  assert.equal(r.api.requestRefresh('boot'),first);
  assert.equal(calls,1);
  complete('done');
  await first;
  const second=r.api.refresh();
  assert.equal(calls,2);
  complete();await second;
});

test('failed reads release the flight, and recovery is bounded independently of UI pulses',async()=>{
  let calls=0;
  const r=feedRuntime(async()=>{calls++;if(calls===1)throw Error('offline')});
  await assert.rejects(r.api.requestRefresh('boot'),/offline/);
  for(let i=0;i<5;i++){r.advance(900);await r.api.requestRefresh('boot')}
  assert.equal(calls,1);
  r.advance(500);await r.api.requestRefresh('boot');
  assert.equal(calls,2);
  r.document.hidden=true;r.advance(5000);await r.api.requestRefresh('boot');
  assert.equal(calls,2);
});

test('loader re-entry during WAITING_FOR_SSOT cannot replace the boot owner',()=>{
  const source=read('trade-review-loader.js');
  const code=source.slice(0,source.lastIndexOf('boot();'))+'})();';
  const window={},context={window,document:{head:{},documentElement:{}},Date,console};
  vm.runInNewContext(code,context);
  const owner=window.__JJOONI_UI_BOOT_V14;
  vm.runInNewContext(code,context);
  assert.equal(window.__JJOONI_UI_BOOT_V14,owner);
  assert.equal(owner.state,'WAITING_FOR_SSOT');
});

test('boot and master recovery do not broadcast fake browser lifecycle events',()=>{
  for(const file of ['boot-coordinator-v33.js','fast-refresh-v32.js']){
    assert.doesNotMatch(read(file),/dispatchEvent\(new Event\(['"]visibilitychange/);
    assert.match(read(file),/__JJOONI_LIVE_BRIDGE\?\.requestRefresh/);
  }
  const fast=read('fast-refresh-v32.js');
  assert.doesNotMatch(fast,/s\.src='trade-review-loader/);
});

test('unchanged master receipts retain trade array and do not request a redraw, but corrections do',()=>{
 const source=read('fast-refresh-v32.js'),window={},D={human:{trades:[]}},context={window,D,console,Date};
 vm.runInNewContext(source.slice(0,source.indexOf('window.__JJOONI_CT_FAST={'))+'window.applyMasterTrades=applyMasterTrades;})();',context);
 const receipt={master_overlay:{trade_overlay:{schema:'JJOONI_CT_MASTER_TRADE_OVERLAY_V1',rows:[{account:'TOSS',ticker:'TQQQ',side:'BUY',trade_date:'2026-10-19',qty:1,price:10}]}}};
 assert.equal(window.applyMasterTrades(receipt,'test'),true);const prior=D.human.trades;
 assert.equal(window.applyMasterTrades(receipt,'repeat'),false);assert.equal(D.human.trades,prior);
 receipt.master_overlay.trade_overlay.rows[0].price=11;
 assert.equal(window.applyMasterTrades(receipt,'correction'),true);assert.equal(D.human.trades.length,1);assert.equal(D.human.trades[0].price,11);
});
