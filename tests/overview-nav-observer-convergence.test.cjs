const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const source=fs.readFileSync('live-bridge.js','utf8');
const begin=source.indexOf('function updateOverviewTotalNav(){');
const end=source.indexOf('\nfunction updateCards(){',begin);
assert.ok(begin>=0&&end>begin,'Overview NAV function exists');
const fn=source.slice(begin,end);

function renderTwice({labelInitial,navInitial,authority=100}){
 const mutations={label:0,value:0};
 let labelText=labelInitial, valueText=navInitial;
 const value={dataset:{},get textContent(){return valueText;},set textContent(v){mutations.value++;valueText=v;}};
 const box={classList:{contains:()=>false},querySelector:()=>value,parentElement:null};
 const label={children:[],dataset:{},parentElement:box,closest:()=>null,
   get textContent(){return labelText;},
   set textContent(v){mutations.label++;labelText=v;}};
 const root={querySelectorAll:()=>[label]};
 const document={getElementById: id=>id==='panel-overview'?root:null};
 const context={CANON:{accounts:{}},REGISTRY:[],window:{},document,
   authoritativeFiveAccountNav:()=>({nav:authority,source:'ACCOUNT_SUM_4',kind:'PRODUCER'}),
   won:x=>'₩'+x.toLocaleString('ko-KR'),n:x=>Number(x),
   getComputedStyle:()=>({fontSize:'18px'})};
 vm.runInNewContext(fn+'\nupdateOverviewTotalNav();updateOverviewTotalNav();',context,{timeout:1000});
 return {mutations,labelText,valueText,window:context.window};
}

test('overview NAV patch is idempotent when the title already shows four-account NAV',()=>{
 const result=renderTwice({labelInitial:'현재 총자산 (4계좌 NAV)',navInitial:'₩99'});
 assert.equal(result.valueText,'₩100');
 assert.equal(result.mutations.value,1,'no redundant NAV write on the second pass');
 assert.equal(result.mutations.label,0,'never rewrite identical label into the observed DOM');
 assert.equal(result.window.__JJOONI_OVERVIEW_5NAV_V45.nav,100);
});

test('legacy overview title is normalized only once and stays stable on rerender',()=>{
 const result=renderTwice({labelInitial:'현재 총자산',navInitial:'₩99'});
 assert.equal(result.valueText,'₩100');
 assert.equal(result.labelText,'현재 총자산 (4계좌 NAV)');
 assert.equal(result.mutations.label,1,'old title should be changed only once');
 assert.equal(result.mutations.value,1);
});

test('overview honors one validated producer authority rather than an unrelated local sum',()=>{
 assert.match(fn,/const truth=authoritativeFiveAccountNav\(\)/);
 const result=renderTwice({labelInitial:'현재 총자산 (4계좌 NAV)',navInitial:'₩99',authority:250});
 assert.equal(result.valueText,'₩250');
 assert.equal(result.window.__JJOONI_OVERVIEW_5NAV_V45.nav,250);
});
