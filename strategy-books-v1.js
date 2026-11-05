(function(root){
'use strict';
const M=typeof module==='object'&&module.exports?require('./canonical-metrics.js'):root.JjooniMetrics;
const IDS=['TOSS','ISA','PENSION','IRP'];
const NAMES={TOSS:'토스 · 트라이팟',ISA:'ISA · 바이팟',PENSION:'연금저축',IRP:'IRP',TRIPOD:'토스 · 트라이팟 전략'};
const GROUPS={NASDAQ_SYSTEM:'나스닥 시스템',NASDAQ_ACTIVE:'나스닥 액티브 · 별도',OTHER:'기타 운용',UNALLOCATED:'현금·환율·미귀속'};
const owner=id=>id==='TRIPOD'?'TOSS':id;
const n=M.number,first=M.first,sum=xs=>xs.length===0?0:M.sum(xs),sym=s=>String(s||'').trim().toUpperCase().replace(/\.(KS|KQ)$/,'');
function classify(p,account){const ticker=sym(p.ticker||p.symbol),name=String(p.name||p.stock_name||'');if(ticker==='426030'||/나스닥|NASDAQ/i.test(name)&&/액티브|ACTIVE/i.test(name))return 'NASDAQ_ACTIVE';if(account==='TOSS')return ['QQQ','QQQM','QLD','TQQQ'].includes(ticker)?'NASDAQ_SYSTEM':'OTHER';if(account==='ISA'&&!(['133690','368590','418660','409820'].includes(ticker)||/^\d[A-Z0-9]{5}$/.test(ticker)&&/(나스닥|NASDAQ)/i.test(name)&&/레버리지|2X|2배/i.test(name)))return 'OTHER';if(['QQQ','QQQM','QLD','TQQQ','133690','368590','418660','409820'].includes(ticker))return 'NASDAQ_SYSTEM';if(/(?:나스닥\s*100|NASDAQ[ -]?100)/i.test(name)&&!/액티브|ACTIVE|커버드|COVERED|인버스|INVERSE|채권혼합/i.test(name))return 'NASDAQ_SYSTEM';return 'OTHER'}
function leverage(p){const t=sym(p.ticker||p.symbol),name=String(p.name||'');if(/채권혼합\s*50/i.test(name))return .5;if(t==='TQQQ')return 3;if(t==='QLD'||/레버리지|2X|2배/i.test(name))return 2;return 1}
function exposureLabel(x){return n(x)==null?'노출 확인 필요':Number(x.toFixed(2))+'배'}
// A product multiplier is not a strategy name. These are account-specific
// implementations of the same verified market-state signal (user reference photo).
const STATES=['GREEN','YELLOW','RED'];
function signalState(signal){if(!signal?.trusted)return null;const target=String(signal.target||'');return /TQQQ\s*100/.test(target)?'GREEN':/QQQ\s*50.*QLD\s*50|QLD\s*50.*QQQ\s*50/.test(target)?'YELLOW':/현금\s*100|CASH\s*100/i.test(target)?'RED':null}
function accountPolicy(account,state){
 const policies={
  TOSS:{name:'토스 내 해외 TRI-POD',green:[['나스닥100 3배',1,3]],yellow:[['나스닥100 1배',.5,1],['나스닥100 2배',.5,2]]},
  TRIPOD:{name:'해외 TRI-POD',green:[['나스닥100 3배',1,3]],yellow:[['나스닥100 1배',.5,1],['나스닥100 2배',.5,2]]},
  ISA:{name:'ISA 적용형 · 최대 2배',green:[['나스닥100 2배',1,2]],yellow:[['나스닥100 1배',.5,1],['나스닥100 2배',.5,2]]},
  PENSION:{name:'연금저축 적용형 · 최대 1배',green:[['나스닥100 1배',1,1]],yellow:[['나스닥100 1배',1,1]]},
  IRP:{name:'IRP·DC 적용형 · 70/30 구성',green:[['나스닥100 1배',.7,1],['나스닥100 채권혼합50',.3,.5]],yellow:[['나스닥100 1배',.7,1],['나스닥100 채권혼합50',.3,.5]]}
 };const p=policies[account];if(!p)return null;const selected=STATES.includes(state)?state:null,composition=selected?(selected==='RED'?[['파킹',1,0]]:p[selected.toLowerCase()]):[];return {name:p.name,state:selected,composition,target:selected?composition.map(([label,weight])=>label+' '+Math.round(weight*100)+'%').join(' + '):null,exposure:selected?composition.reduce((v,[,weight,multiplier])=>v+weight*multiplier,0):null}
}
function positions(account,a){const rows=[],seen=new Map(),errors=[];for(const p of M.positions(a)){const ticker=sym(p.ticker||p.symbol),key=account+'|'+ticker;if(!ticker){errors.push('종목코드 누락');continue}const q=first(p,['qty','quantity','held_qty']),value=M.valueKrw(p,a),fingerprint=JSON.stringify([q,value,first(p,['avg_price','average_price']),M.currency(p),first(p,['cost_basis_krw','purchase_cost_krw','acquisition_cost_krw']),first(p,['holding_pnl_krw','unrealized_pnl_krw','evaluation_pnl_krw','eval_pnl_krw','pnl_krw'])]);if(seen.has(key)){if(seen.get(key)===fingerprint){errors.push('중복행 제외: '+key);continue}errors.push('충돌 보유행: '+key);const old=rows.find(x=>x.key===key);if(old)old.conflict=true;continue}seen.set(key,fingerprint);rows.push({key,account,ticker,name:p.name||p.stock_name||ticker,qty:q,value,group:classify(p,account),leverage:leverage(p),day:M.positionDay(p,a),raw:p})}return {rows,errors}}
function normalizeTrade(r){const account=String(r.account||'').trim().toUpperCase().replace(/-/g,''),ticker=sym(r.ticker||r.symbol),side=String(r.side||'').toUpperCase(),kind=/SELL|매도|익절/.test(side)?'SELL':/BUY|매수/.test(side)?'BUY':null,qty=n(String(r.qty??r.quantity??'').replace(/,/g,'')),price=n(String(r.price??'').replace(/,/g,''));if(!IDS.includes(account)||!ticker||!kind||!(qty>0))return null;const number=v=>n(typeof v==='string'?v.replace(/,/g,''):v),currency=String(r.currency||'').toUpperCase(),fx=currency==='KRW'?1:number(r.fx),grossDirect=number(r.krw_amount),native=number(r.amount)??(price!=null?price*qty:null),gross=grossDirect>0?grossDirect:fx>0&&native>0?fx*native:null,commission=number(r.commission),tax=number(r.tax),fees=commission===0&&tax===0?0:commission!=null&&tax!=null&&(currency==='KRW'||fx>0)?(commission+tax)*fx:null,at=M.parseMs(r.filled_at_kst||r.trade_date||r.date);return {account,ticker,key:account+'|'+ticker,id:String(r.trade_key||r.broker_trade_id||''),kind,qty,price,gross,fees,at,name:r.name||ticker,currency,group:classify({ticker,name:r.name},account)}}
function ledgerRows(source){const rows=[],seen=new Map(),errors=[];for(const r of source.rows||[]){const t=normalizeTrade(r);if(!t)continue;if(!t.id){errors.push({key:t.key,reason:'체결 식별자 없음'});continue}const key=t.account+'|'+t.id,prior=seen.get(key),fingerprint=JSON.stringify(t);if(prior){if(prior!==fingerprint)errors.push({key:t.key,reason:'동일 체결 ID 충돌'});continue}seen.set(key,fingerprint);rows.push(t)}rows.sort((a,b)=>(a.at??0)-(b.at??0));return {rows,errors,available:source.status==='AVAILABLE'}}
// Recent broker fills and the historical sheet must feed the same cost engine.
// Only broker-authoritative rows with an order ID may supplement the ledger.
function withBrokerTrades(source={},live={}){
 const rows=[...(source.rows||[])],known=new Set(rows.map(r=>String(r.broker_trade_id||r.order_id||r.trade_key||'').replace(/^TOSS\|/,'')));
 const executionKey=t=>JSON.stringify([t.key,t.kind,t.at,t.qty,t.price]);
 const executions=new Set(rows.map(normalizeTrade).filter(Boolean).map(executionKey));
 let added=0;
 for(const r of live.recent_trades||[]){
  const id=String(r.order_id||'').trim();
  if(!['BROKER_DIRECT_TOSS_API','BROKER_DIRECT_TOSS_API_FAST'].includes(r.source)||String(r.account).toUpperCase()!=='TOSS'||!id||known.has(id))continue;
  const t=normalizeTrade({...r,trade_key:id});if(!t||t.at==null)continue;
  // Matching execution facts prevent cross-source duplication when IDs differ.
  const execution=executionKey(t);if(executions.has(execution))continue;
  rows.push({...r,trade_key:id});known.add(id);executions.add(execution);added++;
 }
 const dates=(source.rows||[]).map(r=>String(r.filled_at_kst||r.trade_date||'')).filter(Boolean).sort();
 return {...source,rows,broker_added:added,sheet_latest_at:dates.at(-1)||null};
}
function withConfirmedTradeFx(source={},book={},asOf=null){
 const end=M.parseMs(asOf);
 return {...source,rows:(source.rows||[]).map(r=>{
  const id=String(r.order_id||r.broker_trade_id||r.trade_key||'').replace(/^TOSS\|/,''),pin=book.trade_fx_v1?.['TOSS|'+id];
  if(!pin||String(r.account).toUpperCase()!=='TOSS'||String(r.currency).toUpperCase()!=='USD')return r;
  const confirmed=M.parseMs(pin.confirmed_at),t=normalizeTrade(r);
  if(pin.source!=='USER_AUTHORIZED_CURRENT_SNAPSHOT_FX'||!(n(pin.fx)>0)||confirmed==null||end==null||confirmed>end)return r;
  if(!t||sym(pin.ticker)!==t.ticker||n(pin.qty)!==t.qty||n(pin.price)!==t.price||M.parseMs(pin.filled_at)!==t.at)return {...r,fx:null,krw_amount:null,commission:null};
  return {...r,fx:pin.fx,fx_source:pin.source,fx_confirmed_at:pin.confirmed_at};
 })};
}
function withReceiptKrw(source={},book={},asOf=null){
 const end=M.parseMs(asOf);
 return {...source,rows:(source.rows||[]).map(r=>{
  const id=String(r.order_id||r.broker_trade_id||r.trade_key||'').replace(/^TOSS\|/,''),pin=book.trade_krw_v1?.['TOSS|'+id];
  if(!pin||String(r.account).toUpperCase()!=='TOSS'||String(r.currency).toUpperCase()!=='USD'||n(r.krw_amount)>0)return r;
  const t=normalizeTrade(r),confirmed=M.parseMs(pin.confirmed_at);
  if(pin.source!=='USER_TOSS_ORDER_SCREENSHOT_KRW'||confirmed==null||end==null||confirmed>end)return r;
  if(!t||t.kind!=='BUY'||sym(pin.ticker)!==t.ticker||n(pin.qty)!==t.qty||n(pin.price)!==t.price||M.parseMs(pin.filled_at)!==t.at||!(n(pin.krw_amount)>0))return {...r,fx:null,krw_amount:null};
  // The screenshot supplies displayed KRW principal, not an extra fill or a fee.
  // Preserve missing fees; translate known native fees at the receipt-implied FX.
  return {...r,krw_amount:pin.krw_amount,fx:pin.krw_amount/(t.qty*t.price),krw_source:pin.source};
 })};
}
function costReason(quality){return ({
 OPENING_COST_SOURCE_AHEAD:'최신 계좌 원본 연결 대기',
 OPENING_COST_LEDGER_MISSING:'체결 원장 조회 실패',
 OPENING_COST_TRADE_CONFLICT:'동일 체결 ID 자료 충돌',
 OPENING_COST_TRADE_FX_OR_FEES_MISSING:'추가 체결의 거래 당시 환율·수수료·세금 확인 필요',
 OPENING_COST_QUANTITY_MISMATCH:'기준 수량 + 이후 체결 수량이 현재 보유수량과 다름',
 OPENING_COST_NEW_POSITION_TRADE_MISSING:'신규 보유종목의 매수 체결 누락',
 OPENING_COST_INPUT_MISSING:'고정한 기준원가 자료 확인 필요'
 })[quality]||'과거 원화 원가·증권사 원화손익 누락'}
function flowBook(book){const flows=Object.fromEntries(IDS.map(a=>[a,0])),seen=new Set();for(const e of book.events||[]){if(seen.has(e.id))throw Error('중복 현금흐름 ID');seen.add(e.id);if(e.voided_at)continue;if(!(n(e.amount_krw)>0))throw Error('현금흐름 금액 오류');const v=Number(e.amount_krw);if(e.kind==='TRANSFER'){const from=owner(e.from_account),to=owner(e.to_account);if(!IDS.includes(from)||!IDS.includes(to)||e.from_account===e.to_account)throw Error('내부이체 계좌 오류');flows[from]-=v;flows[to]+=v}else if(['DEPOSIT','WITHDRAWAL'].includes(e.kind)){if(!IDS.includes(owner(e.account)))throw Error('현금흐름 계좌 오류');flows[owner(e.account)]+=e.kind==='DEPOSIT'?v:-v}}return flows}
function dietzBase(base,events,account,start,end){if(!(base>=0&&end>=start))return null;let value=base;for(const e of events){if(e.voided_at)continue;let leg=0;if(e.kind==='TRANSFER')leg=owner(e.to_account)===owner(e.from_account)?0:owner(e.to_account)===account?e.amount_krw:owner(e.from_account)===account?-e.amount_krw:0;else if(owner(e.account)===account&&['DEPOSIT','WITHDRAWAL'].includes(e.kind))leg=e.kind==='DEPOSIT'?e.amount_krw:-e.amount_krw;const at=M.parseMs(e.at);if(leg&&at==null)return null;const weight=end===start?0:Math.max(0,Math.min(1,(end-at)/(end-start)));value+=leg*weight}return value>0?value:null}
function costEvidence(book){const state=book.cost_basis_v1||{},only=o=>Object.fromEntries(Object.entries(o||{}).filter(([,v])=>v.ticker==='TQQQ'));return {opening_at:state.at,policy:state.policy,anchors:Object.fromEntries(Object.entries(state.positions||{}).filter(([k])=>['TOSS|TQQQ','TRIPOD|TQQQ'].includes(k))),fx:only(book.trade_fx_v1),receipts:only(book.trade_krw_v1),transfers:(book.cost_basis_transfers_v1||[]).filter(e=>e.ticker==='TQQQ')}}
function stableJson(v){const sort=x=>x&&typeof x==='object'?Array.isArray(x)?x.map(sort):Object.fromEntries(Object.keys(x).sort().filter(k=>x[k]!==undefined).map(k=>[k,sort(x[k])])):x;return JSON.stringify(sort(v))}
function savedHoldingCost(row,trades,book,asOf){const saved=book.holding_costs_v1?.[row.key],end=M.parseMs(asOf),through=M.parseMs(saved?.through_at);if(!saved||saved.source!=='VERIFIED_ROLLED_KRW_COST'||row.key!=='TOSS|TQQQ'||n(saved.qty)!==row.qty||n(saved.avg_native)!==first(row.raw,['avg_price','average_price'])||n(saved.cost_krw)==null||saved.cost_krw<0||through==null||end==null||through>end)return null;if(stableJson(saved.input_evidence)!==stableJson(costEvidence(book)))return null;if(trades.errors.some(e=>e.key===row.key)||trades.rows.some(t=>t.key===row.key&&(t.at==null||t.at>through&&t.at<=end)))return null;return {cost:saved.cost_krw,quality:'SAVED_VERIFIED_KRW_COST'}}
function openingHoldingCost(row,trades,book,asOf){
 const state=book?.cost_basis_v1;if(state?.policy!=='CURRENT_FX_OPENING_THEN_TRADE_FX'||M.currency(row.raw)!=='USD')return null;
 const cut=M.parseMs(state.at),end=M.parseMs(asOf),anchor=state.positions?.[row.key],fail=quality=>({cost:null,quality});
 if(cut==null||end==null||end<cut)return fail('OPENING_COST_SOURCE_AHEAD');
 if((state.unresolved||[]).some(x=>x.key===row.key))return fail('OPENING_COST_INPUT_MISSING');
 if(anchor&&(n(anchor.qty)==null||anchor.qty<0||n(anchor.cost_krw)==null||anchor.cost_krw<0))return fail('OPENING_COST_INPUT_MISSING');
 if(!trades.available&&end!==cut)return fail('OPENING_COST_LEDGER_MISSING');
 if(trades.errors.some(e=>e.key===row.key))return fail('OPENING_COST_TRADE_CONFLICT');
 let qty=anchor?Number(anchor.qty):0,cost=anchor?Number(anchor.cost_krw):0,used=0;
 const carry=[],seenTransfers=new Set();
 for(const e of book.cost_basis_transfers_v1||[]){
  if(e.to_account!==row.account||sym(e.ticker)!==row.ticker)continue;
  const at=M.parseMs(e.at),source=state.positions?.[e.source_key];
  if(at==null||at<=cut||at>end)continue;
  if(e.source!=='VERIFIED_LEGACY_TRIPOD_COST_CARRY'||e.from_account!=='TRIPOD'||e.to_account!=='TOSS'||e.source_key!=='TRIPOD|'+row.ticker||!source||seenTransfers.has(e.source_key)||n(e.qty)!==n(source.qty)||n(e.cost_krw)!==n(source.cost_krw))return fail('OPENING_COST_INPUT_MISSING');
  seenTransfers.add(e.source_key);carry.push({kind:'BUY',qty:e.qty,gross:e.cost_krw,fees:0,at});
 }
 const inventory=[...trades.rows.filter(t=>t.key===row.key&&(t.at==null||t.at>cut&&t.at<=end)),...carry].sort((a,b)=>(a.at??0)-(b.at??0));
 for(const t of inventory){
  if(t.at==null||t.gross==null||t.fees==null)return fail('OPENING_COST_TRADE_FX_OR_FEES_MISSING');
  if(t.kind==='BUY'){qty+=t.qty;cost+=t.gross+t.fees}else{if(qty+1e-7<t.qty)return fail('OPENING_COST_QUANTITY_MISMATCH');cost-=qty>0?cost/qty*t.qty:0;qty-=t.qty;if(Math.abs(qty)<1e-7){qty=0;cost=0}}used++
 }
 if(row.qty==null||Math.abs(qty-row.qty)>1e-5)return fail('OPENING_COST_QUANTITY_MISMATCH');
 if(!anchor&&!used)return fail('OPENING_COST_NEW_POSITION_TRADE_MISSING');
 return {cost,quality:anchor?used?'OPENING_PLUS_TRADE_FX':'CURRENT_FX_OPENING':'POST_CUTOVER_TRADE_KRW_COST_WITH_FEES'}
}
function holdingCost(row,a,trades,book={},asOf=null){const receipt=brokerCheckpoint(row,trades,book,asOf);if(receipt)return receipt;const brokerCurrent=row.raw.cost_basis_source==='TOSS_OPENAPI_HOLDINGS_KRW'&&n(row.raw.cost_basis_qty)===row.qty;const brokerCost=brokerCurrent?first(row.raw,['cost_basis_krw','purchase_cost_krw','acquisition_cost_krw']):null;if(brokerCost!=null&&brokerCost>=0)return {cost:brokerCost,quality:'KRW_COST_SOURCE'};const brokerAvg=brokerCurrent?first(row.raw,['avg_price_krw']):null;if(brokerAvg!=null&&brokerAvg>=0&&row.qty>0)return {cost:brokerAvg*row.qty,quality:'KRW_COST_SOURCE'};const saved=savedHoldingCost(row,trades,book,asOf);if(saved)return saved;const opening=openingHoldingCost(row,trades,book,asOf);if(opening)return opening;const p=row.raw,explicit=first(p,['cost_basis_krw','purchase_cost_krw','acquisition_cost_krw']);if(explicit!=null&&explicit>=0)return {cost:explicit,quality:'KRW_COST_SOURCE'};let qty=0,cost=0,broken=trades.errors.some(e=>e.key===row.key),used=0;for(const t of trades.rows.filter(t=>t.key===row.key)){if(t.at==null||t.gross==null||t.fees==null){broken=true;continue}if(t.kind==='BUY'){qty+=t.qty;cost+=t.gross+t.fees;used++}else if(qty+1e-7>=t.qty){cost-=qty>0?cost/qty*t.qty:0;qty-=t.qty}else broken=true}if(trades.available&&used&&!broken&&row.qty!=null&&Math.abs(qty-row.qty)<1e-5)return {cost,quality:'TRADE_ROW_KRW_COST_WITH_FEES'};const brokerPnl=first(p,['holding_pnl_krw','unrealized_pnl_krw','evaluation_pnl_krw','eval_pnl_krw','pnl_krw']);if(brokerPnl!=null&&row.value!=null&&row.value-brokerPnl>0)return {cost:row.value-brokerPnl,quality:'BROKER_KRW_PNL_IMPLIED_COST'};if(M.currency(p)==='KRW'){const q=row.qty,av=first(p,['avg_price','average_price']);if(q>0&&av!=null)return {cost:q*av,quality:'HOLDING_AVG_BEFORE_COSTS'};if(String(p.record_type).toUpperCase()==='FUND'&&av!=null)return {cost:av,quality:'FUND_REFERENCE_COST'}}return {cost:null,quality:'HISTORICAL_KRW_COST_MISSING'}}
function signalAction(group,trustedSignal,account){
 if(group.group!=='NASDAQ_SYSTEM')return {action:group.group==='NASDAQ_ACTIVE'?'별도 운용':'개별 운용',target:null};
 const policy=accountPolicy(account,signalState(trustedSignal));
 if(!policy?.state)return {...policy,action:'신호 검증 대기'};
 if(!group.positions.length)return {...policy,action:'전략 대상 보유 없음 · 편입 확인 필요'};
 return {...policy,action:trustedSignal.action==='HOLD_NO_TRADE'?'신호 유지 · 추가 매매 없음':'계좌별 목표 구성 확인 · 수동 판단'}
}
// The user's confirmed opening/FX anchor must never change when positions rotate.
function assertImmutableStrategyAnchor(previous,next){
 if(!previous?.baseline?.at||!previous?.cost_basis_v1?.at)return true;
 const fields=[['baseline.at',previous.baseline?.at,next?.baseline?.at],['baseline.snapshot_id',previous.baseline?.snapshot_id,next?.baseline?.snapshot_id],['cost_basis_v1.at',previous.cost_basis_v1?.at,next?.cost_basis_v1?.at],['cost_basis_v1.snapshot_id',previous.cost_basis_v1?.snapshot_id,next?.cost_basis_v1?.snapshot_id],['cost_basis_v1.policy',previous.cost_basis_v1?.policy,next?.cost_basis_v1?.policy]];
 for(const [field,before,after] of fields)if(before!=null&&before!==after)throw Error('STRATEGY_P0_ANCHOR_REBASE_BLOCKED: '+field);
 // A same-timestamp payload can still silently rewrite KRW opening principal.
 // Existing opening lots and the original account baseline are append-never evidence.
 if(previous.baseline?.accounts&&stableJson(previous.baseline.accounts)!==stableJson(next?.baseline?.accounts))throw Error('STRATEGY_P0_ANCHOR_REBASE_BLOCKED: baseline.accounts');
 for(const [key,opening] of Object.entries(previous.cost_basis_v1?.positions||{})){
  if(stableJson(opening)!==stableJson(next?.cost_basis_v1?.positions?.[key]))throw Error('STRATEGY_P0_ANCHOR_REBASE_BLOCKED: cost_basis_v1.positions.'+key);
 }
 return true;
}
function brokerCheckpoint(row,trades,book={},asOf){
 const p=book.broker_holding_costs_v1?.[row.key],end=M.parseMs(asOf),cut=M.parseMs(p?.confirmed_at);
 if(p?.source!=='OWNER_PROVIDED_BROKER_RECEIPT'||end==null||cut==null||end<cut||!(n(p.qty)>0)||!(n(p.cost_krw)>0))return null;
 const later=trades.rows.filter(t=>t.key===row.key&&(t.at==null||t.at>cut&&t.at<=end));
 if(trades.errors.some(t=>t.key===row.key)||later.some(t=>t.at==null))return null;
 let qty=n(p.qty),cost=n(p.cost_krw);const sales=[];
 for(const t of later){
  if(t.gross==null||t.fees==null||!trades.available)return null;
  if(t.kind==='BUY'){qty+=t.qty;cost+=t.gross+t.fees}
  else{if(t.qty>qty+1e-6)return null;const soldCost=cost/qty*t.qty;sales.push({account:row.account,ticker:row.ticker,qty:t.qty,date:new Date(t.at+9*3600000).toISOString().slice(0,10),trade_id:t.id,pnl:t.gross-soldCost-t.fees,quality:'RECEIPT_ROLLED_TRADE'});qty-=t.qty;cost-=soldCost}
 }
 if(Math.abs(qty-row.qty)>1e-5)return null;
 if(!later.length&&n(p.avg_native)!=null&&n(p.avg_native)!==first(row.raw,['avg_price','average_price']))return null;
 return {cost,quality:'BROKER_RECEIPT_KRW_COST',sales};
}
function preferBrokerRealized(book,view,account,estimate={},source=null){
 const end=M.parseMs(view.as_of),confirmed=Object.values(book.broker_realized_sales_v1||{}).filter(p=>p.source==='OWNER_PROVIDED_BROKER_RECEIPT'&&p.kind==='REALIZED_SALE'&&p.account===account&&M.parseMs(p.confirmed_at)<=end&&n(p.net_pnl_krw)!=null).map(p=>({account:p.account,ticker:p.ticker,qty:p.qty,date:p.trade_date,pnl:p.net_pnl_krw,trade_id:p.trade_id,quality:'BROKER_RECEIPT_NET'}));
 const rolled=[];if(source){const trades=ledgerRows(withReceiptKrw(withConfirmedTradeFx(source,book,view.as_of),book,view.as_of)),a=view.accounts?.find(a=>a.id===account);for(const [key,p]of Object.entries(book.broker_holding_costs_v1||{})){if(p.account!==account||!a?.sourceComplete)continue;const holding=a.groups?.flatMap(g=>g.positions||[]).find(x=>x.key===key)||{key,account,ticker:p.ticker,qty:0,raw:{}};const result=brokerCheckpoint(holding,trades,book,view.as_of);if(result)rolled.push(...result.sales)}}
 if(!confirmed.length&&!rolled.length)return estimate;
 const same=(a,b)=>a.trade_id&&b.trade_id&&a.trade_id===b.trade_id||a.ticker===b.ticker&&a.date===b.date&&Math.abs(a.qty-b.qty)<1e-6;
 const calculated=rolled.filter(p=>!confirmed.some(c=>same(c,p)));
 const remaining=estimate.status==='AVAILABLE'?(estimate.sales||[]).filter(p=>![...confirmed,...calculated].some(c=>same(c,p))):[];
 const sales=[...confirmed,...calculated,...remaining];return {status:'AVAILABLE',pnl:sum(sales.map(p=>p.pnl)),sales,confirmed:remaining.length===0&&calculated.length===0,confirmedCount:confirmed.length,basis:'BROKER_RECEIPTS_PREFERRED',scope:'CONFIRMED_SALES_AND_AVAILABLE_ESTIMATES',complete:estimate.complete===true};
}
function requireRestoredStrategyBook(book){
 if(!book?.baseline?.at||!book?.cost_basis_v1?.at||!book?.cost_basis_v1?.policy)throw Error('STRATEGY_P0_SOURCE_MISSING: 기존 확정 원장 복원 실패 · 자동 초기화 금지');
 return book;
}

// Strategy performance survives product rotation. Original opening cost is a
// fixed denominator; remaining inventory cost is never substituted for it.
function strategyCapital(book,account,asOf=null,master=null,view=null){
 const end=M.parseMs(asOf),openingAt=M.parseMs(book.cost_basis_v1?.at);if(end!=null&&openingAt!=null&&end<openingAt)return {value:null,at:book.cost_basis_v1.at,basis:"FUTURE_OPENING_BLOCKED"};
 const pinned=book.strategy_capital_v1?.[account];
 if(pinned?.source==='OWNER_CONFIRMED_STRATEGY_CAPITAL'&&n(pinned.principal_krw)>0){
  const adjustment=(book.strategy_capital_adjustments_v1||[]).find(e=>e.id===pinned.last_adjustment_id);
  const effective=adjustment?.effective_date_kst?M.parseMs(adjustment.effective_date_kst+'T00:00:00+09:00'):null;
  if(end!=null&&effective!=null&&end<effective&&n(adjustment.prior_displayed_principal_krw)>0)return {value:n(adjustment.prior_displayed_principal_krw),at:pinned.at,basis:'OWNER_CONFIRMED_PRIOR_CAPITAL'};
  return {value:n(pinned.principal_krw),at:pinned.at,basis:'OWNER_CONFIRMED_STRATEGY_CAPITAL'};
 }
 const recorded=(book.events||[]).filter(e=>!e.voided_at&&e.kind==='STRATEGY_OPENING'&&owner(e.account)===account&&e.strategy==='NASDAQ_SYSTEM'&&n(e.amount_krw)>0&&M.parseMs(e.at)!=null&&(end==null||M.parseMs(e.at)<=end));
 if(recorded.length===1)return {value:n(recorded[0].amount_krw),at:recorded[0].at,basis:'OWNER_CONFIRMED_STRATEGY_OPENING'};
 if(recorded.length>1)return {value:null,at:null,basis:'CONFLICTING_STRATEGY_OPENINGS'};
 const opening=book.cost_basis_v1||{},lots=Object.entries(opening.positions||{}).filter(([key,p])=>key.startsWith(account+'|')&&classify(p,account)==='NASDAQ_SYSTEM');
 if(account==='TOSS')for(const e of book.cost_basis_transfers_v1||[]){const p=opening.positions?.[e.source_key];if(e.source==='VERIFIED_LEGACY_TRIPOD_COST_CARRY'&&e.from_account==='TRIPOD'&&e.to_account==='TOSS'&&p&&n(e.qty)===n(p.qty)&&n(e.cost_krw)===n(p.cost_krw)&&!lots.some(([key])=>key===e.source_key))lots.push([e.source_key,p])}
 if(lots.length){const value=sum(lots.map(([,p])=>n(p.cost_krw)));return {value:value>0?value:null,at:opening.at,basis:'IMMUTABLE_OPENING_KRW_COST'}}
 const ps=(book.baseline?.accounts?.[account]?.positions||[]).filter(p=>classify(p,account)==='NASDAQ_SYSTEM');
 const value=sum(ps.map(p=>M.currency(p)==='KRW'?first(p,['cost_basis_krw','purchase_cost_krw'])??(first(p,['qty','quantity'])*first(p,['avg_price','average_price'])):null));
 // Freeze a derived strategy denominator at its first recorded reallocation.
 // The prior baseline remains auditable; a voided event still preserves this checkpoint.
 if(!ps.length){
  const checkpoints=(book.events||[]).filter(e=>['STRATEGY_ALLOCATION_IN','STRATEGY_ALLOCATION_OUT'].includes(e.kind)&&owner(e.account)===account&&e.strategy==='NASDAQ_SYSTEM'&&M.parseMs(e.at)!=null&&(end==null||M.parseMs(e.at)<=end)).sort((a,b)=>M.parseMs(a.at)-M.parseMs(b.at));
  const firstCheckpoint=checkpoints[0],match=String(firstCheckpoint?.note||'').match(/^\[기준원금:(\d+(?:\.\d+)?)\]/);
  if(match&&Number(match[1])>0)return {value:Number(match[1]),at:new Date(M.parseMs(firstCheckpoint.at)-1).toISOString(),basis:'OWNER_CONFIRMED_PRE_ALLOCATION_CHECKPOINT'};
 }
 if(!ps.length&&master?.status==='AVAILABLE'&&view){
  const current=view.accounts.find(a=>a.id===account)?.groups.find(g=>g.group==='NASDAQ_SYSTEM')?.positions||[],ts=ledgerRows(master),rows=ts.rows.filter(t=>t.account===account&&t.group==='NASDAQ_SYSTEM'&&t.at!=null&&(end==null||t.at<=end));
  const firstSale=rows.find(t=>t.kind==='SELL')?.at??Infinity,firstAllocation=rows.filter(t=>t.kind==='BUY'&&t.at<firstSale),tickers=new Set([...rows.map(t=>t.ticker),...current.map(p=>p.ticker)]);
  if(rows.length&&firstAllocation.length&&!ts.errors.some(e=>e.key.startsWith(account+'|'))&&rows.every(t=>t.gross>0)&&[...tickers].every(ticker=>Math.abs(rows.filter(t=>t.ticker===ticker).reduce((n,t)=>n+(t.kind==='BUY'?t.qty:-t.qty),0)-(current.find(p=>p.ticker===ticker)?.qty||0))<1e-5))return {value:sum(firstAllocation.map(t=>t.gross)),at:new Date(firstAllocation[0].at).toISOString(),basis:'RECONCILED_FIRST_STRATEGY_ALLOCATION_BEFORE_FEES'};
 }
 return {value:ps.length&&value>0?value:null,at:book.baseline?.at,basis:'ORIGINAL_BASELINE_KRW_COST'};
}
function strategyRealized(book,source,view,account,fallback){
 if(account!=='TOSS')return fallback;
 const end=M.parseMs(view.as_of),cut=M.parseMs(book.cost_basis_v1?.at),a=view.accounts.find(a=>a.id===account);
 if(!a?.sourceComplete||end==null||cut==null||end<cut||source.status!=='AVAILABLE')return {...fallback,complete:false};
 const ts=ledgerRows(withReceiptKrw(withConfirmedTradeFx(source,book,view.as_of),book,view.as_of)),inventory=new Map(),sales=[];
 if(ts.errors.some(e=>e.key.startsWith(account+'|')))return {...fallback,complete:false};
 for(const [key,p] of Object.entries(book.cost_basis_v1.positions||{})){
  if(!(key.startsWith(account+'|')||account==='TOSS'&&(book.cost_basis_transfers_v1||[]).some(e=>e.source_key===key&&e.source==='VERIFIED_LEGACY_TRIPOD_COST_CARRY'&&n(e.qty)===n(p.qty)&&n(e.cost_krw)===n(p.cost_krw))))continue;
  if(classify(p,account)!=='NASDAQ_SYSTEM')continue;
  const ticker=sym(p.ticker),old=inventory.get(ticker)||{qty:0,cost:0};
  if(n(p.qty)==null||n(p.cost_krw)==null)return {...fallback,complete:false};
  inventory.set(ticker,{qty:old.qty+n(p.qty),cost:old.cost+n(p.cost_krw)});
 }
 for(const p of book.baseline?.accounts?.[account]?.positions||[]){const ticker=sym(p.ticker||p.symbol);if(inventory.has(ticker)||classify(p,account)!=='NASDAQ_SYSTEM'||M.currency(p)!=='KRW')continue;const qty=first(p,['qty','quantity']),cost=first(p,['cost_basis_krw','purchase_cost_krw'])??(qty*first(p,['avg_price','average_price']));if(qty>0&&cost>=0)inventory.set(ticker,{qty,cost})}
 const confirmed=fallback?.sales?.filter(p=>p.quality==='BROKER_RECEIPT_NET')||[];
 for(const t of ts.rows.filter(t=>t.account===account&&t.group==='NASDAQ_SYSTEM'&&(t.at==null||t.at>cut&&t.at<=end))){
  if(t.at==null)return {...fallback,complete:false};const lot=inventory.get(t.ticker)||{qty:0,cost:0};
  if(t.kind==='BUY'){if(t.gross==null||t.fees==null)return {...fallback,complete:false};lot.qty+=t.qty;lot.cost+=t.gross+t.fees}
  else {if(t.qty>lot.qty+1e-5)return {...fallback,complete:false};const matched=confirmed.find(p=>p.trade_id===t.id||p.ticker===t.ticker&&p.date===new Date(t.at+9*3600000).toISOString().slice(0,10)&&Math.abs(p.qty-t.qty)<1e-5);if(!matched&&(t.gross==null||t.fees==null))return {...fallback,complete:false};const cost=lot.cost/lot.qty*t.qty;sales.push(matched||{account,ticker:t.ticker,qty:t.qty,date:new Date(t.at+9*3600000).toISOString().slice(0,10),trade_id:t.id,pnl:t.gross-t.fees-cost,quality:'OPENING_ROLLED_NET'});lot.qty-=t.qty;lot.cost-=cost;if(Math.abs(lot.qty)<1e-5){lot.qty=0;lot.cost=0}}
  inventory.set(t.ticker,lot);
 }
 const ps=a.groups.find(g=>g.group==='NASDAQ_SYSTEM').positions;
 for(const ticker of new Set([...inventory.keys(),...ps.map(p=>p.ticker)]))if(Math.abs((inventory.get(ticker)?.qty||0)-(ps.find(p=>p.ticker===ticker)?.qty||0))>1e-5)return {...fallback,complete:false};
 if(confirmed.some(c=>!sales.includes(c)))return {...fallback,complete:false};
 return {status:'AVAILABLE',pnl:sum(sales.map(p=>p.pnl)),sales,complete:true,confirmed:sales.every(p=>p.quality==='BROKER_RECEIPT_NET'),basis:'OPENING_ROLLED_AND_BROKER_NET_RECEIPTS'};
}
function applyStrategyPerformance(overview,book,view,source,master=null){
 for(const row of overview.accounts){
  const capital=strategyCapital(book,row.id,view.as_of,master,view);row.initialCapital=capital.value;row.capitalAt=capital.at;row.capitalBasis=capital.basis;
  row.capitalFlow=0;for(const e of book.events||[]){const at=M.parseMs(e.at);if(e.voided_at||e.strategy!=='NASDAQ_SYSTEM'||at==null||at<=M.parseMs(capital.at)||at>M.parseMs(view.as_of))continue;const amount=n(e.amount_krw);if(!(amount>0))continue;if(e.kind==='TRANSFER'){if(owner(e.to_account)===row.id)row.capitalFlow+=amount;if(owner(e.from_account)===row.id)row.capitalFlow-=amount}else if(owner(e.account)===row.id&&['DEPOSIT','WITHDRAWAL','STRATEGY_ALLOCATION_IN','STRATEGY_ALLOCATION_OUT'].includes(e.kind))row.capitalFlow+=((e.kind==='DEPOSIT'||e.kind==='STRATEGY_ALLOCATION_IN')?1:-1)*amount}
  row.capital=capital.value!=null?capital.value+row.capitalFlow:null;
  row.masterRealized=strategyRealized(book,source,view,row.id,row.masterRealized);
  const r=row.masterRealized,realized=r?.status==='AVAILABLE'&&n(r.pnl)!=null?r.pnl:row.periodParticipated?null:0;
  // No history is fabricated during the deferred ledger read.
  row.strategyIncome=sum((book.events||[]).filter(e=>!e.voided_at&&e.kind==='DIVIDEND'&&owner(e.account)===row.id&&e.strategy==='NASDAQ_SYSTEM'&&M.parseMs(e.at)>M.parseMs(capital.at)&&M.parseMs(e.at)<=M.parseMs(view.as_of)).map(e=>n(e.amount_krw)));
  row.cumulativePnl=row.holdingPnl!=null&&realized!=null?row.holdingPnl+realized+row.strategyIncome:null;
  row.cumulativeComplete=r?.complete===true;
  row.cumulativeReturn=row.cumulativeComplete&&row.cumulativePnl!=null&&row.capital>0?100*row.cumulativePnl/row.capital:null;
  row.dayBase=row.value!=null&&row.day!=null?row.value-row.day:null;
  row.dayReturn=row.day!=null&&row.dayBase>0?100*row.day/row.dayBase:null;
 }
 const active=overview.accounts.filter(a=>a.count||a.capital>0||a.masterRealized?.sales?.length);
 const total=overview.total;total.capital=sum(active.map(a=>a.capital));total.cumulativePnl=active.length?sum(active.map(a=>a.cumulativePnl)):null;
 total.cumulativeReturn=active.every(a=>a.cumulativeComplete)&&total.cumulativePnl!=null&&total.capital>0?100*total.cumulativePnl/total.capital:null;
 total.dayBase=sum(overview.accounts.map(a=>a.dayBase));total.dayReturn=total.day!=null&&total.dayBase>0?100*total.day/total.dayBase:null;
 return overview;
}

function strategySummary(view){
 const accounts=view.accounts.map(a=>{const g=a.groups.find(x=>x.group==='NASDAQ_SYSTEM'),ps=g.positions,covered=ps.filter(p=>!p.conflict&&p.cost!=null&&p.value!=null&&p.cost>=0),missing=ps.filter(p=>!covered.includes(p)),holdingPnl=sum(ps.map(p=>p.holdingPnl)),cost=sum(ps.map(p=>p.cost)),holdingReturn=holdingPnl!=null&&cost>0?100*holdingPnl/cost:null;return {id:a.id,label:a.label,holdings:ps.map(p=>({ticker:p.ticker,name:p.name,qty:p.qty,value:p.value})),available:a.sourceComplete,value:a.sourceComplete?g.value:null,cost:a.sourceComplete?cost:null,holdingPnl:a.sourceComplete?holdingPnl:null,holdingReturn:a.sourceComplete?holdingReturn:null,day:a.sourceComplete?g.day:null,count:ps.length,coveredCount:covered.length,missing:!a.sourceComplete?[{account:a.id,ticker:'계좌 전체',reason:'계좌 보유 원본 누락'}]:missing.map(p=>({account:a.id,ticker:p.ticker,reason:p.conflict?'중복 보유행 충돌':p.value==null?'원화 평가액 누락':costReason(p.costQuality)})),coveredCost:sum(covered.map(p=>p.cost)),coveredPnl:sum(covered.map(p=>p.holdingPnl)),costQuality:ps.length&&ps.every(p=>['KRW_COST_SOURCE','TRADE_ROW_KRW_COST_WITH_FEES','POST_CUTOVER_TRADE_KRW_COST_WITH_FEES','SAVED_VERIFIED_KRW_COST','BROKER_RECEIPT_KRW_COST'].includes(p.costQuality))?'ACTUAL_COST':'SOURCE_OR_BEFORE_COSTS',periodParticipated:ps.length>0||g.intervalBase>0,periodPnl:a.sourceComplete&&g.intervalVerified?g.intervalPnl:null,periodReason:!a.sourceComplete?'계좌 보유 원본 누락':!view.baseline_at?'추적 시작 자료 대기':!g.quantityReconciled?'체결·보유수량 대사 필요':view.ledgerStatus!=='AVAILABLE'?'체결 원장 연결 대기':!a.reconciled?'계좌 가치 대사 필요':!view.reviewed?'입출금 확인 후 확정':g.intervalPnl==null?'원화 체결대금·비용 확인 필요':null,action:g.action}}
 );const participating=accounts.filter(a=>a.periodParticipated),total={available:accounts.every(a=>a.available),availableCount:accounts.filter(a=>a.available).length,value:sum(accounts.map(a=>a.value)),cost:sum(accounts.map(a=>a.cost)),holdingPnl:sum(accounts.map(a=>a.holdingPnl)),day:sum(accounts.map(a=>a.day)),count:accounts.reduce((v,a)=>v+a.count,0),coveredCount:accounts.reduce((v,a)=>v+a.coveredCount,0),coveredCost:sum(accounts.map(a=>a.coveredCost)),coveredPnl:sum(accounts.map(a=>a.coveredPnl)),missing:accounts.flatMap(a=>a.missing),periodPnl:participating.length?sum(participating.map(a=>a.periodPnl)):null};if(!total.available)total.periodPnl=null;total.holdingReturn=total.holdingPnl!=null&&total.cost>0?100*total.holdingPnl/total.cost:null;total.coveredReturn=total.coveredCost>0?100*total.coveredPnl/total.coveredCost:null;return {accounts,total,baseline_at:view.baseline_at,as_of:view.as_of,method:'HOLDING_KRW_COST_WEIGHTED_AND_VERIFIED_PERIOD_PNL'}
}
// User-entered Master weekly trades are separate from the broker DB_TRADES.
// Compute a clearly provisional realized result from complete matched gross
// buys/sells, never quietly substitute today's holdings return for strategy P&L.
function estimateMasterRealized(source={},view={}){
 const empty=()=>({status:'UNAVAILABLE',pnl:null,sales:[],unmatched:[],basis:'MASTER_GROSS_WAVG_FEES_UNVERIFIED'});
 const accounts=Object.fromEntries(IDS.map(a=>[a,{...empty(),coveredTickers:[]} ]));
 const start=M.parseMs(view.baseline_at),end=M.parseMs(view.as_of);
 if(source?.status!=='AVAILABLE'||!Array.isArray(source.rows)||start==null||end==null||end<start)return {status:'UNAVAILABLE',accounts};
 const byKey=new Map(),seen=new Map();
 for(let i=0;i<source.rows.length;i++){
  const r=source.rows[i],t=normalizeTrade(r);
  if(!t||t.at==null||t.at>end||!['ISA','PENSION','IRP'].includes(t.account)||t.group!=='NASDAQ_SYSTEM')continue;
  const key=t.key,id=String(r.trade_key||'').trim();
  if(!id){const row=byKey.get(key)||{rows:[],errors:[]};row.errors.push('MASTER_TRADE_KEY_MISSING');byKey.set(key,row);continue}
  const fingerprint=JSON.stringify([key,t.kind,t.at,t.qty,t.gross]);
  if(seen.has(id)){if(seen.get(id)!==fingerprint){const row=byKey.get(key)||{rows:[],errors:[]};row.errors.push('MASTER_TRADE_ID_CONFLICT');byKey.set(key,row)}continue}
  seen.set(id,fingerprint);
  const row=byKey.get(key)||{rows:[],errors:[]};row.rows.push({...t,sourceIndex:i,tradeDate:String(r.trade_date||r.date||'').slice(0,10)});byKey.set(key,row)
 }
 for(const [key,record] of byKey){
  const aid=key.split('|')[0],ticker=key.split('|')[1],result=accounts[aid];
  if(!result)continue;
  let qty=0,cost=0,invalid=record.errors.length>0;
  const sales=[];
  for(const t of record.rows.sort((a,b)=>a.at-b.at||a.sourceIndex-b.sourceIndex)){
   if(!(t.qty>0&&t.gross>0)){invalid=true;break}
   if(t.kind==='BUY'){qty+=t.qty;cost+=t.gross}
   else{
    if(qty+1e-7<t.qty){invalid=true;break}
    const soldCost=cost/qty*t.qty;
    const pnl=t.gross-soldCost;
    if(t.at>start)sales.push({account:aid,ticker,date:t.tradeDate,qty:t.qty,proceeds:t.gross,cost:soldCost,pnl,quality:'MASTER_GROSS_BEFORE_FEES'});
    qty-=t.qty;cost-=soldCost;
    if(Math.abs(qty)<1e-7){qty=0;cost=0}
   }
  }
  const liveAccount=view.accounts?.find(a=>a.id===aid);
  const current=liveAccount?.groups?.flatMap(g=>g.positions||[]).filter(p=>p.ticker===ticker)||[];
  const actualQty=current.length===0?0:current.length===1?current[0].qty:null;
  if(!liveAccount?.sourceComplete||actualQty==null||Math.abs(qty-actualQty)>1e-5)invalid=true;
  if(invalid){
   result.unmatched.push({ticker,reason:record.errors[0]||'MASTER_BROKER_POSITION_OR_TRADE_RECONCILIATION_NEEDED'});
  }else {result.sales.push(...sales);result.coveredTickers.push(ticker)}
 }
 for(const aid of IDS){
  const result=accounts[aid];
  if(result.unmatched.length){result.status='PARTIAL';result.pnl=null;continue}
  const live=view.accounts?.find(a=>a.id===aid),current=live?.groups?.find(g=>g.group==='NASDAQ_SYSTEM')?.positions||[];result.complete=source.status==='AVAILABLE'&&!!live?.sourceComplete&&current.every(p=>result.coveredTickers.includes(p.ticker)||!byKey.has(aid+'|'+p.ticker)&&(view.accounts?.find(a=>a.id===aid)?.groups?.find(g=>g.group==='NASDAQ_SYSTEM')?.quantityReconciled===true));result.status='AVAILABLE';result.pnl=result.sales.length||result.complete?sum(result.sales.map(s=>s.pnl)):null;
 }
 return {status:'AVAILABLE',accounts,source:source.source,read_at:source.read_at,source_fingerprint:source.source_fingerprint,fees_verified:false}
}
// Keep a verified pre-sale checkpoint when a broker-confirmed full exit occurs.
// This is a sale-level estimate, not a strategy lifetime return or new P0.
function estimateTossExit(book={},source={},view={}){
 const out={status:'UNAVAILABLE',pnl:null,sales:[],unmatched:[],basis:'BROKER_TQQQ_EXIT_COST_CHECKPOINT'};
 const saved=book.holding_costs_v1?.['TOSS|TQQQ'],through=M.parseMs(saved?.through_at),end=M.parseMs(view.as_of);
 if(saved?.source!=='VERIFIED_ROLLED_KRW_COST'||!(n(saved.qty)>0)||!(n(saved.cost_krw)>0)||through==null||end==null||end<through||!saved.input_evidence)return out;
 const before=saved.input_evidence,now=costEvidence(book);
 if(before.opening_at!==now.opening_at||before.policy!==now.policy||stableJson(before.anchors)!==stableJson(now.anchors)||stableJson(before.transfers)!==stableJson(now.transfers))return out;
 for(const key of ['fx','receipts'])for(const [id,value] of Object.entries(before[key]||{}))if(stableJson(value)!==stableJson(now[key]?.[id]))return out;
 const sourceRows=source.rows||[];
 const normalized=ledgerRows(withReceiptKrw(withConfirmedTradeFx(source,book,view.as_of),book,view.as_of));
 if(normalized.errors.some(e=>e.key==='TOSS|TQQQ'))return out;
 const rows=normalized.rows.filter(t=>t.key==='TOSS|TQQQ'&&(t.at==null||t.at>through&&t.at<=end));
 if(rows.length!==1)return out;
 const t=rows[0],raw=sourceRows.find(r=>String(r.order_id||r.broker_trade_id||r.trade_key||'').replace(/^TOSS\|/,'')===t.id.replace(/^TOSS\|/,''));
 const acct=view.accounts?.find(a=>a.id==='TOSS');
 const holdings=acct?.groups?.flatMap(g=>g.positions||[]).filter(p=>p.ticker==='TQQQ')||[];
 if(!acct?.sourceComplete||holdings.length||!raw||!['BROKER_DIRECT_TOSS_API','BROKER_DIRECT_TOSS_API_FAST'].includes(raw.source)||t.kind!=='SELL'||Math.abs(t.qty-n(saved.qty))>1e-5||!(t.gross>0))return out;
 const pnl=t.gross-n(saved.cost_krw);out.status='AVAILABLE';out.pnl=pnl;out.sales=[{account:'TOSS',ticker:'TQQQ',qty:t.qty,proceeds:t.gross,cost:n(saved.cost_krw),pnl,date:String(raw.filled_at_kst||raw.trade_date||'').slice(0,10),quality:'BROKER_EXIT_PINNED_FX_BEFORE_FEES'}];return out;
}
function build(C,book={},source={},trustedSignal=null){const accountRows=[],errors=[],baseline=book.baseline,baseMs=M.parseMs(baseline?.at),asOf=M.parseMs(C.generated_kst||C.observed_at),trades=ledgerRows(withReceiptKrw(withConfirmedTradeFx(source,book,C.generated_kst||C.observed_at),book,C.generated_kst||C.observed_at)),flows=flowBook(book),reviewed=!!baseline&&book.reviewed_snapshot_id===C.snapshot_id&&asOf>=baseMs&&!(book.events||[]).some(e=>!e.voided_at&&M.parseMs(e.at)>asOf);trades.rows=trades.rows.filter(t=>t.at==null||asOf==null||t.at<=asOf);for(const id of IDS){const a=C.accounts?.[id]||{},baseA=baseline?.accounts?.[id]||{},cur=positions(id,a),base=positions(id,baseA),nav=n(a.nav),groups=Object.values(GROUPS).map((label,i)=>({group:Object.keys(GROUPS)[i],label,positions:[],value:0,day:0,holdingPnl:0,intervalPnl:null}));errors.push(...cur.errors);for(const r of cur.rows){const g=groups.find(g=>g.group===r.group),basis=holdingCost(r,a,trades,book,C.generated_kst||C.observed_at);r.cost=r.conflict?null:basis.cost;r.costQuality=basis.quality;r.holdingPnl=!r.conflict&&r.value!=null&&r.cost!=null?r.value-r.cost:null;g.positions.push(r)}for(const g of groups.filter(g=>g.group!=='UNALLOCATED')){g.value=sum(g.positions.map(p=>p.conflict?null:p.value));g.day=sum(g.positions.map(p=>p.day));g.holdingPnl=sum(g.positions.map(p=>p.holdingPnl));const costs=sum(g.positions.map(p=>p.cost));g.cost=costs;g.holdingReturn=g.holdingPnl!=null&&costs>0?100*g.holdingPnl/costs:null;g.exposure=g.value>0?sum(g.positions.map(p=>p.value*p.leverage))/g.value:g.value===0?0:null;g.actualHoldingCost=g.positions.length>0&&g.positions.every(p=>['KRW_COST_SOURCE','TRADE_ROW_KRW_COST_WITH_FEES','POST_CUTOVER_TRADE_KRW_COST_WITH_FEES','SAVED_VERIFIED_KRW_COST','BROKER_RECEIPT_KRW_COST'].includes(p.costQuality));const bpos=base.rows.filter(p=>p.group===g.group),periodTrades=trades.rows.filter(t=>t.account===id&&t.at>baseMs&&t.at<=asOf&&(cur.rows.find(p=>p.ticker===t.ticker)?.group||base.rows.find(p=>p.ticker===t.ticker)?.group||t.group)===g.group),tickers=new Set([...g.positions,...bpos,...periodTrades].map(p=>p.ticker));let quantityOk=true;for(const ticker of tickers){const start=bpos.find(p=>p.ticker===ticker)?.qty||0,end=g.positions.find(p=>p.ticker===ticker)?.qty||0,delta=periodTrades.filter(t=>t.ticker===ticker).reduce((s,t)=>s+(t.kind==='BUY'?t.qty:-t.qty),0);if(Math.abs(start+delta-end)>1e-5)quantityOk=false}const tradeCash=sum(periodTrades.map(t=>t.gross==null||t.fees==null?null:t.kind==='BUY'?-t.gross-t.fees:t.gross-t.fees)),baseValue=sum(bpos.map(p=>p.value)),income=(book.events||[]).filter(e=>!e.voided_at&&owner(e.account)===id&&e.strategy===g.group&&['DIVIDEND','FEE','TAX'].includes(e.kind)&&M.parseMs(e.at)<=asOf).reduce((s,e)=>s+e.amount_krw*(e.kind==='DIVIDEND'?1:-1),0),ledgerError=trades.errors.some(e=>e.key.startsWith(id+'|'));
if(baseline&&trades.available&&asOf>=baseMs&&g.value!=null&&baseValue!=null&&tradeCash!=null&&quantityOk&&[...g.positions,...bpos].every(p=>p.qty!=null&&String(p.raw.record_type||'POSITION').toUpperCase()!=='FUND')&&!ledgerError&&!cur.rows.some(p=>p.conflict)&&!base.rows.some(p=>p.conflict))g.intervalPnl=g.value-baseValue+tradeCash+income;g.intervalVerified=reviewed&&g.intervalPnl!=null;g.quantityReconciled=quantityOk;g.intervalBase=baseValue;g.action=signalAction(g,trustedSignal,id)}const allocated=sum(groups.filter(g=>g.group!=='UNALLOCATED').map(g=>g.value)),rest=groups.find(g=>g.group==='UNALLOCATED');rest.value=nav!=null&&allocated!=null?nav-allocated:null;const day=n(a.today_pnl),positionDay=sum(groups.filter(g=>g.group!=='UNALLOCATED').map(g=>g.day));rest.day=day!=null&&positionDay!=null?day-positionDay:null;const change=baseline&&nav!=null&&n(baseA.nav)!=null?nav-baseA.nav:null,periodFlows=(book.events||[]).some(e=>!e.voided_at&&M.parseMs(e.at)>asOf)?null:flows[id],net=change!=null&&periodFlows!=null?change-periodFlows:null,knownStrategy=sum(groups.filter(g=>g.group!=='UNALLOCATED').map(g=>g.intervalPnl));rest.intervalPnl=net!=null&&knownStrategy!=null?net-knownStrategy:null;rest.intervalVerified=reviewed&&rest.intervalPnl!=null;const check=sum(groups.map(g=>g.value)),reconciled=nav!=null&&check!=null&&Math.abs(nav-check)<.01&&!(rest.value<-.01)&&!cur.rows.some(p=>p.conflict);if(!reconciled){errors.push(id+' 계좌 가치 대사 필요');for(const g of groups){g.intervalVerified=false}}const returnBase=dietzBase(n(baseA.nav),book.events||[],id,baseMs,asOf);accountRows.push({id,label:NAMES[id],sourceComplete:Array.isArray(a.positions)&&nav!=null,nav,day,groups,baseNav:n(baseA.nav),change,flow:periodFlows,netProfit:net,actualProfit:reviewed&&reconciled?net:null,returnBase,actualReturn:reviewed&&reconciled&&returnBase>0?100*net/returnBase:null,reviewed,reconciled,sourcePnl:n(a.pnl??a.total_pnl),sourceReturn:n(a.return_pct??a.total_return_pct)})}
const total={nav:sum(accountRows.map(a=>a.nav)),day:sum(accountRows.map(a=>a.day)),baseNav:sum(accountRows.map(a=>a.baseNav)),flow:sum(accountRows.map(a=>a.flow)),change:sum(accountRows.map(a=>a.change)),netProfit:sum(accountRows.map(a=>a.netProfit)),actualProfit:sum(accountRows.map(a=>a.actualProfit)),sourcePnl:sum(accountRows.map(a=>a.sourcePnl)),sourceKnownPnl:accountRows.reduce((s,a)=>s+(a.sourcePnl??0),0),sourceKnownCount:accountRows.filter(a=>a.sourcePnl!=null).length};total.returnBase=sum(accountRows.map(a=>a.returnBase));total.actualReturn=total.actualProfit!=null&&total.returnBase>0?100*total.actualProfit/total.returnBase:null;total.returnMethod='MODIFIED_DIETZ';total.reconciled=accountRows.every(a=>a.reconciled);return {schema:'CT_STRATEGY_ATTRIBUTION_V1',snapshot_id:C.snapshot_id,as_of:C.generated_kst||C.observed_at,baseline_at:baseline?.at||null,accounts:accountRows,total,errors,ledgerStatus:source.status||'NOT_LOADED',tradeErrors:trades.errors,reviewed,orders:'NONE',aggregation_rule:'SUM_FOUR_PHYSICAL_ACCOUNTS_TOSS_OWNS_TRIPOD_NO_EXTRA_NAV'}}
const api={strategyCapital,strategyRealized,applyStrategyPerformance,brokerCheckpoint,preferBrokerRealized,IDS,owner,classify,assertImmutableStrategyAnchor,requireRestoredStrategyBook,leverage,exposureLabel,accountPolicy,signalState,strategySummary,estimateMasterRealized,estimateTossExit,positions,normalizeTrade,ledgerRows,withBrokerTrades,withConfirmedTradeFx,withReceiptKrw,costReason,flowBook,holdingCost,openingHoldingCost,costEvidence,build,signalAction,dietzBase};if(typeof module==='object'&&module.exports){module.exports=api;return}root.JjooniStrategyBooks=api;if(!root.document)return;if(root.__JJOONI_STRATEGY_BOOKS_V1)return;
const API='https://jjooni-ct-fast-apgynr7pea-du.a.run.app',S={book:{},ledger:{},masterActivity:{status:'NOT_LOADED'},busy:false,error:'',loaded:false,recorded:new Set(),activeAccount:'ALL'};root.__JJOONI_STRATEGY_BOOKS_V1=S;
const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!=null)x.textContent=text;if(cls)x.className=cls;return x},won=x=>n(x)==null?'확인 필요':(x<0?'-':'')+'₩'+Math.round(Math.abs(x)).toLocaleString('ko-KR'),signed=x=>n(x)==null?'확인 필요':(x>0?'+':'')+won(x),pct=x=>n(x)==null?'확인 필요':(x>=0?'+':'')+x.toFixed(2)+'%',tone=x=>x>0?'sbUp':x<0?'sbDown':'';
async function request(path,body){const pw=sessionStorage.getItem('jjooni_ct_session_pw');if(!pw)throw Error('로그인이 필요합니다');const epoch=Math.floor(Date.now()/30000),key=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),{name:'HMAC',hash:'SHA-256'},false,['sign']),bytes=new Uint8Array(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode('ct-fast:'+epoch))),proof=[...bytes].map(x=>x.toString(16).padStart(2,'0')).join(''),ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),35000);try{const r=await fetch(API+path,{method:'POST',cache:'no-store',signal:ctrl.signal,headers:{'Content-Type':'application/json','X-CT-Epoch':String(epoch),'X-CT-Proof':proof},body:JSON.stringify(body)}),out=await r.json();if(!r.ok)throw Error(out.error||out.error_type||'조회 실패');return out}finally{clearTimeout(timer)}}
function style(){if(document.getElementById('ctStrategyBooksStyle'))return;const s=el('style');s.id='ctStrategyBooksStyle';s.textContent=`.ctStrategyBooks{margin:16px 0;padding:20px;background:#fff;border:1px solid #dce5ef;border-radius:16px;color:#142b45;min-width:0}.ctStrategyBooks h3{margin:0 0 7px;font-size:20px}.ctStrategyBooks h4{margin:18px 0 8px}.ctStrategyBooks .sbNote{font-size:12px;color:#667085;line-height:1.7}.ctStrategyBooks .sbMetrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.ctStrategyBooks .sbMetric{padding:13px;background:#f6f9fc;border-radius:10px;min-width:0}.ctStrategyBooks .sbMetric small{display:block;font-size:11px;color:#667085}.ctStrategyBooks .sbMetric b{display:block;font-size:21px;margin-top:5px;overflow-wrap:anywhere}.ctStrategyBooks .sbControls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0}.ctStrategyBooks button{padding:8px 11px;background:#1459a6;color:#fff;border:0;border-radius:7px;cursor:pointer}.ctStrategyBooks button:disabled{opacity:.5;cursor:wait}.ctStrategyBooks select,.ctStrategyBooks input{padding:8px;border:1px solid #ccd7e5;border-radius:7px;background:#fff;color:#142b45;max-width:100%;min-width:0}.ctStrategyBooks .sbScroll{overflow:auto}.ctStrategyBooks table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}.ctStrategyBooks th,.ctStrategyBooks td{padding:10px;text-align:right;border-bottom:1px solid #e7edf5}.ctStrategyBooks th:first-child,.ctStrategyBooks td:first-child{text-align:left}.ctStrategyBooks th{background:#f6f9fc;color:#667085;font-weight:700}.ctStrategyBooks .sbUp{color:#d92d20}.ctStrategyBooks .sbDown{color:#175cd3}.ctStrategyBooks details{border:1px solid #e4eaf2;border-radius:10px;padding:12px;margin-top:10px}.ctStrategyBooks summary{cursor:pointer;font-size:14px;font-weight:700}.ctStrategyBooks .sbBadge{padding:7px 10px;background:#eef8f1;border-radius:7px;font-size:12px;line-height:1.6}.ctStrategyBooks .sbWarning{background:#fff7ed;color:#92400e}.ctStrategyBooks form{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.ctStrategyBooks form input{width:155px}.ctStrategyBooks .sbFormLabel{font-size:12px;color:#667085;display:flex;flex-direction:column;gap:5px}.ctStrategyBooks .sbRule{display:block;padding:8px;border-radius:7px;white-space:normal;min-width:140px;max-width:250px;line-height:1.6}.ctStrategyBooks .sbGREEN{background:#eaf8ef;color:#146c43}.ctStrategyBooks .sbYELLOW{background:#fff6dd;color:#875d00}.ctStrategyBooks .sbRED{background:#fff0ee;color:#b42318}.ctStrategyBooks .sbEyebrow{font-size:11px;font-weight:700;letter-spacing:.09em;color:#5d728c}.ctStrategyBooks .sbHeading p{margin:4px 0 14px}.ctStrategyBooks .sbHero{padding:22px;background:#f3f7ff;border:1px solid #cdddf6;border-radius:14px}.ctStrategyBooks .sbHeroLabel{font-size:14px;font-weight:700}.ctStrategyBooks .sbHeroReturn{display:block;font-size:42px;line-height:1.3;margin:6px 0;overflow-wrap:anywhere}.ctStrategyBooks .sbHeroPnl{font-size:20px;font-weight:700}.ctStrategyBooks .sbHeroValues{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:16px}.ctStrategyBooks .sbHeroValues .sbMetric{background:#fff;padding:10px}.ctStrategyBooks .sbHeroValues .sbMetric b{font-size:17px}.ctStrategyBooks .sbAccountCards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ctStrategyBooks .sbAccountCard{padding:16px;border:1px solid #dce5ef;border-radius:12px;min-width:0}.ctStrategyBooks .sbCardHead{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.ctStrategyBooks .sbCardHead strong{font-size:25px;overflow-wrap:anywhere}.ctStrategyBooks .sbCardMoney{display:flex;justify-content:space-between;gap:8px;margin:8px 0;font-size:14px}.ctStrategyBooks .sbCardMoney span:last-child{font-weight:700}.ctStrategyBooks .sbCardAmounts{display:flex;gap:8px 15px;flex-wrap:wrap;font-size:12px;color:#667085}.ctStrategyBooks .sbRealized{font-size:15px;font-weight:800;margin-top:9px}.ctStrategyBooks .sbPeriod{font-size:12px;margin-top:12px;padding-top:10px;border-top:1px solid #dce5ef;line-height:1.6;overflow-wrap:anywhere}.ctStrategyBooks .sbMissing{font-size:12px;color:#92400e;line-height:1.5;overflow-wrap:anywhere}.ctStrategyBooks .sbCardAction{margin-top:8px;font-size:11px;color:#60748a}.ctStrategyBooks .sbCoverage{padding:10px;background:#fff6dd;border-radius:8px;margin-top:12px;font-size:12px;line-height:1.7}.ctStrategyBooks .sbCoverage span{display:block}.ctStrategyBooks .sbRuleCard{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:15px}.ctStrategyBooks .sbRuleCard>b,.ctStrategyBooks .sbRuleCard>p{grid-column:1/-1}.ctStrategyBooks .sbRuleCard .sbRule{min-width:0;max-width:none}.ctStrategyBooks .sbTotalRow{font-weight:800;background:#f6f9fc}@media(max-width:699px){.ctStrategyBooks .sbAccountCards{grid-template-columns:minmax(0,1fr)}.ctStrategyBooks .sbHero{padding:15px}.ctStrategyBooks .sbHeroReturn{font-size:36px}.ctStrategyBooks .sbHeroPnl{font-size:17px}.ctStrategyBooks .sbHeroValues{grid-template-columns:repeat(2,minmax(0,1fr))}.ctStrategyBooks .sbHeroValues .sbMetric b{font-size:16px}.ctStrategyBooks .sbRuleCard{grid-template-columns:minmax(0,1fr)}.ctStrategyBooks{padding:13px}.ctStrategyBooks .sbMetrics{grid-template-columns:repeat(2,minmax(0,1fr))}.ctStrategyBooks .sbMetric b{font-size:17px}.ctStrategyBooks th,.ctStrategyBooks td{padding:8px}}`;document.head.append(s)}
// Account cards display strategy attribution from the same book as the strategy tab.
// These are nested disclosures, never additional account/NAV rows.
function accountSleeves(){
 for(const card of document.querySelectorAll('.ctAcct,.ctA8Card,.ctP8Card')){
  const name=card.querySelector('.ctAcctName,.ctA8Name,.ctP8Name')?.textContent?.trim()||'',id=/^(?:Toss|토스)(?:\s|$)/i.test(name)?'TOSS':/^ISA(?:\s|$)/i.test(name)?'ISA':/^IRP(?:\s|$)/i.test(name)?'IRP':/^연금저축(?:\s|$)/.test(name)?'PENSION':null;if(!id)continue;
  const row=S.performance?.accounts.find(a=>a.id===id),waiting=!S.loaded,title=id==='TOSS'?'트라이팟':id==='ISA'?'바이팟':'나스닥100 · TRI-POD 적용형';
  const signature=JSON.stringify([id,waiting,S.busy,S.error,row,S.performance?.as_of]);let panel=card.querySelector('.ctStrategySleeve');if(panel?.dataset.signature===signature)continue;
  if(!panel){panel=el('section',null,'ctStrategySleeve');panel.dataset.account=id;panel.setAttribute('aria-label',title+' 성과');card.append(panel)}panel.dataset.signature=signature;const wasOpen=!!panel.querySelector('.ctSleeveDisclosure[open]');panel.replaceChildren();
  const head=el('div',null,'ctSleeveHead');head.append(el('b',title+' · 누적 수익률'),el('strong',waiting?(S.error?'조회 실패':'조회 중…'):!row?.available?'원본 연결 대기':!row.count&&!row.capital&&!row.masterRealized?.sales?.length?'미편입':row.cumulativeReturn==null?'누적 원장 확인 중':pct(row.cumulativeReturn),tone(row?.cumulativeReturn)));panel.append(head,capitalHighlight(row,waiting));
  const amounts=el('div',null,'ctSleeveAmounts');amounts.append(el('span','평가액 '+won(row?.value)),el('span','원화 보유손익 '+(waiting?'조회 중…':!row?.count?'—':signed(row.holdingPnl)),tone(waiting?null:row?.holdingPnl)),el('span','보유 원가 '+(waiting?'조회 중…':won(row?.cost))),el('span','보유 수익률 '+(waiting?'조회 중…':pct(row?.holdingReturn))));panel.append(amounts);if(!waiting)panel.append(el('div','누적손익 '+signed(row?.cumulativePnl),'ctSleeveCumulative '+tone(row?.cumulativePnl)));const dayLine=el('div',null,'ctSleeveDay');dayLine.append(el('span','당일 보유 가격손익'),el('strong',waiting?'조회 중…':!row?.available?'원본 연결 대기':!row.count?'— · 미편입':signed(row.day)+' · '+pct(row.dayReturn),tone(row?.day)));panel.append(dayLine);
   const realized=row?.masterRealized;
   if(!waiting&&realized?.status==='AVAILABLE'&&realized.sales.length&&row.holdingPnl!=null){
    const combined=row.holdingPnl+realized.pnl;
    const x=el('div',null,'ctSleeveRealized');
    x.append(el('span',realized.confirmed?'증권사 확정 매도손익':id==='TOSS'?'이월 매도손익 · 거래별 원가·비용':'기록된 매도 실현손익 · 비용 전'),colored(realized.pnl),
             el('span','보유+기록된 매도손익'),colored(combined));
    panel.append(x);
    panel.append(el('p',realized.confirmed?'증권사 증빙의 수수료·세금 포함 매도손익 이월 · 보유손익은 최신 평가액−저장 원가 · 확인한 거래 범위 합계':id==='TOSS'?'최초 고정 원가 이후 매도 전체를 거래별 환율·비용으로 이월 · 증권사 확정 매도손익 우선':'마스터 거래원장 가중평균 원가 기준 · 수수료·세금 및 증권사 체결 대사 전 · 확정 수익률 아님','ctSleeveNote'));
   }else if(id==='ISA'&&!waiting)panel.append(el('p','매도 실현손익 '+(realized?.status==='PARTIAL'?'거래·잔고 대사 필요':'마스터 원장 조회 대기'),'ctSleeveNote'));
   const disclosure=el('details',null,'ctSleeveDisclosure');disclosure.open=wasOpen;disclosure.addEventListener('click',e=>e.stopPropagation());disclosure.append(el('summary','편입종목·산정 기준'),holdingPreview(row));panel.append(disclosure);if(!waiting&&row?.count)panel.append(el('p','누적 = 보유손익 + 이월 매도손익 + 귀속 배당 · 수익률 기준원금은 ETF 전환 때 유지. 당일은 현재 보유수량의 가격변동이며 당일 매도분·환율효과는 제외','ctSleeveNote'));
  if(!waiting&&row?.missing.length)disclosure.append(el('p',row.missing.map(x=>x.ticker+' · '+x.reason).join(' / '),'ctSleeveNote'));
  disclosure.append(el('p',id==='TOSS'?'토스 실잔고의 QQQ·QQQM·QLD·TQQQ 집계 · 전략 전환 후에도 동일 원장으로 추적':id==='ISA'?'국내 패시브 나스닥100 1배·2배 보유분':'해당 계좌의 패시브 나스닥100 보유분 · 액티브 제외','ctSleeveNote'),el('p','계좌 자산에 포함 · 총자산에 한 번만 반영','ctSleeveNote'));
  if(waiting&&S.error)panel.append(el('p',S.error,'ctSleeveNote'));
  const button=el('button',waiting&&S.error?'다시 조회':'전략 성과 상세');button.type='button';button.onclick=e=>{e.stopPropagation();if(waiting&&S.error)return load(true);S.activeAccount=id;document.querySelector('.tab[data-tab="tripod"]')?.click();render();box?.scrollIntoView({block:'start',behavior:'smooth'})};panel.append(button)
 }
}
function holdingPreview(row){const list=el('ul',null,'sbHoldingPreview');list.setAttribute('aria-label','전략 편입 보유종목');for(const p of row?.holdings||[]){const item=el('li');item.dataset.strategyTicker=p.ticker;item.append(el('b',p.name),el('span',p.ticker+' · '+(p.qty==null?'수량 확인 필요':Number(p.qty).toLocaleString('ko-KR',{maximumFractionDigits:6})+'주')));list.append(item)}return list}
function sleeveStyle(){if(document.getElementById('ctStrategySleeveStyle'))return;const s=el('style');s.id='ctStrategySleeveStyle';s.textContent=`.ctStrategySleeve{grid-column:1/-1;flex-basis:100%;box-sizing:border-box;min-width:0;width:100%;padding:12px;margin-top:10px;border:1px solid #d8e5f4;border-radius:10px;background:#f4f8ff;text-align:left;white-space:normal;color:#142b45;font:13px/1.6 system-ui}.ctSleeveHead{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}.ctSleeveHead strong{font-size:23px}.ctStrategySleeve .ctStrategyCapital,.ctStrategyBooks .ctStrategyCapital{display:flex;align-items:baseline;justify-content:space-between;gap:6px 14px;flex-wrap:wrap;margin:12px 0;padding:12px 14px;border:1px solid #c4d8f2;border-radius:9px;background:#fff;color:#142b45;min-width:0}.ctStrategySleeve .ctStrategyCapital>span,.ctStrategyBooks .ctStrategyCapital>span{font-size:14px;font-weight:700;color:#365a7f}.ctStrategySleeve .ctStrategyCapital>strong,.ctStrategyBooks .ctStrategyCapital>strong{font-size:24px;font-weight:800;line-height:1.35;letter-spacing:-.03em;font-variant-numeric:tabular-nums;overflow-wrap:anywhere;max-width:100%}.ctSleeveAmounts{display:flex;gap:3px 14px;flex-wrap:wrap;margin-top:5px}.ctSleeveAmounts span{overflow-wrap:anywhere}.ctStrategySleeve .ctSleeveDay{display:flex;justify-content:space-between;gap:10px;align-items:baseline;margin-top:8px;border-top:1px solid #dce5ef;padding-top:8px;font-size:13px}.ctStrategySleeve .ctSleeveDay strong{font-size:16px;text-align:right}.ctSleeveRealized{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 12px;border-top:1px solid #dce5ef;margin-top:9px;padding-top:9px;font-size:13px}.ctSleeveRealized span:nth-child(even){font-weight:800;text-align:right}.ctStrategySleeve .sbUp{color:#d92d20}.ctStrategySleeve .sbDown{color:#175cd3}.ctStrategySleeve .ctSleeveNote{margin:4px 0;color:#667085;font-size:13px;overflow-wrap:anywhere}.sbHoldingPreview{list-style:none;padding:0;margin:10px 0}.sbHoldingPreview li{padding:9px 0;border-top:1px solid #dce5ef;overflow-wrap:anywhere}.sbHoldingPreview b{display:block;font-size:15px;line-height:1.5}.sbHoldingPreview span{display:block;font-size:13px;line-height:1.6;color:#526779}.ctStrategySleeve button{background:#1459a6;color:#fff;border:0;border-radius:6px;font:inherit;padding:10px 12px;min-height:44px;margin-top:5px;cursor:pointer}`;document.head.append(s)}
let box=null,lastRenderSignature=null;
function ensure(){style();const host=document.getElementById('panel-tripod')||document.getElementById('panel-compare')||document.getElementById('panel-overview');if(!host)return false;if(!box?.isConnected){box=el('section',null,'ctStrategyBooks');box.id='ctStrategyBooksV1';host.prepend(box)}if(host.firstElementChild!==box)host.prepend(box);return true}
function table(headers,rows){const wrap=el('div',null,'sbScroll'),t=el('table'),head=el('tr');headers.forEach(h=>head.append(el('th',h)));t.append(head);for(const r of rows){const tr=el('tr');for(const value of r){const td=el('td');if(value instanceof Node)td.append(value);else td.textContent=value;tr.append(td)}t.append(tr)}wrap.append(t);return wrap}
function metric(label,value,sub){const x=el('div',null,'sbMetric');x.append(el('small',label),el('b',value),el('small',sub));return x}
function colored(value,format=signed){return el('span',format(value),tone(value))}
function capitalHighlight(row,waiting=false){const box=el('div',null,'ctStrategyCapital');box.setAttribute('aria-label','수익률 기준원금');box.append(el('span','기준원금'),el('strong',waiting?'조회 중…':won(row?.capital)));return box}
function periodLine(row){if(row.cumulativePnl!=null)return '누적손익 '+signed(row.cumulativePnl)+' · 기준원금 '+won(row.capital)+' · '+(row.cumulativeComplete?'보유·매도 원장 대사':'확인된 거래 범위');if(row.masterRealized?.status==='AVAILABLE'&&row.masterRealized.sales.length&&row.holdingPnl!=null)return (row.id==='TOSS'?'보유+TQQQ 매도 잠정손익 ':'바이팟 잠정 합산손익 ')+signed(row.holdingPnl+row.masterRealized.pnl)+' · 매도손익 '+signed(row.masterRealized.pnl)+' 포함, 비용 미확인';return row.periodPnl!=null&&row.periodParticipated?'추적기간 실수익 '+signed(row.periodPnl):row.periodParticipated===false?'추적기간 실수익 — · 미편입':'추적기간 실수익 — · '+(row.periodReason||'계좌별 확인 사유 참고')}
function render(){
 if(!ensure())return;
 // An empty client book during the first network read is not missing cost data.
 // Never publish a partial return or a missing-cost diagnosis before it arrives.
 if(!S.loaded){
  sleeveStyle();accountSleeves();box.setAttribute('aria-busy',String(S.busy));
  const signature=JSON.stringify(['BOOK_PENDING',S.busy,S.error]);if(lastRenderSignature===signature&&box.childElementCount)return;
  lastRenderSignature=signature;box.replaceChildren(el('h3','트라이팟 성과'),el('p',S.error?'전략 원장 연결 실패':'전략 원장 불러오는 중','sbBookStatus'),el('p',S.error?'저장된 원가·체결 원장을 조회하지 못했습니다. 원가 누락으로 판정하지 않았습니다.':'저장된 원가·체결 원장을 받은 뒤 보유 수익률을 계산합니다.','sbNote'));
  if(S.error){box.append(el('p',S.error,'sbNote'));const retry=el('button','원장 다시 조회');retry.disabled=S.busy;retry.onclick=()=>load(true);box.append(retry)}
  return;
 }
 box.setAttribute('aria-busy',String(S.busy));
 const C=root.__JJOONI_CANONICAL_SSOT||{},tp=root.__JJOONI_TRIPOD_DAILY_FRESHNESS_V35?.last;let view,connected;try{connected=withBrokerTrades(S.ledger,root.__JJOONI_LIVE_PAYLOAD||{});view=build(C,S.book,connected,tp)}catch(e){box.replaceChildren(el('h3','트라이팟 성과'),el('p',e.message,'sbNote'));return}
 S.snapshot=view;const overview=strategySummary(view),masterEstimate=estimateMasterRealized(S.masterActivity,view);for(const row of overview.accounts)row.masterRealized=preferBrokerRealized(S.book,view,row.id,row.id==='TOSS'?estimateTossExit(S.book,connected,view):masterEstimate.accounts[row.id],connected);applyStrategyPerformance(overview,S.book,view,connected,S.masterActivity);S.performance=overview;S.realizedEstimate=masterEstimate;sleeveStyle();accountSleeves();
 const refreshButton=box.querySelector('.sbControls button');if(refreshButton){refreshButton.disabled=S.busy;const label=S.busy?'확인 중…':'성과 새로고침';if(refreshButton.textContent!==label)refreshButton.textContent=label}
 const submitButton=box.querySelector('.sbFlowJournal button[type="submit"]');if(submitButton)submitButton.disabled=S.busy||!view.baseline_at;
 const signature=JSON.stringify([view,S.book,S.ledger,S.masterActivity,S.activeAccount,S.error]);
 if(signature===lastRenderSignature&&box.childElementCount)return;
 const openDetails=new Set([...box.querySelectorAll('details[open]')].map(d=>d.className+'|'+(d.dataset.account||'')));
 const priorBrokerForm=box.querySelector('.sbBrokerEvidence form');const priorForm=box.querySelector('.sbFlowJournal form'),focusedInput=priorForm?.contains(document.activeElement)?document.activeElement:null;
 const total=overview.total,selected=view.accounts.filter(a=>S.activeAccount==='ALL'||a.id===S.activeAccount);const draft=document.createDocumentFragment();
 const heading=el('div',null,'sbHeading');heading.append(el('div','TRI-POD PERFORMANCE','sbEyebrow'),el('h3','트라이팟 성과'),el('p','토스: QQQ·QQQM·QLD·TQQQ 보유분 · ISA: 패시브 나스닥100 1배·2배 · 연금저축·IRP: 패시브 나스닥100 · 액티브 제외','sbNote'));draft.append(heading);draft.append(el('p','누적손익은 현재 보유손익에 이전 매도손익과 전략 배당을 이월해 계산합니다. ETF 교체 시 기준원금과 과거 손익을 유지하며, 당일 보유 가격손익은 별도로 표시합니다.','sbNote'));draft.append(el('p','트라이팟은 토스 안의 전략입니다. 토스 실제 잔고로 한 번만 계산하며 별도 트라이팟 자산을 다시 더하지 않습니다.','sbNote'));const basis=S.book.cost_basis_v1;if(basis?.policy==='CURRENT_FX_OPENING_THEN_TRADE_FX')draft.append(el('p','기존 해외 원가: '+new Date(basis.at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' 기준환율로 고정 · 이후 매수: 거래 당시 환율','sbBadge'));
 if(connected.sheet_latest_at)draft.append(el('p','과거 체결 원장 최신 '+connected.sheet_latest_at.slice(0,10)+' · 최신 증권사 체결 '+connected.broker_added+'건 보완 · 환율 누락 체결은 서버에 고정한 확인 시점 환율 적용','sbNote'));
 const receiptPins=Object.values(S.book.trade_krw_v1||{});if(receiptPins.length)draft.append(el('p','사용자 제공 토스 주문화면 원화 매수금액 '+receiptPins.length+'건 적용 · 기준원가 이전 매수는 중복 가산 제외 · 수수료는 증권사 체결 기준','sbBadge'));
 const fxPins=Object.values(S.book.trade_fx_v1||{}).filter(p=>classify(p,p.account)==='NASDAQ_SYSTEM');if(fxPins.length){const rates=[...new Set(fxPins.map(p=>Number(p.fx).toLocaleString('ko-KR',{maximumFractionDigits:6})))];draft.append(el('p','확인 시점 환율 고정 적용 · USD/KRW '+rates.join(' / ')+'원 · '+fxPins.length+'건 · 이후 환율 변동으로 원가 재계산 없음','sbBadge'));}
 const hero=el('section',null,'sbHero');hero.setAttribute('aria-label','전체 트라이팟 성과');hero.append(el('div','전체 트라이팟 누적 수익률','sbHeroLabel'),el('strong',total.cumulativeReturn!=null?pct(total.cumulativeReturn):!total.available?'원본 연결 대기':total.count?'계좌별 누적 성과 확인':'미편입','sbHeroReturn '+tone(total.cumulativeReturn)),el('div',total.cumulativePnl!=null?'누적손익 '+signed(total.cumulativePnl):'누적손익 · 계좌별 원장 확인 중','sbHeroPnl '+tone(total.cumulativePnl)));
 const values=el('div',null,'sbHeroValues');values.append(metric('전략 보유 평가액',won(total.value),'전체 계좌의 전략 보유분'),metric('수익률 기준원금',won(total.capital),'최초 원가 기준 · ETF 전환 시 유지'),metric('당일 보유 가격손익',signed(total.day)+' · '+pct(total.dayReturn),'현재 보유수량 기준 · 당일 매도분·환율효과 제외'));hero.append(values);
 if(total.missing.length){const coverage=el('div',null,'sbCoverage');coverage.append(el('b','원가 확인 '+total.coveredCount+'/'+total.count+'종목 · 원본 '+total.availableCount+'/4계좌'),el('span','확인된 종목만: '+pct(total.coveredReturn)+' · '+signed(total.coveredPnl)+' (전체 성과 아님)'));hero.append(coverage)}
 hero.append(el('div','추적기간 실수익 '+(total.periodPnl!=null?signed(total.periodPnl):'— · 계좌별 확인 사유 참고'),'sbPeriod '+tone(total.periodPnl)),el('p','누적 수익률 = 이월 매도손익·현재 보유손익·전략 배당 합계 ÷ 수익률 기준원금. 확인되지 않은 계좌의 원금·매도내역은 임의 추정하지 않습니다.','sbNote'));draft.append(hero);
 const controls=el('div',null,'sbControls'),select=el('select');select.setAttribute('aria-label','전략 성과 계좌 선택');for(const id of ['ALL',...IDS]){const o=el('option',id==='ALL'?'전체 계좌':NAMES[id]);o.value=id;select.append(o)}select.value=S.activeAccount;select.onchange=()=>{S.activeAccount=select.value;render()};const refresh=el('button',S.busy?'확인 중…':'성과 새로고침');refresh.disabled=S.busy;refresh.onclick=()=>load(true);controls.append(select,refresh);draft.append(controls);if(S.error){const warning=el('p',/ACCOUNT_SOURCE_STALE/.test(S.error)?'계좌 원본의 시각 확인이 필요해 원장 기록을 보류했습니다. 마지막 평가 자료를 표시합니다.':'최신 자료를 확인하지 못했습니다. 마지막 확인값을 표시합니다. 다시 새로고침해 주세요.','sbBadge sbWarning');warning.title=S.error;draft.append(warning)}
 draft.append(el('h4','계좌별 트라이팟 성과'));const cards=el('div',null,'sbAccountCards');
 for(const row of overview.accounts.filter(a=>S.activeAccount==='ALL'||a.id===S.activeAccount)){
  const card=el('article',null,'sbAccountCard');card.dataset.account=row.id;card.setAttribute('aria-label',row.label+' 트라이팟 성과');const head=el('div',null,'sbCardHead');head.append(el('b',row.label),el('strong',!row.available?'원본 연결 대기':row.count||row.capital||row.masterRealized?.sales?.length?row.cumulativeReturn!=null?pct(row.cumulativeReturn):'누적 원장 확인 중':'미편입',tone(row.cumulativeReturn)));card.append(head,capitalHighlight(row));
  const line=el('div',null,'sbCardMoney sbCumulative');line.append(el('span','누적손익'),colored(row.cumulativePnl));card.append(line);const daily=el('div',null,'sbCardMoney');daily.append(el('span','당일 보유 가격손익'),row.count?el('span',signed(row.day)+' · '+pct(row.dayReturn),tone(row.day)):el('span','— · 미편입'));card.append(daily);const small=el('div',null,'sbCardAmounts');small.append(el('span','평가액 '+won(row.value)),el('span','현재 보유 원가 '+won(row.cost)));card.append(small);const holding=el('div',null,'sbCardMoney sbHoldingPnl');holding.append(el('span','현재 보유손익 · '+pct(row.holdingReturn)),colored(row.holdingPnl));card.append(holding,el('p','당일은 현재 보유수량의 가격변동 · 당일 매도분·환율효과 제외','sbNote'),holdingPreview(row));
   if(row.masterRealized?.status==='AVAILABLE'&&row.masterRealized.sales.length&&row.holdingPnl!=null){
    const last=row.masterRealized.sales.at(-1);
    card.append(el('div',(row.masterRealized.confirmed?'증권사 확정 매도손익 ':row.id==='TOSS'?'이월 매도손익(원가·비용 포함) ':'매도 실현손익(마스터 · 비용 전) ')+signed(row.masterRealized.pnl),'sbRealized '+tone(row.masterRealized.pnl)));
    card.append(el('div','보유+기록된 매도손익 '+signed(row.holdingPnl+row.masterRealized.pnl),'sbRealized '+tone(row.holdingPnl+row.masterRealized.pnl)));
    card.append(el('p',last.date+' '+last.ticker+' '+Number(last.qty).toLocaleString('ko-KR')+'주 매도 · '+(row.masterRealized.confirmed||row.masterRealized.complete&&row.id==='TOSS'?'수수료·세금 포함':'비용 반영 범위 확인'),'sbNote'));
   }
   if(row.id==='ISA'&&row.masterRealized?.status==='PARTIAL')card.append(el('p','매도손익 원장·잔고 대사 미완료 · 임의 합산 금지','sbMissing'));

  card.append(el('div',periodLine(row),'sbPeriod '+tone(row.periodPnl)));
  if(row.missing.length)card.append(el('p',row.missing.map(x=>x.ticker+' · '+x.reason).join(' / '),'sbMissing'));
  if(row.count&&!row.missing.length&&row.costQuality!=='ACTUAL_COST')card.append(el('small','초기 환율 고정·거래 원가 또는 증권사 평단 기준 · 비용 반영 범위 확인','sbNote'));
  if(row.action?.target)card.append(el('p','현재 목표: '+row.action.target,'sbBadge'));
  card.append(el('div',row.action?.action||'신호 검증 대기','sbCardAction'));cards.append(card)
 }draft.append(cards,el('p','전체 누적 수익률은 누적손익 합계 ÷ 고정 기준원금 합계이며, 계좌 수익률의 단순 평균이 아닙니다. 같은 종목도 계좌별 실제 보유분만 한 번씩 합산합니다.','sbNote'),el('p','시세 평가 기준 '+(view.as_of||'연결 대기')+' · 추적 시작 '+(view.baseline_at||'첫 원본 연결 대기'),'sbNote'));
 const master=C.master_refresh;if(master){const stamp=master.observed_at||'시각 확인 필요',missing=master.status==='UNAVAILABLE',sourceAt=master.source_updated_kst||master.source_modified_at||master.master_modified_at,frameAt=C.generated_kst||C.observed_at,behind=sourceAt&&frameAt&&M.parseMs(sourceAt)>M.parseMs(frameAt);draft.append(el('p',missing?'마스터 원천 조회 실패 · 이전 보유구성 참고값':behind?'마스터 수정시각이 현재 스냅샷보다 최신 · 다시 동기화 필요':'마스터 조회시각 '+stamp+' · 당일 거래·실잔고 반영 여부는 별도 대사 필요','sbNote'+(missing||behind?' sbWarning':'')))}else draft.append(el('p','마스터 원천 조회 상태 없음 · 거래·실잔고 동기화 미검증','sbNote sbWarning'));
 const rules=el('details',null,'sbRules');rules.append(el('summary','계좌별 운용 규칙 · 목표 구성'),el('p','공격: 상승·VIX10 < 28·고점 대비 낙폭 9% 이내. 감속: 상승 중 공격 조건 미충족 또는 하락·VIX10 < 18. 파킹: 하락·VIX10 ≥ 18.','sbNote'));
 for(const a of selected){const current=accountPolicy(a.id,signalState(tp)),rule=el('div',null,'sbRuleCard');rule.append(el('b',current.name));for(const [i,state] of STATES.entries()){const p=accountPolicy(a.id,state);rule.append(el('span',['공격','감속','파킹'][i]+': '+p.target+' · '+exposureLabel(p.exposure),'sbRule sb'+state))}rule.append(el('p','현재 목표: '+(current.target||'신호 검증 대기'),'sbNote'));rules.append(rule)}rules.append(el('p','비중은 해당 전략에 배정한 자금 기준입니다. IRP 0.85배 = 70% × 1배 + 30% × 0.5배. 파킹·채권혼합 자금은 귀속 확인 전까지 기타·미귀속으로 남습니다.','sbNote'));draft.append(rules);
 const audit=el('details',null,'sbPortfolioAudit');audit.append(el('summary','전체 자산·추적 원장 확인'),el('p','아래는 전략 이외 자산까지 포함한 실제 4계좌입니다. 트라이팟 평가액을 전체 자산에 다시 더하지 않습니다.','sbNote'));
 const metrics=el('div',null,'sbMetrics');metrics.append(metric('전체 계좌 순자산',won(view.total.nav),'실제 4계좌 합계'),metric('전체 오늘손익',signed(view.total.day),'원본 기준'),metric('전체 추적 실수익',signed(view.total.actualProfit),view.reviewed?'수정Dietz '+pct(view.total.actualReturn):'입출금 확인 후 확정'),metric('원본 누적손익',signed(view.total.sourcePnl),'자료 확인 '+view.total.sourceKnownCount+'/4계좌'));audit.append(metrics);
 const review=el('button','전체 4계좌 입출금 대사 완료');review.disabled=S.busy||!view.baseline_at;review.onclick=()=>write({command:'review',snapshot_id:C.snapshot_id});audit.append(review,el('p','계좌 실수익 = 현재 순자산 − 추적 시작 순자산 − 순입금. 내부이체는 전체 합계에서 상쇄됩니다. 전략 추적 실수익은 보유자산 원본·체결 원장·배당 및 비용 귀속을 대사해 계산합니다.','sbNote'),table(['계좌','순자산','오늘손익','추적 원화 실수익','순입금','대사'],selected.map(a=>[a.label,won(a.nav),signed(a.day),signed(a.actualProfit),signed(a.flow),a.reviewed?'확인 완료':'확인 필요'])));
 if(fxPins.length)audit.append(el('h4','확인 시점 환율 적용 내역'),table(['계좌','종목','수량','적용 환율','환율 확인 시각'],fxPins.map(p=>[NAMES[p.account],p.ticker,String(p.qty),String(p.fx),p.confirmed_at])));
 if(basis?.positions)audit.append(el('h4','고정한 해외 기준원가'),table(['계좌','종목','초기 환율','초기 수량','원화 기준원가'],Object.values(basis.positions).filter(p=>IDS.includes(p.account)).map(p=>[NAMES[p.account],p.ticker,String(p.fx),String(p.qty),won(p.cost_krw)])));if(total.missing.length)audit.append(el('h4','전략 원가 자료 누락'),...total.missing.map(x=>el('p',NAMES[x.account]+' · '+x.ticker+' · '+x.reason,'sbMissing')));
 if(view.errors.length||view.tradeErrors.length)audit.append(el('p',[...view.errors,...view.tradeErrors.map(x=>x.reason)].slice(0,8).join(' · '),'sbBadge sbWarning'));draft.append(audit);
 for(const a of selected){const detail=el('details',null,'sbAccountDetails');detail.dataset.account=a.id;detail.append(el('summary',a.label+' · 종목·전략 상세'));detail.append(table(['전략','평가액','원화 보유손익','보유 수익률','추적 실수익'],a.groups.map(g=>[g.label,won(g.value),signed(g.holdingPnl),pct(g.holdingReturn),signed(g.intervalVerified?g.intervalPnl:null)])),table(['종목','전략','상품 배율','수량','평가액 · 원화','원화 원가','원화 보유손익'],a.groups.flatMap(g=>g.positions.map(p=>[p.name+' · '+p.ticker,g.label,g.group==='NASDAQ_SYSTEM'?exposureLabel(p.leverage):'대상 외',String(p.qty??'확인 필요'),won(p.value),won(p.cost),signed(p.holdingPnl)]))));draft.append(detail)}
 brokerEvidenceForm(draft,view);strategyAllocationForm(draft,view);flowForm(draft,view);draft.append(el('p','나스닥 액티브는 별도 집계합니다. 기존 해외 원가는 초기 적용 환율로 고정하며 과거 환차손익은 제외됩니다. 이후 거래는 거래 당시 환율을 우선하며, 누락 시 처음 확인한 현재 환율을 거래별로 고정합니다. 보유 성과와 추적기간 실수익은 서로 다른 지표이며 추적 시작 이전 실현손익은 포함되지 않습니다.','sbNote'))
 for(const d of draft.querySelectorAll('details'))if(openDetails.has(d.className+'|'+(d.dataset.account||'')))d.open=true;
 const nextForm=draft.querySelector('.sbFlowJournal form');if(priorForm&&nextForm){priorForm.querySelector('button[type="submit"]').disabled=S.busy||!view.baseline_at;nextForm.replaceWith(priorForm)}
 const nextBrokerForm=draft.querySelector('.sbBrokerEvidence form');if(priorBrokerForm&&nextBrokerForm){priorBrokerForm.querySelector('button[type="submit"]').disabled=S.busy;nextBrokerForm.replaceWith(priorBrokerForm)}
 // Commit a complete result once; keep the prior cards visible during ledger work.
 box.replaceChildren(draft);
 if(focusedInput)focusedInput.focus({preventScroll:true});
 lastRenderSignature=signature;

}
function brokerEvidenceForm(parent,view){
 const detail=el('details',null,'sbBrokerEvidence');detail.append(el('summary','증권사 원가·확정 매도손익 저장'));
 detail.append(el('p','증권사 화면의 원화 금액을 저장합니다. 보유 원가는 현재 수량을 확인하고, 매도손익은 동일한 체결에 한 번만 연결합니다.','sbNote'));
 const form=el('form'),kind=optionSelect([['HOLDING_COST','현재 보유 원가'],['REALIZED_SALE','확정 매도손익']],'증빙 종류'),account=optionSelect(IDS.map(id=>[id,NAMES[id]]),'증빙 계좌');form.append(kind,account);
 const inputs={};for(const [key,label,type] of [['ticker','증빙 종목코드','text'],['qty','증빙 수량','number'],['cost_krw','증빙 매입원가 원','number'],['trade_date','증빙 매도일','date'],['proceeds_krw','증빙 매도금액 원','number'],['fees_krw','증빙 수수료와 세금 원','number'],['net_pnl_krw','증빙 최종 매도손익 원','number'],['reference','증빙 출처','text']]){
  const wrap=el('label',label,'sbFormLabel'),input=el('input');input.type=type;input.required=true;input.setAttribute('aria-label',label);if(type==='number')input.step='any';wrap.append(input);form.append(wrap);inputs[key]={input,wrap};
 }
 const sync=()=>{const sale=kind.value==='REALIZED_SALE';for(const key of ['trade_date','proceeds_krw','fees_krw','net_pnl_krw']){inputs[key].wrap.hidden=!sale;inputs[key].input.required=sale}};kind.onchange=sync;sync();
 const submit=el('button','증빙을 서버 원장에 저장');submit.type='submit';submit.disabled=S.busy;form.append(submit);
 form.onsubmit=async e=>{e.preventDefault();const evidence={kind:kind.value,account:account.value};for(const [key,{input}] of Object.entries(inputs))if(input.required)evidence[key]=input.type==='number'?Number(input.value):input.value;await write({command:'confirm_broker_evidence',evidence});if(!S.error)detail.append(el('p','저장 완료 · 다른 기기에서도 같은 원장을 사용합니다.','sbBadge'))};detail.append(form);if(S.error)detail.append(el('p',S.error,'sbMissing'));
 const receipts=[...Object.values(S.book.broker_holding_costs_v1||{}),...Object.values(S.book.broker_realized_sales_v1||{})];if(receipts.length)detail.append(table(['계좌','종목','종류','수량','원가','확정 매도손익','증빙'],receipts.map(r=>[NAMES[r.account],r.ticker,r.kind==='HOLDING_COST'?'보유 원가':'매도손익',String(r.qty),won(r.cost_krw),r.kind==='REALIZED_SALE'?signed(r.net_pnl_krw):'—',r.reference])));parent.append(detail);
}
function optionSelect(options,label){const s=el('select');s.setAttribute('aria-label',label);for(const [value,text] of options){const o=el('option',text);o.value=value;s.append(o)}return s}
function strategyAllocationForm(parent,view){
 const detail=el('details',null,'sbStrategyAllocation');detail.append(el('summary','전략 기준원금 편입·회수 기록'));
 detail.append(el('p','같은 계좌의 현금과 전략 사이 배분만 기록합니다. 계좌 전체 입출금은 바뀌지 않습니다. ETF 교체 매도대금은 새 편입금이 아닙니다. 초기 확정은 기존 전략 기준원금이 없을 때만 사용합니다.','sbNote'));
 if(!document.getElementById('sbAllocationStyles')){const st=el('style');st.id='sbAllocationStyles';st.textContent='.sbAllocationForm{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:8px}.sbAllocationForm>*{box-sizing:border-box;min-width:0;max-width:100%;min-height:44px}';document.head.append(st)}
 const form=el('form',null,'sbAllocationForm'),account=optionSelect(IDS.map(id=>[id,NAMES[id]]),'전략 원금 계좌'),kind=optionSelect([['STRATEGY_ALLOCATION_IN','전략 추가 편입'],['STRATEGY_ALLOCATION_OUT','전략 자금 회수'],['STRATEGY_OPENING','초기 기준원금 확정']],'전략 원금 유형'),amount=el('input'),at=el('input'),note=el('input');
 amount.type='number';amount.min='1';amount.step='1';amount.required=true;amount.setAttribute('aria-label','전략 원금 금액');at.type='datetime-local';at.step='1';at.required=true;at.value=new Date(Date.now()+9*3600000).toISOString().slice(0,19);at.setAttribute('aria-label','전략 원금 발생시각');note.required=true;note.placeholder='금액의 근거';note.setAttribute('aria-label','전략 원금 근거');const submit=el('button','전략 원금 기록');submit.type='submit';submit.disabled=S.busy||!view.baseline_at;form.append(account,kind,amount,at,note,submit);
 form.onsubmit=async e=>{e.preventDefault();const row=S.performance?.accounts?.find(x=>x.id===account.value),v=Number(amount.value);if(!row){S.error='계좌 전략 성과를 확인해 주세요.';render();return}if(kind.value==='STRATEGY_OPENING'&&row.capital!=null){S.error='이미 기준원금이 있습니다. 추가 편입 또는 회수를 선택하세요.';render();return}if(kind.value!=='STRATEGY_OPENING'&&row.capital==null){S.error='먼저 초기 기준원금을 확인해 주세요.';render();return}if(kind.value==='STRATEGY_ALLOCATION_OUT'&&v>row.capital){S.error='회수 금액이 현재 전략 기준원금을 초과합니다.';render();return}await write({command:'event',event:{id:crypto.randomUUID(),kind:kind.value,account:account.value,strategy:'NASDAQ_SYSTEM',amount_krw:v,at:at.value+(at.value.length===16?':00':'')+'+09:00',note:(kind.value==='STRATEGY_OPENING'?'':'[기준원금:'+String(row.capital)+'] ')+note.value}})};
 detail.append(form);const confirmed=(S.book.strategy_capital_adjustments_v1||[]).filter(e=>IDS.includes(e.account));if(confirmed.length)detail.append(table(['기준일','계좌','유형','금액','근거'],confirmed.map(e=>[e.effective_date_kst,NAMES[e.account],'추가 편입',won(e.amount_krw),'기존 확정 기록 · '+(e.reason||'')])));const labels={STRATEGY_OPENING:'초기 확정',STRATEGY_ALLOCATION_IN:'추가 편입',STRATEGY_ALLOCATION_OUT:'회수'};const events=(S.book.events||[]).filter(e=>labels[e.kind]);if(events.length)detail.append(table(['시각','계좌','유형','금액','근거','정정'],events.slice(-30).reverse().map(e=>{const cancel=el('button',e.voided_at?'취소됨':'기록 취소');cancel.disabled=S.busy||!!e.voided_at;cancel.onclick=()=>write({command:'void_event',event_id:e.id});return [e.at,NAMES[e.account],labels[e.kind],won(e.amount_krw),e.note,cancel]})));parent.append(detail)
}
function flowForm(parent,view){const detail=el('details',null,'sbFlowJournal');detail.append(el('summary','입출금·내부이체·배당·비용 원장'));const form=el('form'),kind=optionSelect([['DEPOSIT','외부 입금'],['WITHDRAWAL','외부 출금'],['TRANSFER','계좌 간 내부이체'],['DIVIDEND','배당 귀속 메모'],['FEE','수수료 귀속 메모'],['TAX','세금 귀속 메모']],'현금흐름 종류'),account=optionSelect(IDS.map(id=>[id,NAMES[id]]),'출발 또는 대상 계좌'),to=optionSelect(IDS.map(id=>[id,NAMES[id]]),'도착 계좌'),strategy=optionSelect(Object.entries(GROUPS),'귀속 전략'),amount=el('input'),at=el('input'),note=el('input');amount.type='number';amount.min='0.01';amount.step='0.01';amount.required=true;amount.placeholder='원화 금액';amount.setAttribute('aria-label','실제 원화 금액');at.type='datetime-local';at.step='1';at.required=true;const now=new Date(Date.now()+9*3600000);at.value=now.toISOString().slice(0,19);at.setAttribute('aria-label','발생시각 한국시간');note.placeholder='내역 메모';note.setAttribute('aria-label','현금흐름 메모');const submit=el('button','원장에 기록');submit.type='submit';submit.disabled=S.busy||!view.baseline_at;to.value='ISA';to.hidden=true;kind.onchange=()=>{to.hidden=kind.value!=='TRANSFER'};form.append(kind,account,to,strategy,amount,at,note,submit);form.onsubmit=async e=>{e.preventDefault();const event={id:crypto.randomUUID(),kind:kind.value,account:account.value,from_account:account.value,to_account:to.value,strategy:strategy.value,amount_krw:Number(amount.value),at:at.value+(at.value.length===16?':00':'')+'+09:00',note:note.value};await write({command:'event',event});if(!S.error){amount.value='';note.value=''}};detail.append(el('p','실제 입출금만 기록해 주세요. 내부이체는 한 번만 입력합니다. 배당·비용 메모는 전략 귀속용이며 전체 순자산 손익에 다시 더하거나 빼지 않습니다. 체결 수수료는 체결 원장에 포함되므로 여기에서 중복 입력하지 않습니다.','sbNote'),form);const events=S.book.events||[];if(events.length)detail.append(table(['시각','유형','계좌','원화','메모','정정'],events.slice(-20).reverse().map(e=>{const cancel=el('button',e.voided_at?'취소됨':'기록 취소');cancel.disabled=S.busy||!!e.voided_at;cancel.onclick=()=>write({command:'void_event',event_id:e.id});return [e.at,e.kind,e.kind==='TRANSFER'?NAMES[e.from_account]+' → '+NAMES[e.to_account]:NAMES[e.account],won(e.amount_krw),e.note,cancel]})));parent.append(detail)}
function checkedBook(out,requireReady=false){
 const book=out?.book;if(!book||typeof book!=='object'||Array.isArray(book))throw Error('전략 원장 응답 누락');
 if(requireReady||S.loaded)requireRestoredStrategyBook(book);
 if(S.loaded)assertImmutableStrategyAnchor(S.book,book);
 return book;
}
async function write(body){if(S.busy)return;S.busy=true;S.error='';render();try{const out=await request('/strategy/record',body);S.book=checkedBook(out,true);S.recorded.add(S.book.latest_snapshot_id)}catch(e){S.error='원장 기록: '+e.message}finally{S.busy=false;render()}}
async function load(force=false){if(S.busy||S.ledgerBusy)return;S.busy=true;S.error='';render();try{
 if(force){const bridge=root.__JJOONI_LIVE_BRIDGE;if(!bridge?.refreshAccounts)throw Error('계좌 최신화 연결 대기');await bridge.refreshAccounts()}
 const out=await request('/strategy/read',{read_mode:'book'});const nextBook=requireRestoredStrategyBook(checkedBook(out));
 // A missing private P0 anchor is a source outage, never permission to initialize it anew.
 S.book=checkedBook({book:nextBook},true);S.loaded=true;
 // Paint saved basis before historical ledger I/O. Recent broker trades are
 // already merged by render; quantity reconciliation still rejects gaps.
 if(out.ledger?.status!=='DEFERRED')S.ledger=out.ledger||{};
 render();
 if(out.ledger?.status==='DEFERRED'){
  S.ledgerBusy=true;
  void (async()=>{
   const [history,master]=await Promise.allSettled([
    request('/strategy/read',{read_mode:'ledger',refresh:force}),
    request('/strategy/read',{read_mode:'master',refresh:force})
   ]);
   if(history.status==='fulfilled')S.ledger=history.value.ledger||{};
   else S.error='체결 원장 갱신: '+history.reason.message;
   if(master.status==='fulfilled')S.masterActivity=master.value.master_activity||{status:'UNAVAILABLE'};
   else S.masterActivity={status:'UNAVAILABLE',error_type:String(master.reason?.message||'MASTER_READ_FAILED')};
   S.ledgerBusy=false;render();
  })();
 }
}catch(e){S.error='전략 원장 조회: '+e.message}finally{S.busy=false;render()}}
function visible(){return (box?.isConnected&&box.getClientRects().length>0)||[...document.querySelectorAll('.ctStrategySleeve')].some(x=>x.getClientRects().length>0)}
async function boot(){if(!root.__JJOONI_LIVE_READY||!ensure())return;render();if(!visible())return;if(!S.loaded)return load();const id=root.__JJOONI_CANONICAL_SSOT?.snapshot_id;if(id&&!S.recorded.has(id)&&!S.busy)await write({command:'observe'})}
document.addEventListener('jjooni:tripod-daily-verified',render);document.addEventListener('jjooni:live-applied',boot);document.addEventListener('jjooni:public-market-loaded',()=>setTimeout(render,100));document.addEventListener('click',e=>{if(e.target.closest?.('.tab[data-tab="tripod"],.tab[data-tab="compare"],.tab[data-tab="overview"],.tab[data-tab="accounts"],.tab[data-tab="performance"]'))setTimeout(boot,100)});root.addEventListener('resize',()=>{if(box?.isConnected)render()},{passive:true});
// Legacy and desktop renderers can replace account cards after a live event.
let sleeveQueued=false;new MutationObserver(mutations=>{if(sleeveQueued||!mutations.some(m=>(m.target.closest?.('.ctAcct,.ctA8Card,.ctP8Card')&&!m.target.closest?.('.ctStrategySleeve'))||[...m.addedNodes].some(x=>x.nodeType===1&&(x.matches?.('.ctAcct,.ctA8Card,.ctP8Card')||x.querySelector?.('.ctAcct,.ctA8Card,.ctP8Card')))))return;sleeveQueued=true;queueMicrotask(()=>{sleeveQueued=false;accountSleeves();if(!S.loaded&&!S.busy&&visible())boot()})}).observe(document.documentElement,{childList:true,subtree:true});boot();
})(typeof window==='object'?window:globalThis);

