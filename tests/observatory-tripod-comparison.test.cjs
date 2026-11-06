const {test} = require('node:test');
const assert = require('node:assert/strict');
const core = require('../market-observatory/tripod-comparison-core.js');
const official = require('../market-observatory/jjooni-tripod-v1.js');
const tri = 'TQQQ 100%', bi = 'QQQ 50% + QLD 50%', cash = '현금 100%';
const row = (day, ndx, target, qld = 100, tqqq = 100, ma = 100) =>
  ['2026-10-' + String(day).padStart(2, '0'), ndx, ma, target, [100, 100], [qld, qld], [tqqq, tqqq]];
const run = (...rows) => core.simulate({schema: 'JJOONI_TRIPOD_COMPARISON_V1', session: rows.at(-1)[0], rows}, official);
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-10, `${actual} != ${expected}`);

test('next-close fills, fixed official entry threshold, and stop lock', () => {
  const r = run(row(1, 100, tri), row(2, 94, cash, 98, 90),
    row(5, 93, cash, 96, 80), row(6, 84, cash, 80, 80, 120),
    row(7, 83, cash, 70), row(8, 81, cash, 60),
    row(9, 79, cash, 50), row(12, 90, bi, 60), row(13, 93, bi, 70));
  assert.deepEqual(r.map(x => x.applied), ['TRIPOD', 'TRIPOD', 'NOPOD', 'NOPOD', 'NOPOD', 'NOPOD', 'NOPOD', 'NOPOD', 'BIPOD']);
  assert.deepEqual(r.map(x => x.investedPct), [0, 0, 5, 5, 10, 0, 0, 0, 0]);
  assert.equal(r[4].stopFilled, false);
  assert.equal(r[5].stopFilled, true);
  assert.equal(r[8].stopFilled, false);
  near(r[2].values.standard, 80);
  near(r[2].values.jjooni, 80);
  near(r[5].values.jjooni, 72 + 4 * 60 / 96 + 4 * 60 / 70);
  near(r[8].values.jjooni, r[5].values.jjooni);
});

test('QLD stops at five tranches and the 1.5 percent boundary is inclusive', () => {
  const bars = [row(1, 100, tri, 100, 100, 80)];
  let ndx = 100;
  for (let day = 2; day < 12; day++) {
    ndx *= 0.985;
    bars.push(row(day, ndx, cash, 100, 100, 80));
  }
  const r = run(...bars);
  assert.deepEqual(r.map(x => x.investedPct), [0, 0, 5, 10, 15, 20, 25, 25, 25, 25, 25]);
});

test('unknown opening NO-POD cycle is omitted and values rebase on the selected window', () => {
  const r = run(row(1, 95, cash), row(2, 100, tri), row(5, 98, tri, 100, 125),
    row(6, 97, tri, 100, 100));
  assert.equal(r[0].date, '2026-10-02');
  const m = core.summarize(r.slice(1), 'standard');
  assert.deepEqual(m.values, [100, 80]);
  near(m.mdd, -20);
  near(m.total, -20);
  assert.equal(m.cagr, null);
});
