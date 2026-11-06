(function () {
  'use strict';
  const host = document.getElementById('tripodComparison');
  if (!host) return;
  const core = window.JjooniTripodComparisonCore;
  const meta = {
    standard: ['표준 TRI-POD', '#174ea6'], jjooni: ['쭈니 TRI-POD', '#d33779'],
    ndx: ['Nasdaq-100', '#657184'], qqq: ['QQQ', '#008473'],
    qld: ['QLD', '#ae6208'], tqqq: ['TQQQ', '#7952b3']
  };
  const pod = {TRIPOD: ['TRI', '#7d50bf'], BIPOD: ['BI', '#2965bc'],
    MONOPOD: ['MONO', '#007e75'], NOPOD: ['NO', '#758195']};
  const range = ['1M', '3M', '6M', 'YTD', '1Y', '3Y', 'MAX'];
  const esc = value => String(value).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const format = (value, suffix = '') => value == null ? '—' :
    value.toLocaleString('ko-KR', {maximumFractionDigits: 2, minimumFractionDigits: 2}) + suffix;
  const $ = selector => host.querySelector(selector);
  const hidden = new Set();
  let history, loadedAt, pending, retryAfter = 0, priceChart, ddChart;

  host.innerHTML = `
    <style>
    #tripodComparison .tc-controls{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:12px 0}
    #tripodComparison select{border:1px solid #ccd7e5;border-radius:8px;background:#fff;color:#18283e;padding:7px;min-height:40px;font:inherit}
    #tripodComparison .tc-legend{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
    #tripodComparison .tc-legend button{border:1px solid #d7e0eb;border-radius:7px;background:#fff;color:#18283e;padding:6px 9px;min-height:38px;cursor:pointer;font:inherit}
    #tripodComparison .tc-legend button[aria-pressed=false]{opacity:.5;text-decoration:line-through}
    #tripodComparison .tc-swatch{display:inline-block;width:11px;height:4px;vertical-align:middle;margin-right:5px;border-radius:4px}
    #tripodComparison .tc-chart{position:relative;height:clamp(255px,45vw,425px);margin:8px 0 20px}
    #tripodComparison .tc-dd{height:clamp(210px,32vw,310px)}
    #tripodComparison .tc-overflow{overflow:auto}
    #tripodComparison table{width:100%;min-width:670px;font-size:12px;text-align:right;white-space:nowrap}
    #tripodComparison td:first-child,#tripodComparison th:first-child{text-align:left}
    #tripodComparison .tc-strip{display:grid;grid-template-columns:95px minmax(0,1fr);gap:8px;align-items:center;margin:8px 0;font-size:12px}
    #tripodComparison .tc-segments{display:flex;min-width:0;height:18px;overflow:hidden;border-radius:5px;background:#eef3f8}
    #tripodComparison .tc-segments span{min-width:0;overflow:hidden;text-align:center;color:#fff;font-size:10px;line-height:18px}
    </style>
    <h3>전략 비교 차트</h3>
    <p class="meta" id="tcStatus" role="status">미국 완료 거래일의 비교 데이터를 불러오는 중입니다.</p>
    <div id="tcBody" hidden>
      <div class="tc-controls">
        <label>기간 <select id="tcRange">${range.map(r => '<option' + (r === '1Y' ? ' selected' : '') + '>' + r + '</option>').join('')}</select></label>
        <label>기준 <select id="tcMode"><option value="normalized">정규화 · 시작값 100</option><option value="actual">실제 지수 / 가격</option></select></label>
        <label>표시 <select id="tcGroup"><option value="all">전체</option><option value="strategy">전략만</option><option value="etf">ETF만</option></select></label>
        <label><input id="tcShowDD" type="checkbox" checked> 드로우다운</label>
        <label><input id="tcShowPods" type="checkbox" checked> 상태 띠</label>
      </div>
      <div class="tc-legend" id="tcLegend" aria-label="차트 범례"></div>
      <div class="tc-chart"><canvas id="tcPrice" role="img" aria-label="두 TRI-POD 전략과 Nasdaq-100 및 ETF 3종의 누적 성과"></canvas></div>
      <div id="tcPods">
        <h3>포지션 히스토리</h3>
        <div id="tcStrips"></div><div class="meta" id="tcDay">차트를 가리키거나 터치하면 해당 거래일의 포지션을 표시합니다.</div>
      </div>
      <div id="tcDrawdown"><h3>드로우다운 비교</h3><div class="tc-chart tc-dd"><canvas id="tcDD" role="img" aria-label="선택 기간 고점 대비 낙폭"></canvas></div></div>
      <h3>전략 vs ETF 성과비교</h3>
      <div class="tc-overflow"><table><thead><tr><th scope="col">시리즈</th><th scope="col">기간 수익률</th><th scope="col">CAGR</th><th scope="col">MDD</th><th scope="col">변동성</th><th scope="col">샤프</th><th scope="col">표준 대비</th><th scope="col">쭈니 대비</th></tr></thead><tbody id="tcMetrics"></tbody></table></div>
      <p class="meta">Yahoo Finance 미국 완료 일봉 · NDX 가격지수 · ETF 배당·분할 조정 종가 · USD 기준. 실제 가격 모드는 ETF 종가(USD), NDX(pt), 전략 모의 NAV(시작값 100)를 각 축에 표시합니다.</p>
      <p class="meta">공식 목표 변경 및 쭈니 분할매수·손절은 신호 다음 거래일 종가 체결로 가정합니다. 쭈니의 노팟 QLD 투입은 진입 시 전략자산의 5%p씩 최대 25%입니다. 현금 수익률 0% · 수수료·세금·환율 미반영 · 샤프 무위험수익률 0% · CAGR은 1년 이상 표시.</p>
    </div>`;

  function selectRows() {
    const end = history.at(-1).date;
    const start = new Date(end + 'T00:00:00Z');
    const period = $('#tcRange').value;
    if (period === 'MAX') return history;
    if (period === 'YTD') start.setUTCMonth(0, 1);
    else {
      const day = start.getUTCDate();
      const months = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12, '3Y': 36 }[period];
      start.setUTCMonth(start.getUTCMonth() - months, 1);
      const lastDay = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0)).getUTCDate();
      start.setUTCDate(Math.min(day, lastDay));
    }
    const date = start.toISOString().slice(0, 10);
    // Use the preceding close when the calendar boundary is a market holiday.
    const first = history.findLastIndex(row => period === 'YTD' ? row.date < date : row.date <= date);
    return history.slice(Math.max(0, first));
  }

  function strips(rows) {
    return ['표준', '쭈니'].map((name, i) => {
      const segments = [];
      for (const row of rows) {
        const [stage, baseColor] = pod[row.applied];
        const pct = i && row.investedPct;
        const label = pct ? 'NO · QLD ' + pct + '%' : i && row.stopFilled ? 'NO · 손절' : stage;
        const color = pct ? '#ab356a' : i && row.stopFilled ? '#9a351e' : baseColor;
        const last = segments.at(-1);
        if (last?.label === label) {
          last.count++;
          last.end = row.date;
        } else segments.push({label, color, count: 1, start: row.date, end: row.date});
      }
      return '<div class="tc-strip"><b>' + name + '</b><div class="tc-segments">' +
        segments.map(s => `<span style="flex:${s.count} 1 0%;background:${s.color}" title="${esc(s.start + ' ~ ' + s.end + ' · ' + s.label)}">${esc(s.label)}</span>`).join('') + '</div></div>';
    }).join('');
  }

  function render() {
    if (!history?.length) return;
    if (typeof Chart !== 'function') {
      $('#tcStatus').textContent = '차트 모듈을 불러오지 못했습니다. 페이지를 새로고침해 주세요.';
      return;
    }
    const rows = selectRows();
    const stats = Object.fromEntries(core.keys.map(k => [k, core.summarize(rows, k)]));
    const display = $('#tcGroup').value;
    const actual = $('#tcMode').value === 'actual';
    const visible = core.keys.filter((_, i) => display === 'all' || (display === 'strategy' ? i < 2 : i >= 3));
    $('#tcLegend').innerHTML = visible.map(k =>
      `<button type="button" data-series="${k}" aria-pressed="${!hidden.has(k)}"><span class="tc-swatch" style="background:${meta[k][1]}"></span>${meta[k][0]}</button>`).join('');
    $('#tcMetrics').innerHTML = core.keys.map(k => {
      const m = stats[k];
      return '<tr><th scope="row">' + meta[k][0] + '</th>' +
        [format(m.total, '%'), format(m.cagr, '%'), format(m.mdd, '%'), format(m.vol, '%'),
          format(m.sharpe), k === 'standard' ? '—' : format(m.total - stats.standard.total, '%p'),
          k === 'jjooni' ? '—' : format(m.total - stats.jjooni.total, '%p')]
          .map(value => '<td>' + esc(value) + '</td>').join('') + '</tr>';
    }).join('');
    const data = typeof DATA !== 'undefined' ? DATA : null;
    const expected = data?.us_completed_session_date;
    const short = $('#tcRange').value === '3Y' &&
      Date.parse(loadedAt) - Date.parse(rows[0].date) < 365.2425 * 3 * 86400000 - 5 * 86400000;
    $('#tcStatus').textContent = rows[0].date + ' ~ ' + loadedAt + ' · ' + rows.length.toLocaleString('ko-KR') + ' 거래일'
      + (short ? ' · 3년 요청 중 공통 데이터가 확보된 기간 표시' : '')
      + (expected && expected > loadedAt ? ' · ETF 비교 데이터 갱신 대기 (공식 완료세션 ' + expected + ')' : '');
    $('#tcBody').hidden = false;
    $('#tcDrawdown').hidden = !$('#tcShowDD').checked;
    $('#tcPods').hidden = !$('#tcShowPods').checked;
    $('#tcStrips').innerHTML = strips(rows);
    $('#tcDay').textContent = '차트를 가리키거나 터치하면 해당 거래일의 포지션을 표시합니다.';

    function draw(canvas, drawdown) {
      const axes = {x: {ticks: {maxTicksLimit: 6, maxRotation: 0}}, y: {title: {display: true,
        text: drawdown ? '고점 대비 %' : actual ? 'ETF USD' : '시작값 100'},
        display: drawdown || !actual || visible.some(k => ['qqq','qld','tqqq'].includes(k) && !hidden.has(k))}};
      if (actual && !drawdown) {
        axes.index = {position: 'right', title: {display: true, text: 'NDX pt'}, grid: {drawOnChartArea: false}, display: 'auto'};
        axes.nav = {position: 'right', title: {display: true, text: '모의 NAV'}, grid: {drawOnChartArea: false}, display: 'auto'};
      }
      return new Chart(canvas, {
        type: 'line',
        data: {labels: rows.map(row => row.date), datasets: visible.map(k => ({
          label: meta[k][0], borderColor: meta[k][1], backgroundColor: meta[k][1], hidden: hidden.has(k),
          borderWidth: k === 'standard' || k === 'jjooni' ? 2.5 : 1.35,
          borderDash: k === 'standard' ? [6, 4] : [], pointRadius: 0,
          yAxisID: actual && !drawdown ? k === 'ndx' ? 'index' : ['standard','jjooni'].includes(k) ? 'nav' : 'y' : 'y',
          data: drawdown ? stats[k].drawdowns : actual ? rows.map(row => row.actual[k]) : stats[k].values
        }))},
        options: {animation: false, maintainAspectRatio: false,
          interaction: {mode: 'index', intersect: false}, scales: axes,
          plugins: {legend: {display: false}, tooltip: {callbacks: {
            label: ctx => ctx.dataset.label + '  ' + format(ctx.parsed.y, drawdown ? '%' : ''),
            afterBody: items => {
              const row = rows[items[0]?.dataIndex];
              if (!row) return '';
              const stage = pod[row.applied][0];
              const extra = row.investedPct ? ' · QLD ' + row.investedPct + '%' : row.stopFilled ? ' · 손절 체결' : '';
              const detail = '표준 ' + stage + ' / 쭈니 ' + stage + extra;
              $('#tcDay').textContent = row.date + ' · ' + detail + ' · 당일 공식 신호 ' + pod[row.stage][0];
              return detail;
            }
          }}}}
      });
    }
    priceChart?.destroy();
    ddChart?.destroy();
    priceChart = draw($('#tcPrice'), false);
    ddChart = $('#tcShowDD').checked ? draw($('#tcDD'), true) : null;
  }

  function load() {
    const data = typeof DATA !== 'undefined' ? DATA : null;
    if (history && (!data?.us_completed_session_date || loadedAt >= data.us_completed_session_date)) {
      if (!priceChart) render();
      return;
    }
    if (pending || Date.now() < retryAfter) return;
    pending = window.JjooniDataReads.read('./data/tripod-comparison.json').then(payload => {
      if (payload.session === loadedAt) return;
      const rows = core.simulate(payload, window.JjooniTripodCore);
      if (rows.length < 2) throw Error('비교 가능한 완료 거래일이 부족합니다.');
      history = rows;
      loadedAt = payload.session;
    }).catch(() => {
      if (!history) $('#tcStatus').textContent = '아직 공통 비교 일봉을 불러오지 못했습니다. 잠시 후 이 탭을 다시 열면 재시도합니다.';
    }).finally(() => {
      pending = null;
      retryAfter = Date.now() + 15000;
      if (history) render();
    });
  }
  host.addEventListener('change', render);
  host.addEventListener('click', event => {
    const button = event.target.closest('button[data-series]');
    if (!button) return;
    const key = button.dataset.series;
    if (hidden.has(key)) hidden.delete(key); else hidden.add(key);
    render();
    $('#tcLegend').querySelector('[data-series="' + key + '"]')?.focus();
  });
  const panel = document.getElementById('jjooni-tripod');
  new MutationObserver(() => { if (panel.classList.contains('on')) load(); })
    .observe(panel, {attributes: true, attributeFilter: ['class']});
  if (panel.classList.contains('on')) load();
  new MutationObserver(() => { if (panel.classList.contains('on')) load(); })
    .observe(document.getElementById('jjooniTripodRoot'), {childList: true});
})();
