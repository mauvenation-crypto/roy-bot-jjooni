(()=>{
'use strict';
const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const clean=rows=>[...new Map((rows||[]).filter(p=>p&&/^\d{4}-\d{2}-\d{2}$/.test(p.date)&&finite(p.value)).map(p=>[p.date,{date:p.date,value:Number(p.value)}])).values()].sort((a,b)=>a.date.localeCompare(b.date));
function windowRows(rows,range){if(!rows.length||range==='ALL')return rows;const end=Date.parse(rows.at(-1).date+'T00:00:00Z');return rows.filter(p=>Date.parse(p.date+'T00:00:00Z')>=end-({ '1M':31,'3M':92,'1Y':366 }[range]||366)*86400000)}
function position(rows){if(!rows.length)return null;const values=rows.map(p=>p.value),low=Math.min(...values),high=Math.max(...values),last=rows.at(-1);return{low,high,last,ratio:high===low?null:(last.value-low)/(high-low)}}
const format=(v,d=2,suffix='')=>finite(v)?Number(v).toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d})+suffix:'—';
function model(key){
 const data=typeof DATA!=='undefined'?DATA:null;if(!data)return null;
 const item=window.__JJOONI_LATEST_BOARD?.items?.find(x=>x.k===key)||(key==='KR_US_10Y'?{k:key,label:'한국−미국 10년 금리차',digits:3,suffix:'%',kind:'bp'}:null);
 if(key==='KR_US_10Y'&&!data.series?.[key]?.length){
  const us=new Map(clean(data.series?.US10Y_OFFICIAL).map(p=>[p.date,p.value]));
  return{title:item.label,digits:3,suffix:'%',prefix:'',kind:'bp',lines:[{label:item.label,rows:clean(data.series?.KR10Y).filter(p=>us.has(p.date)).map(p=>({date:p.date,value:p.value-us.get(p.date)}))}],basis:'한국 10년 − 미국 재무부 공식 10년 · 동일 관측일끼리 계산'};
 }
 if(item)return{title:item.label,digits:item.digits,suffix:item.suffix||'',prefix:item.prefix||'',kind:item.kind,lines:[{label:item.label,rows:clean(window.__JJOONI_LATEST_BOARD?.getSeries?.(item)||(data.series?.[item.seriesKey||key]||[]))}],note:item.seriesKey?`시장 지수와 공식 일별 금리는 다른 지표입니다. 미 재무부 공식 일별: ${format(data.series?.[key]?.at(-1)?.value,2,'%')} (${data.series?.[key]?.at(-1)?.date||'관측일 미확인'})`:'',basis:item.seriesKey?'Cboe 금리지수 · Yahoo 일별 · 시장 원천 정밀도 유지':(['US3M','US2Y'].includes(key)?'미 재무부 공식 일별 · 원천 소수 2자리 · 시장 금리지수와 별도 기준':'일별 관측값 · 날짜는 원천의 거래일/관측일 기준')};
 const t=data.tripod_latest||{},history=[...(data.tripod_history||[])];const date=t.session_date||t.date;
 if(date)history.push({...t,vix:t.vix??t.vix_latest_close,date});
 const display=window.__JJOONI_LATEST_BOARD?.getTripodDisplay?.(),returnToMax=display?.available&&display.pod==='BIPOD'&&t.regime==='상승',boundaryTitle=returnToMax?'트라이팟 복귀가격':'바이팟 전환가격';
 const line=(label,field,factor=1)=>({label,rows:clean(history.map(p=>({date:p.date,value:finite(p[field])?Number(p[field])*factor:null})))});
 const definitions={
  TRIPOD_TREND:{title:'현재 상태 · NASDAQ 100과 MA250',lines:[line('NASDAQ 100','ndx'),line('MA250','ma250')],note:`현재 전략: ${display?.stateLabel||'미확인'} · ${t.regime||'미확인'} 레짐 · 상승 진입 MA250 × 1.01 / 하락 진입 MA250 × 0.95`,thresholds:true},
  TRIPOD_TARGET:{title:'목표 노출 · 판단 근거',lines:[line('NASDAQ 100','ndx'),line('MA250','ma250')],note:`현재 목표: ${t.target||'미확인'} · 아래에서 VIX와 낙폭 근거도 확인하세요.`,thresholds:true},
  TRIPOD_MA:{title:'MA250 · 계산 참고값',lines:[line('MA250','ma250'),line('NASDAQ 100','ndx')],note:'MA250 자체는 레짐 전환선이 아닙니다. 상승 전환은 MA250 × 1.01 초과, 하락 전환은 MA250 × 0.95 미만 종가이며 사이에서는 이전 레짐을 유지합니다.'},
  TRIPOD_BIPOD:{title:boundaryTitle+' · 52주 고점 −9%',lines:[{label:returnToMax?'트라이팟 복귀선':'바이팟 감속선',rows:clean(history.map(p=>({date:p.date,value:finite(p.ndx)&&finite(p.drawdown_52w_pct)&&Number(p.ndx)>0&&Number(p.drawdown_52w_pct)>-100?Number(p.ndx)/(1+Number(p.drawdown_52w_pct)/100)*.91:null})))},line('NASDAQ 100','ndx')],note:(returnToMax?'현재 바이팟: 종가가 이 선 이상이고 VIX10 < 28을 모두 충족해야 트라이팟으로 복귀합니다. ':'현재 트라이팟: 종가가 이 선 미만 또는 VIX10 ≥ 28이면 바이팟으로 감속합니다. ')+'이 가격선 = 최근 252거래일 최고 종가 × 0.91입니다. 전주 대비 0.00pt는 최고 종가가 지난주와 같아 전환선이 변하지 않았다는 뜻입니다. 상승 레짐에서 종가가 이 가격 미만이거나 VIX10 ≥ 28이면 감속하며, MA250 × 1.01 상승 복귀선과는 구분합니다.'},
  TRIPOD_FALL:{title:'NOPOD 가격선 · MA250 × 0.95',lines:[line('하락 전환선','ma250',.95),line('NASDAQ 100','ndx')],note:'이 가격선은 MA250 × 0.95이며 52주 고점 대비 낙폭 기준이 아닙니다. 종가가 이 선 미만이면 하락 레짐으로 전환하고, VIX10 ≥ 18이면 노팟(현금 100%), 18 미만이면 감속 목표입니다. 두 레짐 전환선 사이에서는 이전 레짐을 유지합니다. 카드의 거리는 현재 NDX 종가 대비입니다.'},
  TRIPOD_RISE:{title:'레짐 상승 전환선 · MA250 × 1.01',lines:[line('상승 전환선','ma250',1.01),line('NASDAQ 100','ndx')],note:'종가가 이 선을 초과하면 상승 레짐입니다. 실제 목표 노출은 VIX10과 52주 고점 대비 낙폭을 함께 판정합니다.'},
  TRIPOD_VIX:{title:'VIX와 10일 평균',lines:[line('VIX','vix'),line('VIX 10일 평균','vix10')],levels:[18,28],note:'레짐별 VIX10 경계: 하락 상태 18 / 상승 상태 28. 일일 VIX와 구분해 확인하세요.'},
  TRIPOD_DD:{title:'52주 고점 대비 낙폭',lines:[line('52주 고점 대비','drawdown_52w_pct')],suffix:'%',levels:[-9],note:'상승 상태에서 낙폭이 9%를 초과하면 감속 조건입니다.'}
 };
 const m=definitions[key];if(!m)return null;
 if(m.thresholds){const ma=line('MA250','ma250');m.lines.push({label:'상승 진입 ×1.01',rows:ma.rows.map(p=>({...p,value:p.value*1.01})),dashed:true},{label:'하락 진입 ×0.95',rows:ma.rows.map(p=>({...p,value:p.value*.95})),dashed:true})}
 return{digits:2,suffix:'',prefix:'',basis:'TRI-POD 완료세션 · 저장된 관측 이력',...m};
}
let dialog,chart,selected,range='1Y',opener,scrollBefore,previousOverflow;
function close(){dialog?.close()}
function ensure(){if(dialog)return;
 const style=document.createElement('style');style.textContent=`
 [data-gate],[data-open-calendar]{cursor:pointer}[data-gate]:focus-visible,[data-open-calendar]:focus-visible{outline:3px solid #3478db;outline-offset:2px}.latestTile[data-metric]{cursor:pointer;transition:border-color .15s,box-shadow .15s}.latestTile[data-metric]:hover{border-color:#5e8fc7;box-shadow:0 3px 14px #2368a322}.latestTile[data-metric]:focus-visible{outline:3px solid #3478db;outline-offset:2px}.latestTile[data-metric] .latestTileTop:after{content:'↗';margin-left:auto;color:#426f9f;font-size:15px}
 .obsMetricDialog{box-sizing:border-box;width:min(880px,calc(100% - 32px));max-height:90dvh;border:0;border-radius:20px;padding:0;color:#10233d;box-shadow:0 18px 80px #10233d55;overflow:auto;overscroll-behavior:contain}.obsMetricDialog::backdrop{background:#10233d88}.obsMetricHead{position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:12px;background:white;border-bottom:1px solid #e3eaf2;padding:16px 20px}.obsMetricHead h2{font-size:20px;margin:0}.obsMetricDialog button{font:inherit;min-height:44px;min-width:44px;border:1px solid #ccd8e5;background:white;border-radius:10px;padding:8px 12px;color:#153b65;cursor:pointer}.obsMetricBody{padding:16px 20px 24px}.obsMetricValue{font-size:30px;font-weight:850}.obsMetricMeta,.obsMetricNote{font-size:14px;line-height:1.6;color:#526071}.obsMetricRanges,.obsMetricRelated{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.obsMetricRanges button[aria-pressed=true]{background:#153b65;color:white}.obsMetricPlot{height:310px;position:relative;margin:16px 0}.obsMetricStats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.obsMetricStats div{padding:12px;border-radius:12px;background:#f1f5fa;font-size:14px;overflow-wrap:anywhere}.obsMetricStats b{display:block;font-size:18px;margin-top:6px}.obsMetricPosition{position:relative;height:10px;border-radius:10px;background:linear-gradient(90deg,#dce8fa,#84a9d2);margin:18px 8px 8px}.obsMetricPosition i{position:absolute;top:-4px;width:10px;height:18px;border-radius:5px;background:#133e6b;transform:translateX(-50%)}.obsMetricDialog button:focus-visible{outline:3px solid #3478db;outline-offset:2px}
 @media(max-width:600px){.obsMetricDialog{width:100%;max-width:100%;max-height:92dvh;margin:auto 0 0;border-radius:20px 20px 0 0;padding-bottom:env(safe-area-inset-bottom)}.obsMetricHead,.obsMetricBody{padding-left:16px;padding-right:16px}.obsMetricHead h2{font-size:18px}.obsMetricPlot{height:280px}.obsMetricStats b{font-size:16px}.obsMetricStats div{padding:10px 8px}.obsMetricDialog:before{content:'';display:block;width:40px;height:4px;border-radius:4px;background:#bcc9d7;margin:8px auto 0}}
 @media(prefers-reduced-motion:reduce){.latestTile[data-metric]{transition:none}}
 `;document.head.appendChild(style);
 dialog=document.createElement('dialog');dialog.className='obsMetricDialog';dialog.setAttribute('aria-labelledby','obsMetricTitle');dialog.innerHTML='<header class="obsMetricHead"><h2 id="obsMetricTitle"></h2><button type="button" data-close aria-label="그래프 닫기">닫기</button></header><div class="obsMetricBody"><div class="obsMetricValue"></div><div class="obsMetricMeta"></div><div class="obsMetricNote"></div><nav class="obsMetricRanges" aria-label="그래프 조회기간"></nav><div class="obsMetricPlot"><canvas aria-label="선택 지표 추이" role="img"></canvas></div><div class="obsMetricStats"></div><div class="obsMetricPosition" aria-hidden="true"><i></i></div><p class="obsMetricPositionText obsMetricMeta"></p><p class="obsMetricBasis obsMetricMeta"></p><div class="obsMetricRelated"></div></div>';document.body.appendChild(dialog);
 dialog.querySelector('[data-close]').onclick=close;
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close()}});
 dialog.addEventListener('close',()=>{chart?.destroy();chart=null;document.body.style.overflow=previousOverflow;window.scrollTo({top:scrollBefore,behavior:'instant'});if(opener?.isConnected)opener.focus({preventScroll:true});else document.querySelector(`[data-metric="${selected}"]`)?.focus({preventScroll:true})});
}
function paint(){
 const m=model(selected);if(!m)return;chart?.destroy();chart=null;
 const lines=m.lines.map(l=>({...l,rows:windowRows(l.rows,range)})),rows=lines[0].rows,pos=position(rows),value=v=>(m.prefix||'')+format(v,m.digits,m.suffix);
 dialog.querySelector('h2').textContent=m.title;
 dialog.querySelector('.obsMetricValue').textContent=pos?value(pos.last.value):'관측값 없음';
 dialog.querySelector('.obsMetricMeta').textContent=pos?`최신 관측 ${pos.last.date} · ${rows.length}개 관측`:'확인 가능한 시계열이 없습니다.';
 dialog.querySelector('.obsMetricNote').textContent=m.note||'';
 const nav=dialog.querySelector('.obsMetricRanges');nav.replaceChildren();for(const [key,label] of [['1M','1개월'],['3M','3개월'],['1Y','1년'],['ALL','전체']]){const b=document.createElement('button');b.textContent=label;b.type='button';b.setAttribute('aria-pressed',String(range===key));b.onclick=()=>{range=key;paint();dialog.querySelector(`.obsMetricRanges button[aria-pressed="true"]`).focus({preventScroll:true})};nav.appendChild(b)}
 const stats=dialog.querySelector('.obsMetricStats');stats.replaceChildren();if(pos)for(const [label,val] of [['기간 최저',value(pos.low)],['최신 관측',value(pos.last.value)],['기간 최고',value(pos.high)]]){const el=document.createElement('div'),b=document.createElement('b');el.textContent=label;b.textContent=val;el.appendChild(b);stats.appendChild(el)}
 const meter=dialog.querySelector('.obsMetricPosition');meter.hidden=!pos||pos.ratio===null;if(pos?.ratio!=null)meter.querySelector('i').style.left=pos.ratio*100+'%';
 dialog.querySelector('.obsMetricPositionText').textContent=!pos?'':pos.ratio===null?'기간 내 관측값이 동일합니다.':`선택 기간 저점 → 고점 사이 현재 위치 ${format(pos.ratio*100,1)}% · 수익률·백분위가 아닙니다.`;
 dialog.querySelector('.obsMetricBasis').textContent=m.basis+(pos?` · ${rows[0].date} ~ ${pos.last.date}`:'')+' · 실시간 가격이 아닌 최신 저장 관측값';
 const related=dialog.querySelector('.obsMetricRelated');related.replaceChildren();if(selected.startsWith('TRIPOD_'))for(const [key,label] of [['TRIPOD_TREND','지수·기준선'],['TRIPOD_VIX','VIX·VIX10'],['TRIPOD_DD','52주 낙폭']]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{selected=key;paint()};related.appendChild(b)}
 const canvas=dialog.querySelector('canvas');canvas.hidden=!pos||typeof Chart==='undefined';if(!pos)return;
 if(typeof Chart==='undefined'){dialog.querySelector('.obsMetricBasis').textContent+=' · 그래프 모듈을 불러오지 못했습니다.';return}
 const colors=['#2167ae','#c07721','#5c869f','#9974ba'];
 const datasets=lines.map((l,i)=>({label:l.label,data:l.rows.map(p=>({x:Date.parse(p.date+'T00:00:00Z'),y:p.value})),borderColor:colors[i%4],borderWidth:2,pointRadius:ctx=>ctx.dataIndex===l.rows.length-1?4:0,pointHitRadius:18,borderDash:l.dashed?[5,4]:[],spanGaps:false}));
 for(const level of m.levels||[])datasets.push({label:`판단 경계 ${level}`,data:[rows[0],rows.at(-1)].map(p=>({x:Date.parse(p.date+'T00:00:00Z'),y:level})),borderColor:'#9b789b',borderDash:[5,4],pointRadius:0});
 const compare=window.__JJOONI_LATEST_BOARD?.getComparison?.();
 const source=m.lines[0].rows,last=source.at(-1);let reference=null,referenceLabel='';
 if(selected==='TRIPOD_BIPOD'&&last){
  // Match the BIPOD card: compare against the final completed close of the prior Mon-Sun week.
  const monday=new Date(last.date+'T00:00:00Z');monday.setUTCDate(monday.getUTCDate()-((monday.getUTCDay()+6)%7));
  const from=new Date(monday);from.setUTCDate(from.getUTCDate()-7);
  reference=source.filter(p=>p.date>=from.toISOString().slice(0,10)&&p.date<monday.toISOString().slice(0,10)).at(-1)||null;
  if(reference)referenceLabel=`전주 마지막 거래일 (${reference.date})`;
 }else if(last&&compare){
  const d=new Date(last.date+'T00:00:00Z');
  if(compare.mode==='prev')reference=source.at(-2);
  else{if(compare.days)d.setUTCDate(d.getUTCDate()-compare.days);if(compare.months)d.setUTCMonth(d.getUTCMonth()-compare.months);if(compare.years)d.setUTCFullYear(d.getUTCFullYear()-compare.years);reference=source.filter(p=>p.date<=d.toISOString().slice(0,10)).at(-1)}
  referenceLabel=`${compare.label} 비교 기준`;
 }
 if(reference&&reference.date>=rows[0].date){datasets.push({label:`${referenceLabel} ${value(reference.value)}`,data:[rows[0],rows.at(-1)].map(p=>({x:Date.parse(p.date+'T00:00:00Z'),y:reference.value})),borderColor:'#7c8c9d',borderDash:[3,5],pointRadius:0})}
 const dateLabel=n=>new Date(Number(n)).toISOString().slice(0,10);
 chart=new Chart(canvas,{type:'line',data:{datasets},options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'nearest',axis:'x',intersect:false},plugins:{legend:{position:'bottom',labels:{font:{size:12},boxWidth:16}},tooltip:{callbacks:{title:items=>items.length?dateLabel(items[0].parsed.x):'',label:c=>`${c.dataset.label}: ${value(c.parsed.y)}`}}},scales:{x:{type:'linear',min:Date.parse(rows[0].date+'T00:00:00Z'),max:Date.parse(rows.at(-1).date+'T00:00:00Z'),ticks:{maxTicksLimit:4,callback:v=>dateLabel(v).slice(2)}},y:{ticks:{maxTicksLimit:5,callback:v=>format(v,m.digits,m.suffix)}}}}});
}
function open(key,trigger){if(dialog?.open||!model(key))return;ensure();opener=trigger;selected=key;range='1Y';scrollBefore=window.scrollY;previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.showModal();paint();dialog.querySelector('[data-close]').focus({preventScroll:true})}
document.addEventListener('click',e=>{if(e.target.closest('[data-open-calendar]')){document.querySelector('#tabs [data-tab=calendar]')?.click();return}const tile=e.target.closest('[data-metric]');if(tile)open(tile.dataset.metric,tile);const gate=e.target.closest('[data-gate]');if(gate)open({drawdown:'TRIPOD_DD',vix:'TRIPOD_VIX',fall:'TRIPOD_FALL',rise:'TRIPOD_RISE',trend:'TRIPOD_TREND'}[gate.dataset.gate]||'TRIPOD_TREND',gate)});
document.addEventListener('keydown',e=>{const tile=e.target.closest('[data-metric],[data-gate],[data-open-calendar]');if(tile&&['Enter',' '].includes(e.key)){e.preventDefault();tile.click()}});
// Install click affordances before the first interaction.
ensure();
// Base Overview KPIs and pulse chips share the same drilldown contract.
function linkExisting(){
 const keys={NASDAQ100:'NASDAQ100',VIX:'VIX',DXY:'DXY',WTI:'WTI','US 2s10s':'US_2S10S','KR 3s10s':'KR_3S10S','JP 2s10s':'JP_2S10S','KR-US 10Y':'KR_US_10Y'};
 for(const el of document.querySelectorAll('#overviewKpis .kpi,#spreadKpis .kpi')){const k=keys[el.querySelector('small')?.textContent];if(!k)continue;el.dataset.metric=k;el.setAttribute('role','button');el.setAttribute('tabindex','0');el.setAttribute('aria-haspopup','dialog');el.setAttribute('aria-label',el.querySelector('small').textContent+' 추이 보기');el.style.cursor='pointer'}
 for(const el of document.querySelectorAll('#pulse .chip')){const item=window.__JJOONI_LATEST_BOARD?.items?.find(i=>el.textContent.startsWith(i.label+' '));if(item){el.dataset.metric=item.k;el.setAttribute('role','button');el.setAttribute('tabindex','0');el.setAttribute('aria-haspopup','dialog');el.setAttribute('aria-label',item.label+' 추이 보기');el.style.cursor='pointer'}}
}
const links=new MutationObserver(linkExisting);for(const id of ['overviewKpis','spreadKpis','pulse']){const el=document.getElementById(id);if(el)links.observe(el,{childList:true})}linkExisting();
window.__JJOONI_METRIC_DETAIL={version:'1.6-bipod-weekly',clean,windowRows,position,model};
})();
