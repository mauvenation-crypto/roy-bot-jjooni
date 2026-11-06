(function (root) {
  'use strict';
  const keys = ['standard', 'jjooni', 'ndx', 'qqq', 'qld', 'tqqq'];
  const noPod = 'NOPOD';
  const targets = {
    TRIPOD: [0, 0, 1], BIPOD: [0.5, 0.5, 0],
    MONOPOD: [1, 0, 0], NOPOD: [0, 0, 0]
  };

  function simulate(payload, official) {
    if (payload?.schema !== 'JJOONI_TRIPOD_COMPARISON_V1' ||
        !Array.isArray(payload.rows) || payload.rows.at(-1)?.[0] !== payload.session) {
      throw Error('비교 데이터 형식 오류');
    }
    const policy = official.POLICY;
    const step = policy.tranchePct / 100;
    const cap = policy.capPct / 100;
    const stopFactor = 1 + policy.stopFromNoPodThresholdPct / 100;
    const seed = {cash: 100, shares: [0, 0, 0]};
    const rows = [];
    let standard = seed, jjooni = seed, previous = null, cycle = null;
    const value = (book, prices) => book.cash + book.shares.reduce((sum, units, i) => sum + units * prices[i], 0);
    const allocate = (nav, prices, weights) => ({
      cash: nav * (1 - weights.reduce((sum, weight) => sum + weight, 0)),
      shares: weights.map((weight, i) => nav * weight / prices[i])
    });
    for (const [date, ndx, ma250, target, ...etfs] of payload.rows) {
      const stage = official.stage({target});
      const prices = etfs.map(pair => pair[1]);
      if (!targets[stage] || ![ndx, ma250, ...etfs.flat()].every(n => Number.isFinite(n) && n > 0) ||
          etfs.length !== 3 || (previous && date <= previous.date)) throw Error('비교 일봉 검증 실패');
      if (!previous && stage === noPod) continue;

      // A signal at the prior close can only change holdings at today's close.
      const applied = previous?.stage ?? stage;
      const priorApplied = rows.at(-1)?.applied;
      const switched = priorApplied !== applied;
      if (switched) {
        standard = allocate(value(standard, prices), prices, targets[applied]);
        jjooni = allocate(value(jjooni, prices), prices, targets[applied]);
      }
      if (applied === noPod && cycle) {
        if (cycle.stopPending) {
          jjooni = allocate(value(jjooni, prices), prices, targets[noPod]);
          cycle.stopPending = false;
          cycle.stopped = true;
        } else if (cycle.buyPending) {
          if (switched) cycle.capital = value(jjooni, prices);
          const amount = Math.min(jjooni.cash, cycle.capital * step);
          jjooni.cash -= amount;
          jjooni.shares[1] += amount / prices[1];
          cycle.tranches += 1;
          cycle.buyPending = false;
        }
        if (switched && cycle.capital === null) cycle.capital = value(jjooni, prices);
      }
      const investedPct = applied === noPod && cycle && !cycle.stopped ? cycle.tranches * policy.tranchePct : 0;
      const stopFilled = applied === noPod && Boolean(cycle?.stopped);
      if (stage === noPod) {
        if (previous?.stage !== noPod) {
          cycle = {capital: null, tranches: 0, stopped: false, buyPending: false, stopPending: false,
            stop: ma250 * policy.noPodLineFactor * stopFactor};
        }
        if (!cycle.stopped && ndx < cycle.stop) {
          cycle.stopPending = true;
          cycle.buyPending = false;
        } else if (!cycle.stopped && previous &&
            ndx <= previous.ndx * (1 + policy.triggerDailyPct / 100) && cycle.tranches * step < cap) {
          cycle.buyPending = true;
        }
      } else {
        cycle = null;
      }
      const navs = {standard: value(standard, prices), jjooni: value(jjooni, prices)};
      rows.push({date, stage, applied, investedPct, stopFilled,
        values: {...navs, ndx, qqq: prices[0], qld: prices[1], tqqq: prices[2]},
        actual: {...navs, ndx, qqq: etfs[0][0], qld: etfs[1][0], tqqq: etfs[2][0]}});
      previous = {date, stage, ndx};
    }
    return rows;
  }

  function summarize(rows, key) {
    const first = rows[0].values[key];
    const values = rows.map(row => row.values[key] / first * 100);
    let high = 100;
    const drawdowns = values.map(value => {
      high = Math.max(high, value);
      return (value / high - 1) * 100;
    });
    const returns = values.slice(1).map((value, i) => value / values[i] - 1);
    const count = returns.length;
    const avg = returns.reduce((sum, x) => sum + x, 0) / count;
    const sd = count > 1 ? Math.sqrt(returns.reduce((sum, x) => sum + (x - avg) ** 2, 0) / (count - 1)) : null;
    const days = (Date.parse(rows.at(-1).date) - Date.parse(rows[0].date)) / 86400000;
    const factor = values.at(-1) / 100;
    return {values, drawdowns, total: (factor - 1) * 100,
      cagr: days >= 365 ? (factor ** (365.2425 / days) - 1) * 100 : null,
      mdd: Math.min(...drawdowns), vol: sd === null ? null : sd * Math.sqrt(252) * 100,
      sharpe: sd > 0 ? avg / sd * Math.sqrt(252) : null};
  }

  root.JjooniTripodComparisonCore = {keys, simulate, summarize};
  if (typeof module !== 'undefined' && module.exports) module.exports = root.JjooniTripodComparisonCore;
})(typeof window === 'undefined' ? globalThis : window);
