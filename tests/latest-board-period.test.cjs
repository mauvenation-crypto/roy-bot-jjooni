const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function board(series, quality={}, quotes={}, crypto_market={}) {
  const src = fs.readFileSync(path.join(__dirname, '../market-observatory/latest-board-v1.js'), 'utf8');
  const context = {
    DATA: {series,cross_market_freshness_quality:quality,crypto_market}, window: {__JJOONI_OBSERVATORY_QUOTES:{get:key=>quotes[key]||null}}, document: {createElement: () => ({}), head: {appendChild() {}}},
    setInterval() {}, clearInterval() {}, console,
  };
  vm.createContext(context);
  vm.runInContext(src.replace('let tries=0;', 'window.testPeriod={stat,standardTile,BY_KEY,setCompare:key=>compareKey=key};let tries=0;'), context);
  return context.window.testPeriod;
}

test('Russell daily gain and weekly loss retain separate signs and bases', () => {
  const api = board({RUSSELL2000: [
    {date: '2026-10-02', value: 2832.89990234},
    {date: '2026-10-08', value: 2794.12988281},
    {date: '2026-10-09', value: 2806.97998047},
  ]});
  const item = api.BY_KEY.RUSSELL2000;
  assert.equal(api.stat(item, 'D1').change.toFixed(2), '0.46');
  assert.equal(api.stat(item, 'W1').change.toFixed(2), '-0.91');
  assert.equal(api.stat(item, 'W1').refDate, '2026-10-02');
  const html = api.standardTile(item);
  assert.match(html, /일간 \+0\.46%/);
  assert.match(html, /주간 -0\.91%/);
  assert.match(html, /2026-10-08 → 2026-10-09/);
});

test('holiday comparison uses latest close on or before weekly target', () => {
  const api = board({SP500: [
    {date: '2026-10-01', value: 100},
    {date: '2026-10-06', value: 104},
    {date: '2026-10-08', value: 105},
  ]});
  assert.equal(api.stat(api.BY_KEY.SP500, 'W1').refDate, '2026-10-01');
  assert.equal(api.stat(api.BY_KEY.SP500, 'W1').change.toFixed(2), '5.00');
});

test('missing weekly reference remains unavailable instead of using daily gain', () => {
  const api = board({RUSSELL2000: [
    {date: '2026-10-08', value: 100}, {date: '2026-10-09', value: 101},
  ]});
  assert.equal(api.stat(api.BY_KEY.RUSSELL2000, 'W1').change, null);
  assert.match(api.standardTile(api.BY_KEY.RUSSELL2000), /주간 —/);
});

test('rate, spread, FX, commodity and sentiment cards show daily and weekly units together', () => {
  const dates=['2026-10-13','2026-10-19','2026-10-20'];
  const rows=values=>values.map((value,i)=>({date:dates[i],value}));
  const api=board({US10Y:rows([4.90,5.10,5.117]),US_2S10S:rows([.2,.3,.33]),
    USDKRW:rows([1300,1320,1327]),WTI:rows([100,102,101]),FEAR_GREED:rows([40,45,47])});
  for(const [key,daily,weekly] of [
    ['US10Y_OFFICIAL','일간 +1.7bp','주간 +21.7bp'],
    ['US_2S10S','일간 +3.0bp','주간 +13.0bp'],
    ['USDKRW','일간 +0.53%','주간 +2.08%'],
    ['WTI','일간 -0.98%','주간 +1.00%'],
    ['FEAR_GREED','일간 +2.0pt','주간 +7.0pt']]){
      const html=api.standardTile(api.BY_KEY[key]);
      assert(html.includes(daily),html);assert(html.includes(weekly),html);
      assert(html.includes('2026-10-13 → 2026-10-20'),html);
  }
});

test('missing observations are excluded rather than converted into zero changes',()=>{
  const api=board({KR10Y:[{date:'2026-10-13',value:null},{date:'2026-10-19',value:4},{date:'2026-10-20',value:null}]});
  const html=api.standardTile(api.BY_KEY.KR10Y);
  assert.match(html,/일간 —/);assert.match(html,/주간 —/);
  assert.doesNotMatch(html,/-400\.0bp/);
});

test('daily and weekly each appear once while longer selected comparisons remain available',()=>{
 const api=board({WTI:[{date:'2026-09-01',value:80},{date:'2026-10-13',value:100},{date:'2026-10-19',value:102},{date:'2026-10-20',value:101}]});
 for(const comparison of ['D1','W1','M1','Y1']){
  api.setCompare(comparison);
  const html=api.standardTile(api.BY_KEY.WTI),text=html.replace(/<div class="latestPrimaryChange[^"]*">.*?<\/div>/g,'').replace(/<[^>]*>/g,'');
  assert.equal((text.match(/일간/g)||[]).length,1,text);
  assert.equal((text.match(/주간/g)||[]).length,1,text);
  assert(text.includes('일간 -0.98%'));assert(text.includes('주간 +1.00%'));
  if(comparison==='M1')assert(text.includes('전월 ▲ 26.25%'));
  if(comparison==='Y1')assert.match(text,/전년 대비 —/);
 }
});

test('Japanese rate cards explicitly mark old official observations as delayed',()=>{
 const api=board({
   JP2Y:[{date:'2026-10-22',value:1.914},{date:'2026-10-23',value:1.872}],
   JP10Y:[{date:'2026-10-22',value:2.914},{date:'2026-10-23',value:2.837}],
   US2Y:[{date:'2026-10-23',value:4.69},{date:'2026-10-26',value:4.68}]
 },{JP_RATES:{status:'LAGGING',last_date:'2026-10-23',expected_latest_weekday:'2026-10-26'}});
 for(const key of ['JP2Y','JP10Y']){
  const html=api.standardTile(api.BY_KEY[key]);
  assert.match(html,/자료 지연 · 2026-10-26 자료 미확인/);
  assert.match(html,/실제 관측 2026-10-23/);
  assert.match(html,/직전 관측일 -[0-9]+\.[0-9]bp/);
  assert.match(html,/오늘 등락이 아닙니다/);
  assert.doesNotMatch(html,/일간 -[0-9]+\.[0-9]bp/);
 }
 const us=api.standardTile(api.BY_KEY.US2Y);
 assert.doesNotMatch(us,/자료 지연/);
 assert.match(us,/일간 -1.0bp/);
});

test('Japan official rate current to expected session has no false stale badge',()=>{
 const api=board({JP10Y:[{date:'2026-10-23',value:2.83},{date:'2026-10-26',value:2.82}]},
  {JP_RATES:{status:'LIVE',expected_latest_weekday:'2026-10-26'}});
 const html=api.standardTile(api.BY_KEY.JP10Y);
 assert.doesNotMatch(html,/자료 지연/);
 assert.match(html,/일간 -1.0bp/);
});

test('Japanese source fetch failure is disclosed without deleting last good price',()=>{
 const api=board({JP2Y:[{date:'2026-10-23',value:1.872}]},
  {JP_RATES:{status:'STALE',expected_latest_weekday:'2026-10-26',fetch_error:'timeout'}});
 const html=api.standardTile(api.BY_KEY.JP2Y);
 assert.match(html,/1.872%/);
 assert.match(html,/원천 조회 실패/);
 assert.match(html,/실제 관측 2026-10-23/);
});

test('US rate labels distinguish local observation day and disclose failed refresh',()=>{
 const api=board({US10Y:[{date:'2026-10-23',value:4.98}]},
 {US10Y:{status:'STALE',target_session:'2026-10-26',fetch_error:'timeout'}});
 const html=api.standardTile(api.BY_KEY.US10Y_OFFICIAL);
 assert.match(html,/미국 현지 2026-10-23 기준 · 일별 확정값/);
 assert.match(html,/자료 지연 · 2026-10-26 자료 미확인/);
 assert.match(html,/원천 조회 실패/);
});


test('market cards place the selected-period change ahead of the level with native units',()=>{
 const api=board({NASDAQ100:[{date:'2026-10-08',value:100},{date:'2026-10-09',value:98}],US2Y:[{date:'2026-10-08',value:4},{date:'2026-10-09',value:4.05}]});
 for(const [key,value] of [['NASDAQ100','-2.00%'],['US2Y','+5.0bp']]){
  const html=api.standardTile(api.BY_KEY[key]);
  assert(html.includes('latestPrimaryValue">'+value));
  assert(html.indexOf('latestPrimaryValue')<html.indexOf('latestLevelValue'));
  assert.match(html,/일간 대비/);
 }
});

test('intraday overlay updates daily card only and leaves closed history and weekly returns intact',()=>{
 const series={NASDAQ100:[{date:'2026-10-22',value:90},{date:'2026-10-29',value:99},{date:'2026-10-30',value:100}]},before=JSON.stringify(series);
 const q={value:103,previous_close:100,change_pct:3,session_date:'2026-10-30',observed_at:'2026-10-30T16:00:00Z',display_status:'장중 관측 · 지연 가능'};
 const api=board(series,{}, {NASDAQ100:q}),item=api.BY_KEY.NASDAQ100;
 assert.equal(api.stat(item).value,103);assert.equal(api.stat(item).change,3);
 assert.match(api.standardTile(item),/전일 종가 대비/);assert.match(api.standardTile(item),/10-31 01:00:00 KST/);
 api.setCompare('W1');assert.equal(api.stat(item).value,100);assert.match(api.standardTile(item),/주간 대비/);
 assert.doesNotMatch(api.standardTile(item),/장중 관측/);assert.equal(JSON.stringify(series),before);
});


test('crypto cards recompute LIVE status from the actual quote timestamp',()=>{
 const kst=minutes=>new Date(Date.now()-minutes*60000+9*3600000).toISOString().replace('Z','+09:00');
 const series={BTCUSD:[{date:'2026-10-30',value:100},{date:'2026-10-31',value:101}],ETHUSD:[{date:'2026-10-30',value:200},{date:'2026-10-31',value:202}]};
 const recent=board(series,{}, {}, {BTCUSD:{status:'LIVE',quote_as_of_kst:kst(5)}});
 assert.match(recent.standardTile(recent.BY_KEY.BTCUSD),/수집 시점 시세/);
 const old=board(series,{}, {}, {BTCUSD:{status:'LIVE',quote_as_of_kst:kst(90)},ETHUSD:{status:'LIVE',quote_as_of_kst:kst(120)}});
 for(const key of ['BTCUSD','ETHUSD']){
  const html=old.standardTile(old.BY_KEY[key]);
  assert.match(html,/이전 시세 · 갱신 지연/);
  assert.doesNotMatch(html,/수집 시점 시세/);
 }
 const noStamp=board(series,{}, {}, {BTCUSD:{status:'LIVE'}});
 assert.match(noStamp.standardTile(noStamp.BY_KEY.BTCUSD),/이전 시세 · 갱신 지연/);
});
