const {test} = require('node:test');
const assert = require('node:assert/strict');
const {evaluate, POLICY} = require('../market-observatory/jjooni-tripod-v1.js');
const TRI='TQQQ 100%', CASH='현금 100%', BI='QQQ 50% + QLD 50%';
const row=(date,ndx,target=CASH)=>({date,ndx,target});
function model(rows, latestOverrides={}) {
  const last=rows.at(-1);
  return evaluate({us_completed_session_date:last.date,tripod_history:rows,
    tripod_latest:{...last,session_date:last.date,ok:true,ma250:100,
      vix10:last.target===CASH?20:15,vix_window_count:10,
      regime:last.target===CASH?'하락':'상승',...latestOverrides}});
}
test('policy is a strictly read-only 5x5 QLD overlay, not the canonical engine',()=>{
  assert.equal(POLICY.tranchePct,5);assert.equal(POLICY.capPct,25);
  assert.equal(POLICY.triggerDailyPct,-1.5);
  assert.equal(POLICY.stopFromNoPodEntryPct,-12);
  assert.equal(POLICY.instrument,'QLD');
});
test('official strategy remains unchanged outside NO-POD',()=>{
  const r=model([row('2026-10-01',100,TRI),row('2026-10-02',102,BI)]);
  assert.equal(r.status,'BASE_STRATEGY');assert.equal(r.officialTarget,BI);
  assert.equal(r.active,false);
});
test('entry day -1.5% trigger schedules 5%, next completed close executes once',()=>{
  const a=[row('2026-10-01',100,TRI),row('2026-10-02',98,CASH)];
  const signal=model(a);
  assert.equal(signal.status,'ACTIVE');
  assert.equal(signal.cycle.entryNdx,98);
  assert.equal(signal.cycle.stopNdx,98*.88);
  assert.equal(signal.cycle.boughtPct,0);
  assert.equal(signal.cycle.pending.pct,5);
  const bought=model([...a,row('2026-10-05',97,CASH)]);
  assert.equal(bought.cycle.boughtPct,5);
  assert.equal(bought.cycle.buyCount,1);
  assert.equal(bought.cycle.pending,null);
});
test('five capped tranches, no duplicate trigger while same day pending',()=>{
  const a=[row('2026-09-30',100,TRI),row('2026-10-01',98,CASH)];
  let price=98,day=2;
  // Rebound then dip keeps index above cycle stop while generating independent signals.
  for (let i=0;i<10;i++) {
    price*=i%2===0?1.012:0.98;
    a.push(row('2026-10-'+String(day++).padStart(2,'0'),price,CASH));
  }
  const r=model(a);
  assert.equal(r.cycle.boughtPct,25);
  assert.equal(r.cycle.buyCount,5);
  assert.equal(r.cycle.pending,null);
  assert.equal(r.cycle.stopped,false);
});
test('stop takes priority over pending buy and forbids reentry until NO-POD ends',()=>{
  const a=[row('2026-10-01',100,TRI),row('2026-10-02',98,CASH)];
  const stop=model([...a,row('2026-10-05',85,CASH)]);
  assert.equal(stop.status,'STOPPED');
  assert.equal(stop.cycle.buyCount,0);
  assert.equal(stop.cycle.boughtPct,0);
  assert.equal(stop.cycle.pending,null);
  assert.equal(stop.cycle.stopDate,'2026-10-05');
  const later=model([...a,row('2026-10-05',85,CASH),row('2026-10-06',81,CASH)]);
  assert.equal(later.status,'STOPPED');assert.equal(later.cycle.pending,null);
});
test('exit resets overlay; next NO-POD has its own frozen entry anchor',()=>{
  const r=model([row('2026-10-01',100,TRI),row('2026-10-02',98,CASH),
    row('2026-10-05',85,CASH),row('2026-10-06',92,BI),
    row('2026-10-07',90,CASH)]);
  assert.equal(r.status,'ACTIVE');
  assert.equal(r.cycle.entryNdx,90);
  assert.equal(r.cycle.stopNdx,90*.88);
  assert.equal(r.cycle.boughtPct,0);
  assert.equal(r.lastCycle.stopDate,'2026-10-05');
});
test('missing NO-POD entry history and uncertified snapshots show no actionable signal',()=>{
  const a=model([row('2026-10-01',99,CASH),row('2026-10-02',96,CASH)]);
  assert.equal(a.status,'UNVERIFIED_ANCHOR');
  assert.equal(a.cycle.entryNdx,null);
  assert.equal(a.cycle.pending,null);
  const b=model([row('2026-10-01',100,TRI),row('2026-10-02',98,CASH)],{ok:false});
  assert.equal(b.status,'UNCERTIFIED');
  const c=model([row('2026-10-01',100,TRI),row('2026-10-02',98,CASH)],{vix_window_count:9});
  assert.equal(c.status,'UNCERTIFIED');
});
