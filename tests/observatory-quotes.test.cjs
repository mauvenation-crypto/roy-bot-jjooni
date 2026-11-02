const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const Q=require('../market-observatory/intraday-quotes-v1.js');
const now=Date.parse('2026-10-30T16:00:00Z');
const row={key:'NASDAQ100',value:103,previous_close:100,observed_at:'2026-10-30T15:59:00Z',session_date:'2026-10-30',market_state:'REGULAR',refresh_status:'FETCHED'};
const payload=q=>({schema:'JJOONI_OBSERVATORY_QUOTES_V1',quotes:{NASDAQ100:q},status:'COMPLETE',fetched_count:1,expected_count:20});
test('quote validation rejects wrong symbols, future clocks, invalid values and private keys',()=>{
 assert(Q.valid(row,'NASDAQ100',now));
 for(const r of [{...row,value:null},{...row,value:'103'},{...row,value:Infinity},{...row,key:'QQQ'},{...row,observed_at:'2026-10-30T17:00:00Z'}])assert(!Q.valid(r,'NASDAQ100',now));
 assert(!Q.valid({...row,key:'accounts'},'accounts',now));
});
test('intraday change uses the source baseline and missing is unknown',()=>{
 const quotes=Q.merge({},payload({...row,change_pct:-999}),now);
 assert.equal(quotes.NASDAQ100.change_pct,3.0000000000000027);
 assert.equal(Q.merge({},payload({...row,previous_close:null}),now).NASDAQ100.change_pct,null);
 assert.equal(Q.merge({},payload({...row,previous_close:0}),now).NASDAQ100.previous_close,null);
});
test('older response cannot regress a later observation and original data is untouched',()=>{
 const first=Q.merge({},payload(row),now),before=JSON.stringify(first);
 const next=Q.merge(first,payload({...row,value:99,observed_at:'2026-10-29T16:00:00Z'}),now);
 assert.equal(next.NASDAQ100.value,103);assert.equal(JSON.stringify(first),before);
 assert.equal(Q.quality({...row,refresh_status:'RETAINED'},now),'이전 관측 유지');
 assert.equal(Q.quality({...row,observed_at:'2026-10-30T15:00:00Z'},now),'관측 지연');
 assert.equal(Q.quality({...row,market_state:'CLOSED'},now),'최근 마감 관측');
});
test('runtime coalesces requests, updates board, preserves previous values after failure',async()=>{
 let reads=0,paints=0,fail=false;
 const live={...row,observed_at:new Date(Date.now()-60000).toISOString()};
 const context=vm.createContext({document:{dispatchEvent(){}},CustomEvent:class{},AbortSignal,Date,Promise,Error,console,
  fetch:async()=>{reads++;if(fail)throw Error('offline');return {ok:true,json:async()=>payload(live)}}});
 context.window=context;context.__JJOONI_LATEST_BOARD={render:()=>paints++};
 vm.runInContext(fs.readFileSync('market-observatory/intraday-quotes-v1.js','utf8'),context);
 const runtime=context.__JJOONI_OBSERVATORY_QUOTES;
 await Promise.all([runtime.refresh(true),runtime.refresh(true)]);
 assert.equal(reads,1);assert.equal(paints,1);assert.equal(runtime.get('NASDAQ100').value,103);
 fail=true;await assert.rejects(runtime.refresh(true));
 assert.equal(runtime.status,'FAILED');assert.equal(runtime.get('NASDAQ100').value,103);assert.equal(paints,2);assert.equal(runtime.get('NASDAQ100').display_status,'이전 관측 유지');
});
test('one button click locks until completion and failure always releases it',async()=>{
 const source=fs.readFileSync('market-observatory/data-refresh-v1.js','utf8');
 const code=source.slice(source.indexOf('let nowBusy='),source.indexOf('\nfunction init()'));
 const button={},message={dataset:{}},root={};let calls=0,release;
 root.__JJOONI_OBSERVATORY_QUOTES={refresh:()=>{calls++;return new Promise(r=>release=r)}};
 const context=vm.createContext({root,Error,Object,Promise});
 vm.runInContext(code+';root.force=forceNow;root.controls=(b,m)=>{nowButton=b;nowMessage=m}',context);root.controls(button,message);
 const pending=root.force();await root.force();assert.equal(calls,1);assert.equal(button.disabled,true);
 release(payload(row));await pending;assert.equal(button.disabled,false);assert.match(message.textContent,/시세 조회 완료/);
 root.__JJOONI_OBSERVATORY_QUOTES.refresh=async()=>{throw Error('offline')};await root.force();
 assert.equal(button.disabled,false);assert.equal(message.dataset.state,'FAILED');assert.match(message.textContent,/마지막 값 유지/);
});

test('newer published crypto observation wins over a cached API quote',()=>{
 assert.equal(Q.select(row,'2026-10-30T16:00:00Z',now),null);
 assert.equal(Q.select(row,'2026-10-30T15:58:00Z',now),row);
 assert.equal(Q.select(row,null,now),row);
 assert.equal(Q.select({...row,observed_at:'invalid'},null,now),null);
});
test('API failure rechecks published data without reporting source collection success',async()=>{
 const source=fs.readFileSync('market-observatory/data-refresh-v1.js','utf8');
 const code=source.slice(source.indexOf('let nowBusy='),source.indexOf('\nfunction init()'));
 const button={},message={dataset:{}};let reads=0;
 const root={__JJOONI_OBSERVATORY_QUOTES:{refresh:async()=>{throw Error('offline')}},
  __JJOONI_OBSERVATORY_MARKET_REFRESH:{status:'UPDATED',refresh:async()=>{reads++;return true}}};
 vm.runInNewContext(code+';root.force=forceNow;root.controls=(b,m)=>{nowButton=b;nowMessage=m}',{root,Error,Object,Promise});
 root.controls(button,message);await root.force();
 assert.equal(reads,1);assert.equal(button.disabled,false);
 assert.equal(message.dataset.state,'API_FAILED_PUBLISHED');
 assert.match(message.textContent,/신규 원천 조회 완료가 아니며/);
});

test('mobile resume reads current quotes once, suppresses hidden/burst reads and permits manual retry',async()=>{
 let clock=Date.now(),reads=0,fail=false;const listeners={};
 class Clock extends Date{static now(){return clock}}
 const document={hidden:true,dispatchEvent(){},addEventListener:(name,fn)=>listeners[name]=fn};
 const context=vm.createContext({document,CustomEvent:class{},AbortSignal,Date:Clock,Promise,Error,console,
  fetch:async()=>{reads++;if(fail)throw Error('offline');return {ok:true,json:async()=>payload({...row,observed_at:new Date(clock-1000).toISOString()})}}});
 context.window=context;context.addEventListener=(name,fn)=>listeners[name]=fn;
 vm.runInContext(fs.readFileSync('market-observatory/intraday-quotes-v1.js','utf8'),context);
 const runtime=context.__JJOONI_OBSERVATORY_QUOTES;
 assert.equal(reads,0,'a hidden tab must not collect');
 document.hidden=false;await listeners.visibilitychange();assert.equal(reads,1);
 await listeners.pageshow({persisted:true});await listeners.visibilitychange();assert.equal(reads,1);
 clock+=60000;await listeners.visibilitychange();assert.equal(reads,2);
 clock+=60000;document.hidden=true;await listeners.visibilitychange();assert.equal(reads,2);
 document.hidden=false;fail=true;await listeners.pageshow({persisted:true});assert.equal(runtime.status,'FAILED');
 await listeners.visibilitychange();assert.equal(reads,3,'failed automatic requests are also bounded');
 fail=false;await runtime.refresh(true);assert.equal(reads,4,'manual request bypasses the lifecycle gate');
 assert.equal(runtime.error,null);assert.equal(runtime.status,'COMPLETE');
});
