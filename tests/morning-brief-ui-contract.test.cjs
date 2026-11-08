const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync('market-observatory/morning-brief-v1.js','utf8');
const html=fs.readFileSync('market-observatory/index.html','utf8');
const start=src.indexOf('function viewState('),end=src.indexOf('\nfunction render(d){',start);
assert.ok(start>=0&&end>start,'real reader exposes pure publication-state helper');
const fn=src.slice(start,end);
const verified={
 report_date_kst:'2026-11-07',market_date_us:'2026-11-06',
 content_status:'WEB_VERIFIED_WITH_DISCLOSED_GAPS',
 revisions:[{revised_at_kst:'2026-11-09T06:45:00+09:00'}],
 editorial_contract:{interpretation_status:'HISTORIC_NARRATIVE_NOT_RECALCULATED_AFTER_EOD_CORRECTION',
  close_checks:[{symbol:'NDX',status:'VERIFIED',close:26989.99,change_pct:1.35},
  {symbol:'SOX',status:'VERIFIED',close:9390.25,change_pct:4.21}]}
};
function view(d,selected='latest',now='2026-11-09'){
 return vm.runInNewContext(fn+'\nviewState(d,selected,now)',{d,selected,now});
}
test('Monday shows Saturday final public brief without calling it a current Monday market report',()=>{
 const x=view(verified);
 assert.equal(x.badge,'마지막 게시본 · 2026-11-07');
 assert.match(x.notice,/월요일.*별도 투자보드/);
 assert.match(x.notice,/26,989\.99/);assert.match(x.notice,/9,390\.25/);
 assert.match(x.notice,/재산출되지 않았습니다/);
 assert.doesNotMatch(x.notice,/CROSS_CHECKED/);
});
test('verified correction is not downgraded to missing source, or presented as original TRI-POD signal',()=>{
 const x=view(verified,'latest','2026-11-10');
 assert.deepEqual(Array.from(x.conflicts),[]);
 assert.match(x.notice,/11-09 공식 종가 정정/);
 assert.match(x.notice,/매매 판단에 사용하지 마세요/);
});
test('unverified conflict remains clearly labeled and cannot display a close',()=>{
 const d=JSON.parse(JSON.stringify(verified));
 d.editorial_contract.interpretation_status='HISTORIC_NARRATIVE_NOT_RECALCULATED';
 d.editorial_contract.close_checks[0]={symbol:'NDX',status:'CONFLICT',close:null,change_pct:null};
 const x=view(d,'latest','2026-11-09');
 assert.deepEqual(Array.from(x.conflicts),['NDX']);
 assert.match(x.notice,/확정 종가 불일치\/미검증/);
});
test('selected historical report is never mislabeled as most recently published',()=>{
 assert.equal(view(verified,'2026-11-07','2026-11-09').badge,'보관 기록 · 2026-11-07');
});
test('mobile reader has correction detail, consistent latest-publication wording and cache bust',()=>{
 assert.match(src,/검증 근거·정정 이력 펼쳐보기/);
 assert.match(src,/briefSourceDetails/);
 assert.match(src,/briefTools\{display:grid/);
 assert.match(src,/공식 EOD 확인/);
 assert.match(html,/morning-brief-v1\.js\?v=20261109-mobile-correction-v2/);
 assert.match(html,/<option value="latest">최신 공개본<\/option>/);
});
