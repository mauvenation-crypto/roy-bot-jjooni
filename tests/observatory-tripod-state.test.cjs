const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('market-observatory/latest-board-v1.js','utf8');
const ctx={};vm.createContext(ctx);
vm.runInContext(src.slice(src.indexOf('function tripodNextModel('),src.indexOf('function tripodNextHtml('))+';this.display=tripodDisplayModel;',ctx);
const date='2026-10-16',base={ok:true,session_date:date,date,ndx:110,ma250:100,vix10:20,vix_window_count:10,drawdown_52w_pct:-12,regime:'상승',target:'QQQ 50% + QLD 50%',vix_latest_close:21};
const display=(changes={},session=date)=>ctx.display({...base,...changes},session,[]);
test('rising BIPOD advertises return to TRI-POD, with drawdown recovery and VIX conditions together',()=>{
 const d=display();assert(d.available);assert.equal(d.pod,'BIPOD');assert.equal(d.primary.label,'트라이팟 복귀가격');
 assert.equal(d.primary.op,'≥');assert.equal(d.primary.boundary,113.75);assert.equal(d.primary.metric,'TRIPOD_BIPOD');assert.match(d.primary.note,/그리고 VIX10 < 28/);
 assert.equal(d.secondary.label,'노팟 전환가격');assert.equal(d.secondary.boundary,95);assert.match(d.secondary.note,/VIX10 ≥ 18/);
});
test('TRI-POD advertises BIPOD deceleration, retaining the OR trigger',()=>{
 const d=display({drawdown_52w_pct:-5,target:'TQQQ 100%'});assert.equal(d.pod,'TRIPOD');assert.equal(d.primary.label,'바이팟 전환가격');assert.equal(d.primary.op,'<');assert.match(d.primary.note,/또는 VIX10 ≥ 28/);
});
test('a recovered price with VIX10 equal to 28 cannot imply TRI-POD restoration',()=>{
 const d=display({drawdown_52w_pct:-5,vix10:28});assert(d.available);assert.equal(d.pod,'BIPOD');assert.equal(d.primary.met,true);assert.match(d.primary.note,/모두 충족/);
 const restored=display({drawdown_52w_pct:-9,vix10:27.99,target:'TQQQ 100%'});assert.equal(restored.pod,'TRIPOD');
});
test('falling BIPOD shows the rising regime boundary and VIX-only cash exit',()=>{
 const d=display({regime:'하락',ndx:90,vix10:17.99});assert.equal(d.pod,'BIPOD');
 assert.equal(d.primary.metric,'TRIPOD_RISE');assert.equal(d.primary.boundary,101);assert.equal(d.primary.op,'>');
 assert.equal(d.secondary.kind,'vix');assert.equal(d.secondary.boundary,18);assert.equal(d.secondary.op,'≥');
});
test('NOPOD shows reentry below VIX10 18 and does not repeat its own cash price line',()=>{
 const d=display({regime:'하락',ndx:90,vix10:18,target:'현금 100%'});assert.equal(d.pod,'NOPOD');assert.equal(d.primary.label,'바이팟 재진입 VIX10');assert.equal(d.primary.op,'<');assert.equal(d.primary.met,false);assert.equal(d.secondary.metric,'TRIPOD_RISE');
 assert.equal(display({regime:'하락',ndx:90,vix10:17.99}).pod,'BIPOD');
});
test('four visible operating forms do not invent an unconfigured MONOPOD market trigger',()=>{
 const d=display();assert.deepEqual(Array.from(d.cases,c=>c.key),['TRIPOD','BIPOD','MONOPOD','NOPOD']);
 assert.equal(display({target:'QQQ 100%'}).available,false);
});
test('unverified and mixed-session snapshots publish no actionable transition descriptor',()=>{
 for(const change of [{ok:false},{vix10:null},{ndx:null},{vix_window_count:9}]){
  const d=display(change);assert.equal(d.available,false);assert.equal(d.primary,undefined);
 }
 const d=display({},'2026-10-17');assert.equal(d.available,false);assert.equal(d.primary,undefined);
});
function board(data){
 const context={DATA:data,window:{__JJOONI_OBSERVATORY_QUOTES:{get:()=>({value:999999,previous_close:1,change_pct:99999,session_date:'2026-10-17',display_status:'장중'})}},
 document:{createElement:()=>({}),head:{appendChild(){}}},setInterval(){},clearInterval(){},console};
 vm.createContext(context);vm.runInContext(src.replace('let tries=0;','window.testTiles=tripodTiles;let tries=0;'),context);return context;
}
test('signal tiles ignore a newer intraday index and VIX and share the certified close date',()=>{
 const data={tripod_latest:base,us_completed_session_date:date,tripod_history:[{date:'2026-10-15',ndx:109,vix:20}],series:{NASDAQ100:[{date:'2026-10-17',value:999999}],VIX:[{date:'2026-10-17',value:999999}]}};
 const b=board(data),tiles=b.window.testTiles();assert.equal(tiles.length,9);
 assert.match(tiles[0],/바이팟 · 1.5배/);assert.match(tiles[2],/>110\.00</);assert.match(tiles[6],/21\.00 \/ 20\.00/);
 for(const tile of tiles.slice(0,8)){assert.match(tile,/<time>2026-10-16<\/time>/);assert.doesNotMatch(tile,/999,999|2026-10-17/);}
 assert.match(tiles[3],/트라이팟 복귀가격/);assert.match(tiles[8],/data-pod-case="MONOPOD"/);assert.match(tiles[8],/별도 시장신호 전환조건은 설정되지 않았습니다/);
});
test('all operating cases render their own next transition labels',()=>{
 for(const change of [{drawdown_52w_pct:-5,target:'TQQQ 100%'},{},{regime:'하락',ndx:90,vix10:17.99},{regime:'하락',ndx:90,vix10:18,target:'현금 100%'}]){
  const data={tripod_latest:{...base,...change},us_completed_session_date:date,tripod_history:[],series:{}},b=board(data),d=b.window.__JJOONI_LATEST_BOARD.getTripodDisplay(),tiles=b.window.testTiles();
  assert.match(tiles[3],new RegExp(d.primary.label));assert.match(tiles[4],new RegExp(d.secondary.label));
 }
});
test('the return-price drilldown keeps the 52-week threshold and describes restoration',()=>{
 const modal=fs.readFileSync('market-observatory/metric-detail-v1.js','utf8'),context={DATA:{tripod_latest:base,tripod_history:[]},window:{__JJOONI_LATEST_BOARD:{getTripodDisplay:()=>({available:true,pod:'BIPOD',stateLabel:'바이팟'})}}};
 vm.createContext(context);vm.runInContext(modal.slice(modal.indexOf('const finite='),modal.indexOf('let dialog,'))+';this.metric=model;',context);
 const m=context.metric('TRIPOD_BIPOD');assert.match(m.title,/트라이팟 복귀가격/);assert.match(m.note,/VIX10 < 28/);assert.equal(m.lines[0].rows[0].value,113.75);
});
