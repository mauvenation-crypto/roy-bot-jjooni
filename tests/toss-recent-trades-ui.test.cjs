'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const script=fs.readFileSync(path.join(__dirname,'..','trade-review-outcomes-v26.js'),'utf8')
 .replace('function reconstructRealized(trades){','window.__testCollectTrades=collectTrades;\nfunction reconstructRealized(trades){');
assert.match(script,/__testCollectTrades=collectTrades/);
function run(humanTrades,recentTrades){
 const window={__JJOONI_LIVE_PAYLOAD:recentTrades===undefined?{}:{recent_trades:recentTrades},addEventListener(){}};
 const ctx={window,document:{addEventListener(){}},setTimeout(){},D:{human:{trades:humanTrades}}};
 vm.runInNewContext(script,ctx,{filename:'trade-review-outcomes-v26.js'});
 return {rows:Array.from(window.__testCollectTrades(),t=>({...t})),bridge:window.__JJOONI_TRADE_OUTCOMES_V26.broker_trade_bridge};
}
const base={account:'TOSS',ticker:'005930.KS',name:'삼성전자',side:'BUY',qty:4,price:180500,filled_at_kst:'2026-11-06T09:58:00+09:00',order_id:'toss-buy-4',source:'BROKER_DIRECT_TOSS_API_FAST'};
test('a confirmed Toss buy absent from the master ledger appears once in review',()=>{
 const x=run([], [base]);
 assert.equal(x.rows.length,1);
 assert.equal(x.rows[0].qty,4);
 assert.equal(x.rows[0].account,'TOSS');
 assert.equal(x.bridge.accepted,1);
});
test('an already recorded trade never duplicates when returned by the broker again',()=>{
 const prior={...base,trade_key:'TOSS|toss-buy-4',order_id:undefined,source:'MASTER_TRADE_LEDGER'};
 const x=run([prior],[base,{...base}]);
 assert.equal(x.rows.length,1);
 assert.equal(x.bridge.accepted,0);
});
test('unverified, account-mismatched, identity-free and unfilled rows are rejected',()=>{
 const x=run([],[
  {...base,source:'MODEL'},
  {...base,account:'ISA'},
  {...base,order_id:''},
  {...base,qty:0},
  {...base,price:null},
  {...base,side:'PENDING'},
  {...base,filled_at_kst:''}
 ]);
 assert.equal(x.rows.length,0);
 assert.equal(x.bridge.rejected,7);
});
test('Toss broker recent trade is not manufactured when API recent trade evidence is missing',()=>{
 const x=run([],undefined);
 assert.equal(x.rows.length,0);
 assert.equal(x.bridge.state,'SOURCE_UNAVAILABLE');
});
