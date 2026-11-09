/* JJOONI Daily Glance — 30-second market card. Read-only; numbers come from daily-glance.json. */
(function () {
  'use strict';
  var VERSION = '20261109-glance2';
  var main = document.querySelector('main.wrap');
  if (!main || document.getElementById('dailyGlance')) return;
  var host = document.createElement('section');
  host.id = 'dailyGlance';
  host.setAttribute('aria-label', '오늘의 30초 시황');
  main.insertBefore(host, main.firstChild);

  var css = '#dailyGlance{margin:10px 0 14px;border:1px solid #d7e0eb;border-radius:12px;background:#fff;color:#18283e;font-size:13px;line-height:1.5;overflow:hidden}' +
    '#dailyGlance .dgHead{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;padding:10px 12px;cursor:pointer;background:#f6f8fb}' +
    '#dailyGlance .dgPod{font-weight:700;padding:2px 8px;border-radius:6px;color:#fff;background:#2965bc}' +
    '#dailyGlance .dgPod.NOPOD{background:#758195}#dailyGlance .dgPod.TRIPOD{background:#7d50bf}' +
    '#dailyGlance .dgTitle{font-weight:600;flex:1 1 240px;word-break:keep-all}' +
    '#dailyGlance .dgMeta{color:#5b6b80;font-size:12px}' +
    '#dailyGlance .dgBody{padding:4px 12px 12px}#dailyGlance[data-collapsed="1"] .dgBody{display:none}' +
    '#dailyGlance ul{margin:6px 0;padding-left:18px}#dailyGlance li{margin:2px 0;word-break:keep-all}' +
    '#dailyGlance .dgGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px 14px;margin-top:8px}' +
    '#dailyGlance table{width:100%;border-collapse:collapse;font-size:12px}#dailyGlance caption{text-align:left;font-weight:600;padding:2px 0}' +
    '#dailyGlance td{padding:2px 0;border-bottom:1px solid #eef2f7}#dailyGlance td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}' +
    '#dailyGlance .up{color:#c4302b}#dailyGlance .dn{color:#1f5fbf}#dailyGlance .old{color:#9aa6b5}' +
    '#dailyGlance .dgWarn{margin:6px 0;padding:6px 8px;border-radius:6px;background:#fff4e5;color:#7a4b00}' +
    '#dailyGlance .dgOk{color:#2e7d32}#dailyGlance .dgFoot{color:#7b8797;font-size:11px;margin-top:6px}';
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function num(v, d) { return v == null ? '—' : Number(v).toLocaleString('ko-KR', {minimumFractionDigits: d, maximumFractionDigits: d}); }
  function chg(item) {
    var v, unit;
    if (item.d1_pct != null) { v = item.d1_pct; unit = '%'; }
    else if (item.d1_bp != null) { v = item.d1_bp; unit = 'bp'; }
    else if (item.d1_pt != null) { v = item.d1_pt; unit = 'pt'; }
    else return '<td class="n">—</td>';
    var cls = v > 0 ? 'up' : v < 0 ? 'dn' : '';
    return '<td class="n ' + cls + '">' + (v > 0 ? '+' : '') + num(v, unit === '%' ? 2 : 1) + unit + '</td>';
  }
  function render(g) {
    var t = g.tripod || {};
    var collapsed = '0';
    try { collapsed = localStorage.getItem('dailyGlanceCollapsed') || '0'; } catch (e) { /* storage unavailable */ }
    host.setAttribute('data-collapsed', collapsed);
    var latestDates = {};
    (g.groups || []).forEach(function (grp) { grp.items.forEach(function (it) { if (it.date && it.key !== 'BTCUSD' && (!latestDates[grp.name] || it.date > latestDates[grp.name])) latestDates[grp.name] = it.date; }); });
    var tables = (g.groups || []).map(function (grp) {
      return '<table><caption>' + esc(grp.name) + '</caption>' + grp.items.map(function (it) {
        if (it.status === 'MISSING') return '<tr><td>' + esc(it.label) + '</td><td class="n old">자료 없음</td><td></td></tr>';
        var old = it.key !== 'BTCUSD' && it.date !== latestDates[grp.name] ? ' old' : '';
        var dp = it.d1_bp != null ? 3 : it.value > 1000 ? 0 : 2;
        return '<tr><td class="' + old + '">' + esc(it.label) + (old ? ' (' + esc(it.date.slice(5)) + ')' : '') + '</td><td class="n">' + num(it.value, dp) + '</td>' + chg(it) + '</tr>';
      }).join('') + '</table>';
    }).join('');
    var bc = g.brief_check || {};
    var brief = bc.status === 'MISMATCH' ? '<div class="dgWarn">⚠️ ' + esc(bc.text) + '</div>' :
      bc.status === 'MATCH' ? '<div class="dgOk">✓ ' + esc(bc.text) + '</div>' :
      bc.status === 'UNVERIFIED' ? '<div class="dgWarn">' + esc(bc.text) + '</div>' :
      bc.text ? '<div class="dgMeta">' + esc(bc.text) + '</div>' : '';
    var cons = g.consistency && g.consistency.status !== 'OK' ? '<div class="dgWarn">⚠️ TRI-POD 신호와 시세 날짜·종가가 맞지 않아 전환선 거리는 참고용입니다.</div>' : '';
    host.innerHTML =
      '<div class="dgHead" role="button" tabindex="0" aria-expanded="' + (collapsed === '1' ? 'false' : 'true') + '">' +
        '<span class="dgPod ' + esc(t.pod) + '">' + esc(t.pod) + '</span>' +
        '<span class="dgTitle">' + esc(g.headline) + '</span>' +
        '<span class="dgMeta">미국 ' + esc(g.us_session) + ' 완료장 · 30초 시황</span></div>' +
      '<div class="dgBody">' + cons +
        '<ul><li>▲ ' + esc(t.next_up) + '</li><li>▼ ' + esc(t.next_down) + '</li>' +
        (g.cross_read || []).map(function (c) { return '<li>' + esc(c.text) + '</li>'; }).join('') + '</ul>' +
        brief + '<div class="dgGrid">' + tables + '</div>' +
        '<div class="dgFoot">숫자 출처: 옵저버토리 수집 파이프라인 확정치 · 생성 ' + esc((g.generated_kst || '').slice(0, 16).replace('T', ' ')) + ' KST · 매매 지시 아님</div>' +
      '</div>';
    var head = host.querySelector('.dgHead');
    function toggle() {
      var next = host.getAttribute('data-collapsed') === '1' ? '0' : '1';
      host.setAttribute('data-collapsed', next);
      head.setAttribute('aria-expanded', next === '1' ? 'false' : 'true');
      try { localStorage.setItem('dailyGlanceCollapsed', next); } catch (e) { /* storage unavailable */ }
    }
    head.addEventListener('click', toggle);
    head.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
  }
  fetch('./data/daily-glance.json?t=' + Date.now(), {cache: 'no-store'})
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (g) { if (g && g.schema === 'JJOONI_DAILY_GLANCE_V1') render(g); else host.remove(); })
    .catch(function () { host.remove(); });
  window.JjooniDailyGlance = {version: VERSION};
})();
