/* JJOONI-style TRI-POD: read-only NO-POD dip overlay. No account/order API. */
(function (root) {
  'use strict';
  const POLICY = Object.freeze({
    triggerDailyPct: -1.5,
    tranchePct: 5,
    capPct: 25,
    stopFromNoPodEntryPct: -12,
    instrument: 'QLD',
    execution: 'NEXT_COMPLETED_SESSION_CLOSE',
    version: 'JJOONI_NOPOD_QLD_V1'
  });
  const finite = v => v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
  const cashTarget = row => String(row && row.target || '') === '현금 100%';
  const stage = row => {
    const x = String(row && row.target || '');
    if (x === '현금 100%') return 'NOPOD';
    if (x === 'TQQQ 100%') return 'TRIPOD';
    if (x === 'QQQ 50% + QLD 50%') return 'BIPOD';
    if (x === 'QQQ 100%') return 'MONOPOD';
    return 'UNKNOWN';
  };
  function evaluate(data) {
    const t = data && data.tripod_latest || {};
    const session = String(data && data.us_completed_session_date || '');
    const date = String(t.session_date || t.date || '');
    const latestIndex = finite(t.ndx);
    const valid = t.ok === true && session && date === session &&
      latestIndex !== null && latestIndex > 0 && finite(t.ma250) > 0 &&
      finite(t.vix10) !== null && Number(t.vix_window_count) === 10 &&
      ['상승', '하락'].includes(t.regime) && stage(t) !== 'UNKNOWN';
    const basic = {policy: POLICY, session, date, officialTarget: t.target || null,
      officialStage: stage(t), valid: !!valid, events: []};
    if (!valid) return Object.assign(basic, {status: 'UNCERTIFIED'});
    const rows = (Array.isArray(data.tripod_history) ? data.tripod_history : [])
      .filter(x => /^\d{4}-\d{2}-\d{2}$/.test(String(x && x.date || '')) &&
        x.date <= session && finite(x.ndx) > 0 && stage(x) !== 'UNKNOWN')
      .map(x => ({date: x.date, ndx: Number(x.ndx), target: x.target}))
      .sort((a,b) => a.date.localeCompare(b.date));
    // Published certified signal overrides any older copy at the same date.
    const latest = {date, ndx: latestIndex, target: t.target};
    const ix = rows.findIndex(x => x.date === date);
    if (ix >= 0) rows[ix] = latest; else rows.push(latest);
    rows.sort((a,b) => a.date.localeCompare(b.date));
    const deduped = rows.filter((x,i) => i === rows.length-1 || x.date !== rows[i+1].date);
    if (deduped.length < 2 || deduped[deduped.length-1].date !== date)
      return Object.assign(basic, {status: 'INSUFFICIENT_HISTORY'});
    let cycle = null, lastCycle = null, previous = null;
    const events = [];
    function record(day, type, text) {
      events.push({date: day, type, text});
      if (events.length > 120) events.shift();
    }
    for (const row of deduped) {
      const noPod = cashTarget(row);
      const dailyPct = previous && previous.ndx > 0 ?
        (row.ndx / previous.ndx - 1) * 100 : null;
      if (!noPod) {
        if (cycle) {
          record(row.date, 'RETURN', '공식 ' + stage(row) + ' 복귀 · 보조 전략 종료');
          lastCycle = Object.assign({}, cycle, {exitDate: row.date});
          cycle = null;
        }
        previous = row;
        continue;
      }
      if (!cycle) {
        // If historical data begins in cash, the true entry anchor is unknowable.
        const anchored = Boolean(previous && !cashTarget(previous));
        cycle = {entryDate: row.date, entryNdx: anchored ? row.ndx : null,
          anchorVerified: anchored, stopNdx: anchored ? row.ndx * 0.88 : null,
          boughtPct: 0, buyCount: 0, pending: null, stopped: false,
          stopDate: null, triggers: 0};
        if (anchored) record(row.date, 'ENTER', 'NO-POD 진입 · NDX 종가 ' + row.ndx.toFixed(2) + ' 기준 고정');
      }
      if (cycle.anchorVerified && !cycle.stopped) {
        // Stop before executing yesterday's pending buy; stop cancels it.
        if (row.ndx < cycle.stopNdx) {
          cycle.stopped = true;
          cycle.stopDate = row.date;
          cycle.boughtPct = 0;
          cycle.pending = null;
          record(row.date, 'STOP', 'NDX 진입 기준 -12% 이탈 · QLD 전량 정리 가정, 사이클 재매수 금지');
        } else {
          if (cycle.pending && cycle.pending.signalDate < row.date) {
            cycle.boughtPct = Math.min(POLICY.capPct, cycle.boughtPct + POLICY.tranchePct);
            cycle.buyCount += 1;
            record(row.date, 'BUY', '전일 신호 실행 가정 · QLD +5%p, 누적 투입 ' + cycle.boughtPct + '%');
            cycle.pending = null;
          }
          if (dailyPct !== null && dailyPct <= POLICY.triggerDailyPct &&
              cycle.boughtPct < POLICY.capPct && !cycle.pending) {
            cycle.pending = {signalDate: row.date, pct: POLICY.tranchePct};
            cycle.triggers += 1;
            record(row.date, 'SIGNAL', 'NDX 일간 ' + dailyPct.toFixed(2) + '% · 다음 거래일 종가 QLD 5%p 대기');
          }
        }
      }
      previous = row;
    }
    const today = deduped[deduped.length-1];
    const prior = deduped[deduped.length-2];
    const dailyPct = prior && prior.ndx > 0 ? (today.ndx / prior.ndx - 1) * 100 : null;
    return Object.assign(basic, {
      status: !cycle ? 'BASE_STRATEGY' : !cycle.anchorVerified ? 'UNVERIFIED_ANCHOR' :
        cycle.stopped ? 'STOPPED' : 'ACTIVE',
      active: Boolean(cycle), cycle, lastCycle, events: events.slice(-16),
      latestNdx: today.ndx, dailyPct,
      nextAction: !cycle ? '기존 송팀장 TRI-POD 목표 유지' :
        !cycle.anchorVerified ? 'NO-POD 최초 진입일 데이터 확보 전 판정 보류' :
        cycle.stopped ? 'NO-POD 종료 전 추가매수 금지' :
        cycle.pending ? '다음 미국 거래일 종가 QLD 5%p 매수 가정 (자동주문 아님)' :
        cycle.boughtPct >= POLICY.capPct ? '누적 25% 한도 도달 · 추가매수 없음' :
        'NDX 일간 -1.5% 이하 하락 시 다음 거래일 종가 분할매수 대기'
    });
  }
  root.JjooniTripodCore = {POLICY, stage, evaluate};
  if (typeof module !== 'undefined' && module.exports) module.exports = {POLICY, stage, evaluate};
  if (typeof document === 'undefined') return;
  const esc = x => String(x == null ? '' : x).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (x, places=2) => finite(x) === null ? '—' :
    Number(x).toLocaleString('ko-KR', {minimumFractionDigits: places, maximumFractionDigits: places});
  const stageName = x => ({TRIPOD:'트라이팟 3배',BIPOD:'바이팟 1.5배',
    MONOPOD:'모노팟 1배 적용형',NOPOD:'노팟 현금',UNKNOWN:'확인 필요'}[x] || '확인 필요');
  const card = (label, value, detail='') =>
    '<div class="jtMetric"><span>'+esc(label)+'</span><b>'+esc(value)+'</b><small>'+esc(detail)+'</small></div>';
  const css = String.raw`
  #jjooni-tripod .jtIntro{margin-bottom:12px;font-size:12px;line-height:1.7;color:#526781}
  #jjooni-tripod .jtHead{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}
  #jjooni-tripod .jtPill{border-radius:99px;background:#e6f1ff;color:#064883;padding:5px 10px;font-size:11px;font-weight:900}
  #jjooni-tripod .jtGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}
  #jjooni-tripod .jtMetric{padding:13px;border:1px solid #e3ebf5;border-radius:12px;background:#f8fbff;min-width:0}
  #jjooni-tripod .jtMetric span,#jjooni-tripod .jtMetric small{display:block;color:#68819c;font-size:11px;line-height:1.5}
  #jjooni-tripod .jtMetric b{display:block;font-size:21px;font-weight:950;overflow-wrap:anywhere;margin:5px 0}
  #jjooni-tripod .jtPod{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
  #jjooni-tripod .jtPod span{border-radius:10px;background:#f1f4f8;color:#5d7186;padding:8px 10px;font-size:11px;font-weight:800}
  #jjooni-tripod .jtPod span.on{background:#083d74;color:#fff}
  #jjooni-tripod .jtNote{border-left:3px solid #4173b7;background:#f3f8ff;border-radius:8px;padding:12px;font-size:12px;line-height:1.7}
  #jjooni-tripod .jtLog{margin-top:12px}
  #jjooni-tripod .jtEvent{display:grid;grid-template-columns:90px 88px 1fr;gap:8px;padding:10px 4px;border-bottom:1px solid #eef1f5;line-height:1.4;font-size:12px}
  #jjooni-tripod .jtEvent em{font-style:normal;font-weight:900;color:#0b568f}
  #jjooni-tripod .jtDisabled{color:#9a3412;background:#fff7ed;border-left-color:#f97316}
  @media(max-width:800px){#jjooni-tripod .jtGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:430px){#jjooni-tripod .jtMetric b{font-size:17px}#jjooni-tripod .jtEvent{grid-template-columns:76px 62px 1fr;font-size:10px}}
  `;
  function render() {
    const host = document.getElementById('jjooniTripodRoot');
    if (!host) return;
    const data = typeof DATA !== 'undefined' ? DATA : null;
    if (!data) { host.textContent = '시장 완료세션 데이터를 불러오는 중입니다.'; return; }
    const m = evaluate(data);
    const c = m.cycle;
    const label = m.status === 'UNCERTIFIED' ? '완료세션 검증 대기' :
      m.status === 'INSUFFICIENT_HISTORY' ? '히스토리 부족' :
      m.status === 'UNVERIFIED_ANCHOR' ? '노팟 진입일 미확인' :
      m.status === 'STOPPED' ? '손절 후 재진입 금지' :
      m.status === 'ACTIVE' ? '쭈니 보조전략 가동 구간' : '공식 TRI-POD 유지';
    const pods = ['TRIPOD','BIPOD','MONOPOD','NOPOD']
      .map(x => '<span class="' + (m.officialStage === x ? 'on' : '') + '">' + stageName(x) + '</span>').join('');
    const foot = '<p class="jtIntro">송팀장 TRI-POD 엔진은 변경하지 않습니다. 노팟 구간에만 적용하는 쭈니 스타일 QLD 분할매수 연구 오버레이입니다. '
      + '아래 비중은 <b>기준투자금 대비 누적 투입 가정치</b>이며 현재 평가비중·실현수익률·실계좌 잔고가 아닙니다.</p>';
    const safe = m.valid && m.status !== 'INSUFFICIENT_HISTORY' && m.status !== 'UNVERIFIED_ANCHOR';
    const metrics = [
      card('공식 전략 단계',stageName(m.officialStage), m.date + ' 미국 완료세션'),
      card('나스닥100 일간 변화', safe && m.dailyPct !== null ? (m.dailyPct > 0 ? '+' : '')+fmt(m.dailyPct)+'%' : '—', '하락 트리거 ≤ -1.5%'),
      card('QLD 누적 투입 가정',safe && c ? String(c.boughtPct)+'%' : (safe ? '0%' : '—'),'기준원금 대비 · 최대 25%'),
      card('다음 거래일 매수 대기',safe && c && c.pending ? '5%' : (safe ? '없음' : '—'),'신호 다음 완료거래일 종가 가정'),
      card('NO-POD 진입일',safe && c ? c.entryDate : '—', '진입일 NDX 종가 고정'),
      card('NO-POD 기준 NDX',safe && c ? fmt(c.entryNdx) : '—','종가 기준'),
      card('손절 판정선',safe && c ? fmt(c.stopNdx) : '—','NDX < 진입 종가 × 0.88'),
      card('QLD 누적 분할 횟수',safe && c ? String(c.buyCount)+'회' : (safe ? '0회' : '—'),'매회 기준원금 5%p')
    ].join('');
    const flags = !safe ?
      '<div class="jtNote jtDisabled">확정 일봉·전환 이력이 검증되지 않아 매수/손절 가격을 임의 생성하지 않습니다.</div>' :
      '<div class="jtNote"><b>다음 행동:</b> '+esc(m.nextAction)+
      '<div>판정은 NDX 미국 완료 일봉 기준 · 손절은 진입일 종가 대비 -12% 미만 · 손절 후 같은 NO-POD 사이클 재매수 금지</div></div>';
    const log = (m.events || []).slice().reverse().map(e =>
      '<div class="jtEvent"><b>'+esc(e.date)+'</b><em>'+esc(e.type)+'</em><span>'+esc(e.text)+'</span></div>').join('');
    host.innerHTML = '<div class="card"><div class="jtHead"><h3>쭈니 스타일 TRI-POD · NO-POD 바이더딥</h3><span class="jtPill">'+esc(label)+'</span></div>'
      + foot + '<div class="jtPod">'+pods+'</div><div class="jtGrid">'+metrics+'</div>'
      + flags + '<div class="jtLog"><h3>시뮬레이션 신호 이력</h3>'
      + (log || '<p class="meta">현재 조회 가능한 전환·분할매수 이벤트가 없습니다.</p>') + '</div>'
      + '<p class="meta">전략 v1 · QLD 5%p × 최대 5회 · NDX 일간 ≤ -1.5% · 다음 완료세션 종가 매수 가정 · NO-POD 종료 즉시 공식 목표로 복귀. '
      + 'QLD 실거래 종가 및 수수료·세금·환율은 반영하지 않으므로 이 화면은 수익률 백테스트가 아닙니다. 자동주문·계좌 변경 없음.</p></div>';
  }
  const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);
  const tabs = document.getElementById('tabs');
  if (tabs) tabs.addEventListener('click', e => {
    const tab = e.target && e.target.closest && e.target.closest('button[data-tab]');
    if (tab && tab.dataset.tab === 'jjooni-tripod') setTimeout(render, 0);
  });
  if (typeof root.render === 'function' && !root.render.__jjooniTripodHooked) {
    const base = root.render;
    const wrapper = function () { const out=base.apply(this,arguments); render(); return out; };
    wrapper.__jjooniTripodHooked=true; root.render=wrapper;
  }
  render();
})(typeof window === 'undefined' ? globalThis : window);
