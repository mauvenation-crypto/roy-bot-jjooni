const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('coordinator publishes no fake ACTIVE and starts one stable loader only after verified facts',()=>{
 const scripts=[],listeners={},nodes=new Map(),text={textContent:'',style:{}};
 const shield={querySelector:()=>text,remove(){nodes.delete('ctUiBootShieldV14')}};nodes.set('ctUiBootShieldV14',shield);
 const document={scripts,head:{appendChild(s){scripts.push(s)}},getElementById:id=>nodes.get(id),createElement:()=>({}),addEventListener:(n,fn)=>listeners[n]=fn};
 const window={__JJOONI_UI_RELEASE:'release-A'};let pulse;
 vm.runInNewContext(fs.readFileSync('boot-coordinator-v33.js','utf8'),{window,document,Date,console,setInterval:fn=>(pulse=fn,1),clearInterval(){},setTimeout(){},encodeURIComponent,location:{reload(){}}});
 assert.equal(window.__JJOONI_UI_BOOT_V14,undefined);assert.equal(scripts.length,0);
 window.__JJOONI_CANONICAL_SSOT={};window.__JJOONI_LIVE_PAYLOAD={};pulse();assert.equal(scripts.length,0);
 window.__JJOONI_LINEAGE_GUARD={version:'verified',policy:'verified'};pulse();listeners['jjooni:live-applied']();pulse();
 assert.equal(scripts.length,1);assert.equal(scripts[0].src,'trade-review-loader.js?v=14.37-broker-evidence&_=release-A');
 assert.equal(window.__JJOONI_LIVE_READY,true);
});
test('startup name subset comes from private sources; full master is never fetched until requested',async()=>{
 const scripts=[],listeners={},events=[];const window={__JJOONI_UI_RELEASE:'release-A',__JJOONI_CANONICAL_SSOT:{accounts:{TOSS:{positions:[{ticker:'AAPL',name:'애플'},{ticker:'005930',name:'삼성전자'}]}}},dispatchEvent:e=>events.push(e)};
 const document={head:{appendChild:s=>scripts.push(s)},createElement:()=>({remove(){}}),addEventListener:(n,fn)=>listeners[n]=fn};
 vm.runInNewContext(fs.readFileSync('security-names-held-v1.js','utf8'),{window,document,CustomEvent:class{constructor(name,detail){this.name=name;this.detail=detail}},console});
 assert.equal(window.__JJOONI_SECURITY_NAMES.AAPL,'애플');assert.equal(window.__JJOONI_SECURITY_NAMES['005930'],'삼성전자');assert.equal(scripts.length,0);
 window.__JJOONI_CANONICAL_SSOT.accounts.TOSS.positions.push({ticker:'UNKNOWN'});
 listeners.click({target:{closest:()=>({dataset:{tab:'overview'}})}});assert.equal(scripts.length,0);
 listeners.click({target:{closest:()=>({dataset:{tab:'trades'}})}});assert.equal(scripts.length,1);
 scripts[0].onerror();await new Promise(resolve=>setImmediate(resolve));
 const retry=window.__JJOONI_LOAD_SECURITY_MASTER();assert.equal(scripts.length,2);scripts[1].onload();await retry;
});
