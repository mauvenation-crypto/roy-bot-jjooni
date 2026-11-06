(function(){
'use strict';

const RT={state:'ACTIVE',render_state:'WAITING_FOR_PANEL',version:'26.9',rendered_at:null,trade_count:0,buy_count:0,sell_count:0,realized_known:0,opportunity_known:0,missing_realized:0,missing_opportunity:0,sort:'RECENT_DESC',formula:'BUY=(basis-trade)*qty;SELL=(trade-basis)*qty',horizon:'now',horizon_label:'현재'};
window.__JJOONI_TRADE_OUTCOMES_V26=RT;
const q=(s,r=document)=>{try{return r.querySelector(s)}catch(_){return null}};
const n=v=>{if(v===null||v===undefined||v==='')return null;const x=Number(String(v).replace(/,/g,''));return Number.isFinite(x)?x:null};
const sym=v=>String(v||'').trim().toUpperCase().replace(/\.(KS|KQ)$/,'');
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const side=t=>{const s=String(t?.side||'').toUpperCase();return s.includes('SELL')||s.includes('매도')?'SELL':s.includes('BUY')||s.includes('매수')?'BUY':'OTHER'};
const acct=t=>String(t?.account||t?.account_type||'UNKNOWN').toUpperCase();
const qty=t=>Math.abs(n(t?.qty??t?.quantity??t?.filled_qty)??0);
const px=t=>n(t?.price??t?.filled_price??t?.avg_price);
const ccy=t=>String(t?.currency||((String(t?.market||'').toUpperCase()==='US')?'USD':'KRW')).toUpperCase();
const ts=t=>String(t?.filled_at_kst||t?.filled_at||t?.trade_date||t?.date||'');
const HORIZONS=[
 {key:'now',label:'현재'},
 {key:'5d',label:'5영업일'},
 {key:'10d',label:'10영업일'},
 {key:'1m',label:'1개월'},
 {key:'6m',label:'6개월'}
];
const horizonDef=key=>HORIZONS.find(x=>x.key===key)||HORIZONS[0];
function tradeTs(t){
 const raw=ts(t).trim();
 if(!raw)return 0;
 let m=raw.match(/^(\d{2})(\d{2})(\d{2})(?:\D?(\d{2})(\d{2})(\d{2})?)?$/);
 if(m){
  const y=2000+Number(m[1]),mo=Number(m[2]),d=Number(m[3]),hh=Number(m[4]||0),mm=Number(m[5]||0),ss=Number(m[6]||0);
  const v=Date.parse(`${String(y).padStart(4,'0')}-${String(mo).padStart(2,'0')}-${String(d).padStart(2,'0')}T${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')}+09:00`);
  return Number.isFinite(v)?v:0;
 }
 m=raw.match(/^(\d{4})(\d{2})(\d{2})(?:\D?(\d{2})(\d{2})(\d{2})?)?$/);
 if(m){
  const y=Number(m[1]),mo=Number(m[2]),d=Number(m[3]),hh=Number(m[4]||0),mm=Number(m[5]||0),ss=Number(m[6]||0);
  const v=Date.parse(`${String(y).padStart(4,'0')}-${String(mo).padStart(2,'0')}-${String(d).padStart(2,'0')}T${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')}+09:00`);
  return Number.isFinite(v)?v:0;
 }
 const v=Date.parse(raw.length<=10?raw+'T00:00:00+09:00':raw);
 return Number.isFinite(v)?v:0;
}
const ticker=t=>sym(t?.ticker||t?.symbol);
const VERIFIED_SECURITY_NAMES={
 'IBBQ':'Invesco Nasdaq Biotechnology ETF',
 'XLV':'State Street Health Care Select Sector SPDR ETF',
 'KO':'The Coca-Cola Company',
 '066570':'LG전자',
 'SPCX':'The SPAC and New Issue ETF',
 '491010':'TIGER 글로벌AI전력인프라액티브'
};
const name=t=>{
 const tk=ticker(t),raw=String(t?.name||t?.stock_name||t?.security_name||t?.display_name||t?.product_name||t?.prdt_name||t?.prdt_abrv_name||t?.hts_kor_isnm||t?.kor_name||t?.korean_name||t?.english_name||t?.eng_name||'').trim();
 const verified=String(VERIFIED_SECURITY_NAMES[tk]||'').trim();
 if(verified)return verified;
 if(raw&&sym(raw)!==tk)return raw;
 try{
  const names=window.__JJOONI_SECURITY_NAMES||{},k=/^\d{1,6}$/.test(tk)?tk.padStart(6,'0'):tk;
  const mapped=String(names[k]||names[tk]||'').trim();
  if(mapped&&sym(mapped)!==tk)return mapped;
 }catch(_){}
 const candidate=o=>{
  if(!o)return '';
  const ot=sym(o.ticker||o.symbol||o.code||o.stock_code||o.pdno||'');
  if(ot!==tk)return '';
  const v=String(o.name||o.stock_name||o.security_name||o.display_name||o.product_name||o.prdt_name||o.hts_kor_isnm||'').trim();
  return v&&sym(v)!==tk?v:'';
 };
 try{
  const C=window.__JJOONI_CANONICAL_SSOT||{};
  for(const a of Object.values(C.accounts||{}))for(const x of (a?.positions||[])){const v=candidate(x);if(v)return v}
 }catch(_){}
 try{
  const d=(typeof D!=='undefined'&&D)?D:window.D;
  const w=d?.human?.watchlist||{};
  for(const x of [...(w.kr||[]),...(w.us||[])]){const v=candidate(x);if(v)return v}
  for(const x of (d?.human?.trades||[])){const v=candidate(x);if(v)return v}
 }catch(_){}
 return tk||raw||'UNKNOWN';
};

// Fund ledger amounts are not exchange-traded per-share prices. Until unit
// NAV and broker units are explicit, do not reconstruct either kind of profit.
function fundUnitsUnknown(t){return /^F\d+$/i.test(ticker(t))||String(t.record_type||t.asset_type||'').toUpperCase()==='FUND'||/증권.*투자신탁|혼합자산|적격TDF/.test(name(t))}
function firstNum(o,keys){for(const k of keys){const x=n(o&&o[k]);if(x!==null)return {value:x,key:k}}return null}
function fee(t){return firstNum(t,['commission','fee','commission_krw','fee_krw'])?.value??0}
function tax(t){return firstNum(t,['tax','tax_krw','transaction_tax'])?.value??0}
function explicitRealized(t){
 let x=firstNum(t,['realized_pnl_krw','pnl_realized_krw','realized_profit_krw']);
 if(x)return {value:x.value,currency:'KRW',basis:'BROKER/LEDGER'};
 x=firstNum(t,['realized_pnl','pnl_realized','realized_profit']);
 return x?{value:x.value,currency:ccy(t),basis:'BROKER/LEDGER'}:null;
}
function money(v,c){
 if(v===null||!Number.isFinite(v))return '—';
 const sign=v>0?'+':v<0?'-':'';const a=Math.abs(v);
 return String(c).toUpperCase()==='USD'?sign+'$'+a.toLocaleString('en-US',{maximumFractionDigits:2}):sign+'₩'+Math.round(a).toLocaleString('ko-KR');
}
function price(v,c){if(v===null)return '—';return String(c).toUpperCase()==='USD'?'$'+v.toLocaleString('en-US',{maximumFractionDigits:2}):'₩'+Math.round(v).toLocaleString('ko-KR')}
function cls(v){return v===null?'na':v>0?'pos':v<0?'neg':'zero'}

function collectTrades(){
 const out=[];
 let d=null;
 try{d=(typeof D!=='undefined'&&D)?D:window.D}catch(_){d=window.D||null}
 try{if(d?.human&&Array.isArray(d.human.trades))out.push(...d.human.trades.filter(t=>!['AI','AIBOT','AI_BOT'].includes(acct(t))))}catch(_){}
 // The human ledger and the broker's recent fills are independent feeds.
 // Display only broker-confirmed TOSS orders, without writing a synthetic fill
 // into the immutable Master ledger or altering any account NAV/cost basis.
 const orderId=t=>String(t?.order_id||t?.broker_trade_id||t?.trade_key||t?.order_no||'').trim().replace(/^TOSS\|/i,'');
 const signature=t=>[acct(t),tradeTs(t),ticker(t),side(t),qty(t),px(t)].join('|');
 const knownOrders=new Set(out.map(t=>acct(t)+'|'+orderId(t)).filter(k=>!k.endsWith('|')));
 const knownExecutions=new Set(out.map(signature));
 const recent=window.__JJOONI_LIVE_PAYLOAD?.recent_trades;
 let accepted=0,duplicate=0,rejected=0;
 if(Array.isArray(recent))for(const t of recent){
  const src=String(t?.source||''),id=orderId(t);
  if(!['BROKER_DIRECT_TOSS_API','BROKER_DIRECT_TOSS_API_FAST'].includes(src)||acct(t)!=='TOSS'||!id||!ticker(t)||!['BUY','SELL'].includes(side(t))||!(qty(t)>0)||!(px(t)>0)||!(tradeTs(t)>0)){rejected++;continue}
  const key='TOSS|'+id,sig=signature(t);
  if(knownOrders.has(key)||knownExecutions.has(sig)){duplicate++;continue}
  out.push({...t,account:'TOSS',order_id:id});knownOrders.add(key);knownExecutions.add(sig);accepted++;
 }
 RT.broker_trade_bridge={state:Array.isArray(recent)?'CHECKED':'SOURCE_UNAVAILABLE',source_rows:Array.isArray(recent)?recent.length:null,accepted,duplicate,rejected,checked_at:new Date().toISOString()};
 const seen=new Set(),dedup=[];
 out.forEach((t,i)=>{
  const oid=orderId(t);
  const key=oid?'OID|'+acct(t)+'|'+oid:['SIG',acct(t),String(t?.trade_date||''),ticker(t),side(t),qty(t),px(t)].join('|');
  if(seen.has(key))return;seen.add(key);dedup.push({...t,__seq:i});
 });
 return dedup;
}

function reconstructRealized(trades){
 const books=new Map(),map=new Map();
 const ordered=[...trades].sort((a,b)=>{
  const at=tradeTs(a);
  const bt=tradeTs(b);
  return at-bt||a.__seq-b.__seq;
 });
 for(const t of ordered){
  const k=acct(t)+'|'+ticker(t),qv=qty(t),p=px(t);if(!ticker(t)||!qv||p===null)continue;
  if(fundUnitsUnknown(t)){if(side(t)==='SELL'){const ex=explicitRealized(t);map.set(t,ex?{...ex,state:'OK'}:{value:null,currency:ccy(t),basis:'FUND_UNITS_REQUIRED',state:'NA'})}continue}
  let b=books.get(k)||{qty:0,avg:null,incomplete:false};
  if(side(t)==='BUY'){
   if(b.qty<0)b.incomplete=true;
   const oldCost=(b.avg??0)*Math.max(0,b.qty),newQty=Math.max(0,b.qty)+qv;
   b.avg=newQty>0?(oldCost+p*qv)/newQty:p;b.qty=newQty;
  }else if(side(t)==='SELL'){
   const ex=explicitRealized(t);
   if(ex){map.set(t,{...ex,state:'OK'});b.qty=Math.max(0,b.qty-qv);if(b.qty<=1e-9)b.avg=null;}
   else if(!b.incomplete&&b.avg!==null&&b.qty+1e-9>=qv){
    const realized=(p-b.avg)*qv-fee(t)-tax(t);
    map.set(t,{value:realized,currency:ccy(t),basis:'WEIGHTED_AVG_LEDGER',state:'OK',avg_cost:b.avg});
    b.qty-=qv;if(b.qty<=1e-9){b.qty=0;b.avg=null}
   }else{
    map.set(t,{value:null,currency:ccy(t),basis:'COST_BASIS_INCOMPLETE',state:'NA'});
    b.incomplete=true;b.qty=Math.max(0,b.qty-qv);if(b.qty<=1e-9)b.avg=null;
   }
  }
  books.set(k,b);
 }
 return map;
}


function tradeDateKey(t){
 const raw=ts(t).trim();
 let m=raw.match(/^(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})/);
 if(m)return `${m[1]}-${m[2]}-${m[3]}`;
 m=raw.match(/^(\d{2})(\d{2})(\d{2})/);
 if(m)return `20${m[1]}-${m[2]}-${m[3]}`;
 return '';
}
function horizonStore(){
 let h=null;
 try{
  const d=(typeof D!=='undefined'&&D)?D:window.D;
  h=d?.human?.trade_review_horizons||null;
  if(h&&typeof h==='object'&&Object.keys(h).length)window.__JJOONI_TRADE_HORIZONS_V26=h;
 }catch(_){}
 return h||window.__JJOONI_TRADE_HORIZONS_V26||{};
}
function horizonBasis(t,key,curMap){
 const def=horizonDef(key);
 if(fundUnitsUnknown(t))return {price:null,state:'FUND_UNITS_REQUIRED',date:'',target:'',label:def.label};
 if(key==='now'){
  const cp=curMap.get(acct(t)+'|'+ticker(t))??null;
  return {price:cp,state:cp!==null?'PASS':'UNAVAILABLE',date:'',target:'',label:def.label};
 }
 const date=tradeDateKey(t),store=horizonStore(),marks=store[ticker(t)+'|'+date]||{},mark=marks[key]||{};
 const hp=n(mark.p??mark.price);
 return {
  price:hp!==null&&hp>0?hp:null,
  state:String(mark.s||mark.status||'UNAVAILABLE').toUpperCase(),
  date:String(mark.d||mark.date||''),
  target:String(mark.t||mark.target||''),
  label:String(mark.l||mark.label||def.label)
 };
}
function shortBasisDate(v){
 const m=String(v||'').match(/^(\d{4})-(\d{2})-(\d{2})/);
 return m?`${m[2]}/${m[3]}`:'';
}

function currentPriceMap(trades){
 const m=new Map();
 const set=(a,s,v)=>{const x=n(v);if(x!==null&&x>0&&s)m.set(String(a||'')+'|'+sym(s),x)};
 trades.filter(t=>!fundUnitsUnknown(t)).forEach(t=>set(acct(t),ticker(t),t.current_price??t.last_price));
 try{Object.entries(window.__JJOONI_CANONICAL_SSOT?.accounts||{}).forEach(([a,o])=>(o.positions||[]).forEach(p=>set(a,p.ticker||p.symbol,p.current_price||p.price||p.last_price)))}catch(_){}
 // Watchlist reference prices never override current account holdings.
 return m;
}

function buildRows(){
 const trades=collectTrades(),realized=reconstructRealized(trades),curMap=currentPriceMap(trades),horizon=RT.horizon||'now';
 return trades.filter(t=>['BUY','SELL'].includes(side(t))&&ticker(t)&&qty(t)>0&&px(t)!==null).map(t=>{
  const sd=side(t);
  const r=sd==='SELL'?(realized.get(t)||{value:null,currency:ccy(t),basis:'COST_BASIS_INCOMPLETE',state:'NA'}):{value:null,currency:ccy(t),basis:'BUY_NOT_REALIZED',state:'NA'};
  const mark=horizonBasis(t,horizon,curMap),cp=mark.price,entry=px(t);
  const op=cp!==null?(sd==='BUY'?(cp-entry)*qty(t):(entry-cp)*qty(t)):null;
  const perf=cp!==null&&entry>0?(sd==='BUY'?(cp/entry-1)*100:((entry-cp)/entry)*100):null;
  const dt=tradeTs(t);
  return {t,realized:r,current:cp,opportunity:op,performance_pct:perf,time:dt,seq:t.__seq,trade_side:sd,basis:mark};
 }).sort((a,b)=>b.time-a.time||b.seq-a.seq).slice(0,40);
}

function ensureStyle(){
 if(q('#ctTradeOutcomeV26Style'))return;
 const s=document.createElement('style');s.id='ctTradeOutcomeV26Style';s.textContent=`
 #ctTradeOutcomeV26{margin:8px 0 12px;font-family:system-ui,-apple-system,sans-serif;color:#172b45}
 .ctO26Head{display:flex;justify-content:space-between;gap:10px;align-items:end;margin:0 2px 7px}.ctO26Title{font-size:17px;font-weight:950}.ctO26Sub{font-size:10px;color:#718196;margin-top:2px}.ctO26Badge{font-size:10px;font-weight:850;color:#38526c;background:#eef4fa;border:1px solid #d9e4ef;border-radius:999px;padding:5px 8px;white-space:nowrap}
 .ctO26Horizons{display:flex;gap:5px;overflow-x:auto;padding:1px 1px 7px;margin:0 1px 2px;scrollbar-width:none}.ctO26Horizons::-webkit-scrollbar{display:none}.ctO26HBtn{appearance:none;border:1px solid #dbe5ef;background:#fff;color:#5f7186;border-radius:999px;padding:6px 10px;font:850 10px/1 system-ui;white-space:nowrap;cursor:pointer}.ctO26HBtn.active{background:#0b3b70;border-color:#0b3b70;color:#fff}.ctO26Summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-bottom:7px}.ctO26Sum{background:#fff;border:1px solid #e0e7ef;border-radius:10px;padding:8px 10px;min-height:54px}.ctO26Sum span{display:block;font-size:10px;color:#718196;font-weight:750}.ctO26Sum b{display:block;font-size:16px;line-height:1.15;margin-top:4px;letter-spacing:-.02em}.ctO26Sum small{display:block;font-size:9px;color:#8a98a8;margin-top:2px}
 .ctO26List{display:grid;gap:5px}.ctO26Row{background:#fff;border:1px solid #e1e7ee;border-radius:10px;padding:8px 10px;display:grid;grid-template-columns:minmax(150px,1.35fr) repeat(2,minmax(105px,.65fr));gap:8px;align-items:center;box-shadow:0 2px 8px rgba(22,43,69,.025)}.ctO26Name{font-size:13px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ctO26Meta{font-size:10px;color:#748398;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ctO26Metric span{display:block;font-size:9px;color:#78889c;font-weight:750}.ctO26Metric b{display:block;font-size:13px;margin-top:2px}.ctO26Metric small{font-size:8px;color:#93a0ad}.ctO26Metric .pos{color:#d43f53}.ctO26Metric .neg{color:#2167c9}.ctO26Metric .zero{color:#48596b}.ctO26Metric .na{color:#8b98a6}.ctO26Empty{background:#fff;border:1px dashed #dce5ee;border-radius:10px;padding:14px;font-size:12px;color:#748398;text-align:center}
 @media(max-width:700px){.ctO26Row{grid-template-columns:1fr 1fr;gap:6px}.ctO26Identity{grid-column:1/-1}.ctO26Metric b{font-size:12px}.ctO26Summary{grid-template-columns:1fr 1fr}}
 `;document.head.appendChild(s);
}

function sumKnown(rows,key,currency){const vals=rows.map(x=>key==='realized'?x.realized:({value:x.opportunity,currency:ccy(x.t)})).filter(x=>x&&x.value!==null&&x.currency===currency);return {sum:vals.reduce((a,x)=>a+x.value,0),count:vals.length}}
function identityNameHtml(t){const nm=name(t),tk=ticker(t);return esc(nm)+(sym(nm)!==tk?' <span style="font-size:10px;color:#7b8a9b">'+esc(tk)+'</span>':'')}
function render(){
 const panel=q('#panel-trades');if(!panel){RT.render_state='WAITING_FOR_PANEL';return;}
 ensureStyle();
 let root=q('#ctTradeOutcomeV26',panel);if(!root){root=document.createElement('section');root.id='ctTradeOutcomeV26';panel.prepend(root)}
 root.removeAttribute('data-ct-trade-review-legacy');root.style.setProperty('display','block','important');
 const hdef=horizonDef(RT.horizon||'now'),rows=buildRows(),krR=sumKnown(rows,'realized','KRW'),krO=sumKnown(rows,'opportunity','KRW');
 const usdR=sumKnown(rows,'realized','USD'),usdO=sumKnown(rows,'opportunity','USD');
 const buyCount=rows.filter(x=>x.trade_side==='BUY').length,sellCount=rows.filter(x=>x.trade_side==='SELL').length;
 const knownR=rows.filter(x=>x.trade_side==='SELL'&&x.realized.value!==null).length,knownO=rows.filter(x=>x.opportunity!==null).length;
 const sumTxt=(kr,usd)=>{const a=[];if(kr.count)a.push(money(kr.sum,'KRW'));if(usd.count)a.push(money(usd.sum,'USD'));return a.length?a.join(' · '):'—'};
 const hbuttons=HORIZONS.map(h=>`<button type="button" class="ctO26HBtn ${h.key===(RT.horizon||'now')?'active':''}" data-horizon-v26="${h.key}" aria-pressed="${h.key===(RT.horizon||'now')?'true':'false'}">${h.label}</button>`).join('');
 const html=`<div class="ctO26Head"><div><div class="ctO26Title">매매복기</div><div class="ctO26Sub">체결 이후 기준시점별 복기 · 매수=(기준가−매수가)×수량 · 매도=(매도가−기준가)×수량 · +는 유리, −는 불리</div></div><div class="ctO26Badge">거래 ${rows.length}건</div></div>
 <div class="ctO26Horizons" role="group" aria-label="체결 후 성과 기준">${hbuttons}</div>
 <div class="ctO26Summary"><div class="ctO26Sum"><span>확인된 실현손익 합계</span><b>${esc(sumTxt(krR,usdR))}</b><small>매도 ${sellCount}건 중 ${knownR}건 원가근거 확인</small></div><div class="ctO26Sum"><span>${esc(hdef.label)} 복기손익 합계</span><b>${esc(sumTxt(krO,usdO))}</b><small>${knownO}/${rows.length}건 · 해당 기준가가 확정된 거래만 반영</small></div></div>
 <div class="ctO26List">${rows.length?rows.map(x=>{const t=x.t,r=x.realized,op=x.opportunity,sd=x.trade_side,b=x.basis||{},label=b.label||hdef.label;let opWord;if(op===null){opWord=b.state==='FUND_UNITS_REQUIRED'?'펀드 기준가·좌수 확인 필요':b.state==='PENDING'?label+' 아직 미도달':b.state==='UNAVAILABLE'?label+' 기준가 없음':'기준가 없음'}else if(sd==='SELL'){opWord=op<0?'기회손실 · 매도 후 상승':op>0?'회피손실 · 매도 후 하락':'변동 없음'}else{opWord=op>0?label+' 기준 수익':op<0?label+' 기준 손실':'변동 없음'}const basisDate=shortBasisDate(b.date),target=shortBasisDate(b.target),basisTxt=x.current!==null?' · '+label+' '+price(x.current,ccy(t))+(basisDate?' ('+basisDate+')':''):(target?' · 목표 '+target:'');const pctTxt=x.performance_pct===null?'':` · ${x.performance_pct>=0?'+':''}${x.performance_pct.toFixed(2)}%`;return `<div class="ctO26Row" data-v26-ticker="${esc(ticker(t))}" data-v26-account="${esc(acct(t))}" data-v26-side="${esc(sd)}" data-v26-horizon="${esc(RT.horizon||'now')}" data-v26-realized="${r.value===null?'NA':'OK'}" data-v26-opportunity="${op===null?'NA':'OK'}"><div class="ctO26Identity"><div class="ctO26Name">${identityNameHtml(t)}</div><div class="ctO26Meta">${esc(acct(t))} · ${esc(sd)} · ${esc(String(ts(t)||t.trade_date||'').replace('T',' ').slice(0,16))} · ${qty(t).toLocaleString()}${fundUnitsUnknown(t)?'원장단위':'주'} × ${esc(price(px(t),ccy(t)))}</div></div><div class="ctO26Metric"><span>실현손익</span><b class="${sd==='SELL'?cls(r.value):'na'}">${sd==='SELL'?esc(money(r.value,r.currency)):'—'}</b><small>${sd==='BUY'?'매수 거래는 미실현':r.value===null?'원가근거 필요':r.basis==='WEIGHTED_AVG_LEDGER'?'가중평균 원가':'원장/브로커'}</small></div><div class="ctO26Metric"><span>${esc(label)} 복기손익</span><b class="${cls(op)}">${esc(money(op,ccy(t)))}</b><small>${esc(opWord)}${basisTxt}${pctTxt}</small></div></div>`}).join(''):'<div class="ctO26Empty">최근 거래가 없습니다.</div>'}</div>`;
 if(root.innerHTML===html)return;root.innerHTML=html;
 root.querySelectorAll('[data-horizon-v26]').forEach(btn=>btn.addEventListener('click',()=>{const key=String(btn.dataset.horizonV26||'now');if(key===(RT.horizon||'now'))return;RT.horizon=key;RT.horizon_label=horizonDef(key).label;render()}));
 RT.state='ACTIVE';RT.render_state='ACTIVE';RT.rendered_at=new Date().toISOString();RT.horizon_label=hdef.label;RT.trade_count=rows.length;RT.buy_count=buyCount;RT.sell_count=sellCount;RT.realized_known=knownR;RT.opportunity_known=knownO;RT.missing_realized=sellCount-knownR;RT.missing_opportunity=rows.length-knownO;
}

function run(){try{render()}catch(e){RT.state='ACTIVE';RT.render_state='ERROR';RT.error=String(e&&e.message||e)}}
setTimeout(run,0);setTimeout(run,900);setTimeout(run,2400);
document.addEventListener('jjooni:live-applied',run);
window.addEventListener('jjooni:security-names-ready',run);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)run()});
window.addEventListener('resize',run,{passive:true});
})();