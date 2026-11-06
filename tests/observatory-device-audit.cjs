// Runs the repository's public Observatory in Chromium, without account APIs.
const {chromium}=require('playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const base=process.env.OBS_AUDIT_BASE_URL||'http://127.0.0.1:8123/market-observatory/';
const widths=process.env.OBS_AUDIT_WIDTHS?process.env.OBS_AUDIT_WIDTHS.split(',').map(Number):[360,390,430,768,800,820,1024,1363];
const smoke=process.env.OBS_PUBLIC_SMOKE==='1';
(async()=>{
 const browser=await chromium.launch(); fs.mkdirSync('/tmp/obs-audit',{recursive:true});
 for(const width of widths){
  const page=await browser.newPage({viewport:{width,height:960},hasTouch:true});
  const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('OBS_PAGE_ERROR',e.message)});
  page.on('requestfailed',r=>console.error('OBS_REQUEST_FAILED',r.url(),r.failure()?.errorText));
  const expected=[...fs.readFileSync('market-observatory/index.html','utf8').matchAll(/src="(\.\/[^"?]+\.js\?v=[^"]+)"/g)].map(m=>m[1]);
  // On push, this public QA may start before GitHub Pages publishes the same
  // commit. Wait for the exact versioned assets without lowering the contract:
  // a missing deployment still fails after a bounded publication window.
  for(let attempt=0;attempt<25;attempt++){
   const target=new URL(base);if(attempt)target.searchParams.set('ui_verify',Date.now());
   await page.goto(target.href,{waitUntil:'networkidle',timeout:90000});
   const scripts=await page.locator('script[src]').evaluateAll(es=>es.map(e=>e.getAttribute('src')));
   const missing=expected.filter(src=>!scripts.includes(src));
   if(!missing.length){console.log('OBS_UI_PUBLICATION_MATCH attempt='+attempt);break;}
   console.log('OBS_UI_PUBLICATION_WAIT attempt='+attempt+' missing='+JSON.stringify(missing));
   assert(attempt<24,'Pages has not published the current UI asset versions: '+JSON.stringify(missing));
   await page.waitForTimeout(10000);
  }
  await page.waitForSelector('body.obsDeviceUI');
  await page.waitForSelector('#latestMarketBoard .latestTile');
  await page.waitForSelector('#tabs [data-tab="indices"]');
  await page.waitForSelector('[data-fresh-key="audit"]',{state:'attached'});
  if(smoke){
   for(const range of ['1Y','10Y','30Y']){
    await page.locator(`.obsRange[data-for="marketChart"] [data-range="${range}"]`).click();
    await page.waitForFunction(r=>{const t=document.querySelector('[data-coverage="marketChart"]')?.textContent||'';return t.startsWith(r+' 표시')&&!t.includes('로딩중')},range);
    const plot=await page.evaluate(()=>{const c=Chart.getChart(document.querySelector('#marketChart'));return {type:c.scales.x.type,min:c.scales.x.min,max:c.scales.x.max,count:c.data.datasets[0].data.length}});
    assert.equal(plot.type,'linear');assert(plot.min>0&&plot.max>plot.min&&plot.count>10,JSON.stringify(plot));
   }
   await page.locator('.obsRange[data-for="marketChart"] [data-range="5Y"]').click();
  }
  for(const tab of ['overview','morning-brief','official-macro','indices','fx','energy','analysis-lab','sectors','regime','tripod','jjooni-tripod','rates','calendar']){
   await page.locator(`#tabs [data-tab="${tab}"]`).click();
   if(tab==='overview'){
    const card=page.locator('#latestMarketBoard .latestChangeFirst[data-metric="NASDAQ100"]');await card.waitFor();
    const layout=await page.evaluate(()=>{const e=document.querySelector('#latestMarketBoard .latestChangeFirst[data-metric="NASDAQ100"]');const primary=e.querySelector('.latestPrimaryValue'),level=e.querySelector('.latestLevelValue');return {primary:parseFloat(getComputedStyle(primary).fontSize),level:parseFloat(getComputedStyle(level).fontSize),first:primary.getBoundingClientRect().top<level.getBoundingClientRect().top,label:e.querySelector('.latestPrimaryLabel').textContent,clipped:primary.scrollWidth>primary.clientWidth+1}});
    assert(layout.primary>=26&&layout.primary>layout.level,'change must dominate level '+JSON.stringify(layout));
    assert(layout.first&&!layout.clipped,'primary change must fit and precede level '+JSON.stringify(layout));
    assert(['일간 대비','전일 종가 대비'].includes(layout.label),layout.label);
   }
   if(tab==='jjooni-tripod'){
    const overlay=page.locator('#jjooniTripodRoot');
    await overlay.waitFor();
    await page.waitForFunction(()=>document.querySelector('#jjooniTripodRoot')?.textContent.includes('쭈니 스타일 TRI-POD'));
    assert.match(await overlay.innerText(),/QLD/,'new tab must render Jjooni QLD overlay');
   }
   if(tab==='analysis-lab')await page.waitForFunction(()=>window.__JJOONI_ANALYSIS_LAB.loaded);
   if(tab==='sectors')await page.waitForFunction(()=>window.__JJOONI_OBSERVATORY_SECTOR_ETF_V1.loaded);
   const result=await page.evaluate(()=>{
    const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
    const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}};
    const panel=document.querySelector('.panel.on');
    return {width:innerWidth,scroll:document.documentElement.scrollWidth,bodyScroll:document.body.scrollWidth,tab:panel.id,
     nav:rect(document.querySelector('#tabs')),header:rect(document.querySelector('.top')),
     freshness:rect(document.querySelector('#obsFreshnessPanel')),
     smallTargets:[...document.querySelectorAll('#tabs button,.obsRange button,.latestCompare button')].filter(visible).filter(e=>e.getBoundingClientRect().height<44).length,
     clipped:[...panel.querySelectorAll('select,input,button,.card,.obsMacroRow,.labSeriesRow')].filter(visible).filter(e=>{const r=e.getBoundingClientRect();return r.left<0||r.right>innerWidth+1}).map(e=>({tag:e.tagName,cls:e.className,...rect(e)})).slice(0,10),
     textMin:Math.min(...[...panel.querySelectorAll('.meta,.obsCoverage,.obsMacroCell span')].filter(visible).map(e=>parseFloat(getComputedStyle(e).fontSize))) };
   });
   console.log('DEVICE_AUDIT '+JSON.stringify(result));
   // The scrollingElement is the authoritative horizontal-scroll viewport.
   // body.scrollWidth may include overflow from a deliberately scrollable,
   // clipped header chip row even though the page itself never scrolls sideways.
   const scrollingWidth=await page.evaluate(()=>document.scrollingElement.scrollWidth);
   assert(scrollingWidth<=width+1&&result.scroll<=width+1,
     'page viewport overflow '+JSON.stringify({...result,scrollingWidth}));
   if(await page.locator('body.obsDeviceUI').count()){
    assert.equal(result.smallTargets,0,'small touch targets '+JSON.stringify(result));
    assert(result.textMin>=11||result.textMin===null,'small text '+JSON.stringify(result));
    assert.equal(new URL(page.url()).hash,'#'+tab);
    if(['overview','tripod'].includes(tab)){const next=page.locator('#latestMarketBoard .tripodNext');await next.waitFor();assert.match(await next.innerText(),/다음 스텝/);const clipped=await next.evaluate(e=>[e,...e.querySelectorAll('article')].some(n=>{const r=n.getBoundingClientRect();return r.left<0||r.right>innerWidth+1}));assert.equal(clipped,false,'transition card overflow');}
    if(tab==='official-macro'){const row=page.locator('[data-macro-key=US_CORE_PCE]');await row.waitFor();assert.match(await row.innerText(),/발표 실제/);assert(await row.getByText(/예상 ·/).isVisible());assert(await row.getByText('Surprise',{exact:true}).isVisible());}
    if(tab==='analysis-lab'){assert.equal(await page.locator('#analysis-lab .obsRange').count(),0);const folded=await page.locator('.labControls').getAttribute('open');assert.equal(folded===null,width<=1100);await page.locator('#labExpand').click();assert(await page.locator('.labExpanded').isVisible());await page.keyboard.press('Escape');assert.equal(await page.locator('.labExpanded').count(),0);}
    if(tab==='regime'){if(await page.getByText('유효기간이 끝난 과거 합의문입니다.',{exact:false}).count())assert.equal(await page.locator('.mrActions').isVisible(),false);}
   }
   if([390,820].includes(width)&&['overview','official-macro','analysis-lab','sectors'].includes(tab)){
    if(tab!=='overview')await page.evaluate(()=>document.querySelector('.panel.on').scrollIntoView({block:'start'}));
    const data=await page.screenshot({type:'jpeg',quality:45});
    // Public market UI only; no morning brief or account/portfolio screenshots.
    console.log(`AUDIT_IMAGE ${width}-${tab} ${data.toString('base64')}`);
   }
  }
  if([390,820].includes(width)&&await page.locator('body.obsDeviceUI').count()){
   if(await page.locator('#obsCalendarDelay').isVisible()){
    await page.locator('#obsCalendarDelay').click();
    try {
      await page.waitForFunction(()=>{const r=document.querySelector('#events [data-actual-status="OVERDUE"]')?.getBoundingClientRect();return r&&r.top>=0&&r.top<innerHeight});
    } catch(err) {
      const diag=await page.evaluate(()=>{const row=document.querySelector('#events [data-actual-status="OVERDUE"]');const rect=row?.getBoundingClientRect();return {hash:location.hash,month:document.querySelector('#calendarMonth')?.textContent,calendarActive:document.querySelector('#calendar')?.classList.contains('on'),overdueRows:document.querySelectorAll('#events [data-actual-status="OVERDUE"]').length,rowRect:rect?{top:rect.top,bottom:rect.bottom}:null,viewport:innerHeight,button:document.querySelector('#obsCalendarDelay')?.textContent,eventsText:document.querySelector('#events')?.textContent?.slice(0,180)}});
      console.error('CALENDAR_DELAY_NAV_DIAGNOSTIC',JSON.stringify({width,...diag}));
      throw err;
    }
   }
   await page.locator('.obsFreshDetails>summary').click();
   const expectedGroups=await page.evaluate(()=>window.__JJOONI_FRESHNESS_ALL_GROUPS.order.length+1);
   await page.waitForFunction(n=>document.querySelectorAll('#obsFreshGrid .obsFreshTile').length===n,expectedGroups);
   assert.equal(await page.locator('#obsFreshGrid .obsFreshTile:visible').count(),expectedGroups);
   assert.equal(await page.locator('[data-fresh-key=market_regime]').count(),1);
   await page.locator('#obsWatchToggle').click();assert(await page.locator('#obsWatchAnalysis').isVisible());
   await page.locator('.obsFreshDetails>summary').click();assert.equal(await page.locator('#obsWatchAnalysis').isVisible(),false);
  }
  if(smoke){
   await page.locator('#tabs [data-tab="rates"]').click();
   for(const grain of ['daily','weekly','monthly','intraday']){
    await page.locator(`[data-rate-grain="${grain}"]`).click();
    await page.waitForFunction(()=>document.querySelector('[data-rate-summary]')?.textContent.includes('개 관측'));
    assert(await page.locator('#usRatesIntraday canvas').isVisible());
   }
   await page.locator('#tabs [data-tab="calendar"]').click();
   await page.locator('#events .obsCalEditBtn').first().click();
   assert(await page.locator('#obsCalEditor.on').isVisible());
   assert(await page.locator('#obsCalEditor input[data-field]').count()>=3);
   await page.locator('#obsCalEditor [data-act="close"]').click();
   assert.equal(await page.locator('#obsCalEditor.on').count(),0);
   console.log('OBS_PUBLIC_E2E=PASS width='+width+' current-assets ranges=1Y/10Y/30Y calendar-editor=read-only');
  }
  assert.deepEqual(errors,[]);
  await page.close();
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
