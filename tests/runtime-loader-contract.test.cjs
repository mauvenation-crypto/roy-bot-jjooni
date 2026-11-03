const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');

test('shell explicitly loads pure metrics then application bootstrap, without an eager UI loader',()=>{
 const index=read('index.html');
 assert.ok(index.indexOf('canonical-metrics.js?v=34.1-quality')<index.indexOf('ui-bootstrap-v1.js?v=3-toss-exit'));
 assert.doesNotMatch(index,/<script src="trade-review-loader/);
 assert.match(index,/legacyDocument.querySelectorAll/);
});
test('canonical calculation does not inject UI or mutate boot state',()=>{
 const canonical=read('canonical-metrics.js'),bootstrap=read('ui-bootstrap-v1.js');
 assert.doesNotMatch(canonical,/createElement|appendChild|BOOTSTRAPPED|__JJOONI_UI_BOOT/);
 assert.match(bootstrap,/boot-coordinator-v33\.js/);assert.match(bootstrap,/fast-refresh-v32\.js/);
});
test('verified coordinator owns a single real loader without fabricated ACTIVE',()=>{
 const boot=read('boot-coordinator-v33.js');
 assert.match(boot,/function verifiedReady\(\)\{return factsReady\(\)&&lineageReady\(\)\}/);
 assert.match(boot,/trade-review-loader\.js\?v=14\.37-toss-exit/);
 assert.doesNotMatch(boot,/V33_DEFERRED_BOOT_HOLD|state:'ACTIVE',version/);
 assert.match(boot,/window\.__JJOONI_LIVE_READY=true/);
});

test('UI loader still requires detail-authority runtimes before showing the dashboard',()=>{
  const loader=read('trade-review-loader.js');
  assert.match(loader,/__JJOONI_SOURCE_AUTHORITY_V24\?\.state==='ACTIVE'/);
  assert.match(loader,/__JJOONI_POSITION_COMPLETENESS_V25\?\.state==='ACTIVE'/);
  assert.match(loader,/startsWith\('25\.1'\)/);
  assert.match(loader,/__JJOONI_TRADE_OUTCOMES_V26\?\.state==='ACTIVE'/);
  assert.match(loader,/__JJOONI_CT_FAST\?\.version==='1\.7'/);
  assert.match(loader,/REQUIRED_DETAIL_RUNTIME_MISSING/);
});

test('UI module optimization preloads downloads but preserves sequential execution',()=>{
  const loader=read('trade-review-loader.js');
  assert.match(loader,/function bootUrl\(src\)/);
  assert.match(loader,/function preloadModules\(modules\)/);
  assert.match(loader,/l\.rel='preload';l\.as='script';l\.href=bootUrl\(src\)/);
  const preload=loader.indexOf('preloadModules(modules.filter');
  const sequential=loader.indexOf("for(const [id,src,label] of modules.filter(x=>!DEFERRED_LABELS.has(x[2]))){bootText('필수 모듈 확인 · '+label);await loadRequired(id,src,label)}");
  assert.ok(preload>=0,'module preloading must be enabled');
  assert.ok(sequential>preload,'required modules must still execute sequentially after preload starts');
  assert.match(loader,/s\.src=bootUrl\(src\)/);
});


test('verified UI loader cache-busts the NAV race-fixed mobile runtime',()=>{
  const loader=read('trade-review-loader.js');
  assert.match(loader,/mobile-stability-v4\.js\?v=4\.6-holdings/);
  assert.match(loader,/version:'14\.36'/);
});

test('retired AUTOBOT module is absent from verified loader',()=>{const loader=read('trade-review-loader.js');assert.doesNotMatch(loader,/AI BOT|autobot-audit-board-v1|ctAutobotAuditBoardV1Script/);});

test('optional loader failure cannot change ACTIVE boot state or stop later optional modules',async()=>{
 const vm=require('node:vm'),window={},context={window,document:{head:{}},console:{warn(){}},Date};
 const source=read('trade-review-loader.js');
 const prefix=source.slice(0,source.indexOf('const LABELS='));
 vm.runInNewContext(prefix+"BOOT.state='ACTIVE';let attempts=[];async function loadRequired(id,src,label){attempts.push(label);if(label==='decision-impact')throw Error('offline')}window.run=()=>loadDeferred([['a','a','decision-impact'],['b','b','manual-intraday']]);window.attempts=attempts;})();",context);
 await window.run();assert.equal(window.__JJOONI_UI_BOOT_V14.state,'ACTIVE');assert.equal(window.__JJOONI_UI_BOOT_V14.optional_failures.length,1);assert.equal(window.attempts.join(','),'decision-impact,manual-intraday');
});
