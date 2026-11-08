const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const {name,width,height} of [{name:'mobile360',width:360,height:800},
    {name:'mobile390',width:390,height:844},
    {name:'mobile430',width:430,height:932},
    {name:'tablet800',width:800,height:1280}]){
   const page=await browser.newPage({viewport:{width,height}});
   await page.goto('http://127.0.0.1:8123/market-observatory/',{waitUntil:'domcontentloaded',timeout:90000});
   await page.locator('button[data-tab="morning-brief"]').click();
   await page.waitForFunction(()=>{
    const cards=[...document.querySelectorAll('#briefKeyFigures .briefFigure b')].map(x=>x.textContent);
    return cards.length===2 && cards[0].includes('26,989.99') && cards[1].includes('9,390.25');
   },{timeout:45000});
   const result=await page.evaluate(()=>{
    const rect=e=>{const b=e.getBoundingClientRect();return {left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width}};
    const tools=document.querySelector('.briefTools');
    return {width:innerWidth,scroll:document.documentElement.scrollWidth,
     title:document.querySelector('#briefTitle')?.textContent,
     badge:document.querySelector('#briefBadge')?.textContent,
     notice:document.querySelector('#briefNotice')?.textContent,
     figures:[...document.querySelectorAll('#briefKeyFigures .briefFigure')].map(x=>x.innerText),
     detailsOpen:document.querySelector('#briefSourceDetails')?.open,
     tools:rect(tools),label:rect(tools.querySelector('label')),select:rect(tools.querySelector('select')),
     refresh:rect(tools.querySelector('button')),head:rect(document.querySelector('.briefHead'))};
   });
   assert.equal(result.scroll<=result.width+3,true, name+' horizontal page overflow '+JSON.stringify(result));
   assert.match(result.badge,/마지막 게시본 · 2026-11-07/);
   assert.match(result.notice,/공식 종가 정정/);
   assert.doesNotMatch(result.notice,/CROSS_CHECKED/);
   assert.match(result.notice,/본문.*재산출되지 않았습니다/);
   assert.match(result.figures[0],/26,989\.99/);
   assert.match(result.figures[0],/1\.35%/);
   assert.match(result.figures[1],/9,390\.25/);
   assert.match(result.figures[1],/4\.21%/);
   assert.equal(result.detailsOpen,false);
   for(const k of ['tools','label','select','refresh','head']){
    assert(result[k].left>=-2&&result[k].right<=width+2,name+' '+k+' overflows');
   }
   if(width<=430){
    assert(result.select.bottom<=result.refresh.top+2,name+' mobile refresh overlaps date select');
   }
   await page.locator('#briefSourceDetails summary').click();
   assert.match(await page.locator('#briefSourceDetails p').textContent(),/26,989\.99/);
   await page.screenshot({path:'/tmp/brief-'+name+'.png'});
   console.log('BRIEF_MOBILE_RENDER=PASS '+name+' verified=NDX_26989.99,SOX_9390.25 last=2026-11-07');
   await page.close();
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
