/* main.js — JINNI GRID Pro Dashboard */

var ApiClient = (function () {
  'use strict';
  function _request(method, path, body) {
    var opts = { method: method };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          var msg = 'HTTP ' + res.status;
          try { var j = JSON.parse(text); if (j.detail) msg = typeof j.detail === 'string' ? j.detail : (j.detail.error || JSON.stringify(j.detail)); } catch (e) { if (text) msg = text; }
          var err = new Error(msg); err.status = res.status; throw err;
        });
      }
      return res.json();
    });
  }
  function _upload(path, file) {
    var fd = new FormData(); fd.append('file', file);
    return fetch(path, { method: 'POST', body: fd }).then(function (res) {
      if (!res.ok) { return res.text().then(function (t) { var m = 'HTTP ' + res.status; try { var j = JSON.parse(t); if (j.detail) m = typeof j.detail === 'string' ? j.detail : (j.detail.error || JSON.stringify(j.detail)); } catch (e) { if (t) m = t; } throw new Error(m); }); }
      return res.json();
    });
  }
  return {
    getFleetWorkers: function () { return _request('GET', '/api/Grid/workers'); },
    getSystemSummary: function () { return _request('GET', '/api/system/summary'); },
    getHealth: function () { return _request('GET', '/api/health'); },
    getStrategies: function () { return _request('GET', '/api/grid/strategies'); },
    getStrategy: function (id) { return _request('GET', '/api/grid/strategies/' + encodeURIComponent(id)); },
    uploadStrategy: function (file) { return _upload('/api/grid/strategies/upload', file); },
    validateStrategy: function (id) { return _request('POST', '/api/grid/strategies/' + encodeURIComponent(id) + '/validate'); },
    createDeployment: function (cfg) { return _request('POST', '/api/grid/deployments', cfg); },
    getDeployments: function () { return _request('GET', '/api/grid/deployments'); },
    getDeployment: function (id) { return _request('GET', '/api/grid/deployments/' + encodeURIComponent(id)); },
    stopDeployment: function (id) { return _request('POST', '/api/grid/deployments/' + encodeURIComponent(id) + '/stop'); },
    getPortfolioSummary: function () { return _request('GET', '/api/portfolio/summary'); },
    getEquityHistory: function () { return _request('GET', '/api/portfolio/equity-history'); },
    getPortfolioTrades: function (params) {
      var q = [];
      if (params) { for (var k in params) { if (params[k]) q.push(k + '=' + encodeURIComponent(params[k])); } }
      return _request('GET', '/api/portfolio/trades' + (q.length ? '?' + q.join('&') : ''));
    },
    getPortfolioPerformance: function () { return _request('GET', '/api/portfolio/performance'); },
    getEvents: function (params) {
      var q = [];
      if (params) { for (var k in params) { if (params[k]) q.push(k + '=' + encodeURIComponent(params[k])); } }
      return _request('GET', '/api/events' + (q.length ? '?' + q.join('&') : ''));
    },
    // Settings
    getSettings: function () { return _request('GET', '/api/settings'); },
    saveSettings: function (settings) { return _request('PUT', '/api/settings', { settings: settings }); },
    // Admin
    getAdminStats: function () { return _request('GET', '/api/admin/stats'); },
    adminDeleteStrategy: function (sid) { return _request('POST', '/api/admin/strategies/' + sid + '/delete'); },
    adminResetPortfolio: function () { return _request('POST', '/api/admin/portfolio/reset'); },
    adminClearTrades: function () { return _request('POST', '/api/admin/trades/clear'); },
    adminRemoveWorker: function (wid) { return _request('POST', '/api/admin/workers/' + wid + '/remove'); },
    adminRemoveStaleWorkers: function () { return _request('POST', '/api/admin/workers/stale/remove'); },
    adminClearEvents: function () { return _request('POST', '/api/admin/events/clear'); },
    adminFullReset: function () { return _request('POST', '/api/admin/system/reset', { confirm: 'RESET_EVERYTHING' }); }
  };
})();

var DeploymentConfig = (function () {
  'use strict';
  return {
    runtimeDefaults: { symbol: 'EURUSD', lot_size: 0.01, tick_lookback_value: 30, tick_lookback_unit: 'minutes', bar_size_points: 100, max_bars_memory: 500 },
    symbolOptions: ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','USDCHF','NZDUSD','XAUUSD','BTCUSD','USTEC','SPX500','DOW30','FTSE100'],
    tickLookbackUnits: ['minutes','hours','days']
  };
})();

var ModalManager = (function () {
  'use strict';
  var _overlay = null;
  function show(options) {
    hide();
    var title = options.title || 'Confirm', bodyHtml = options.bodyHtml || '', confirmText = options.confirmText || 'Confirm', cancelText = options.cancelText || 'Cancel', type = options.type || 'default', onConfirm = options.onConfirm || function () {};
    var confirmStyle = type === 'danger' ? ' style="background:var(--danger);"' : '';
    _overlay = document.createElement('div'); _overlay.className = 'modal-overlay';
    _overlay.innerHTML = '<div class="modal-card"><div class="modal-header"><span class="modal-title">' + title + '</span><button class="modal-close" id="modal-close">&times;</button></div><div class="modal-body">' + bodyHtml + '</div><div class="modal-footer"><button class="wd-btn wd-btn-ghost" id="modal-cancel">' + cancelText + '</button><button class="wd-btn wd-btn-primary" id="modal-confirm"' + confirmStyle + '>' + confirmText + '</button></div></div>';
    document.body.appendChild(_overlay);
    _overlay.querySelector('#modal-close').addEventListener('click', hide);
    _overlay.querySelector('#modal-cancel').addEventListener('click', hide);
    _overlay.querySelector('#modal-confirm').addEventListener('click', function () { onConfirm(); hide(); });
    _overlay.addEventListener('click', function (e) { if (e.target === _overlay) hide(); });
  }
  function hide() { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); _overlay = null; }
  return { show: show, hide: hide };
})();

var ToastManager = (function () {
  'use strict';
  var iconMap = { success: 'fa-circle-check', info: 'fa-circle-info', warning: 'fa-triangle-exclamation', error: 'fa-circle-xmark' };
  function _getContainer() { var c = document.querySelector('.toast-container'); if (!c) { c = document.createElement('div'); c.className = 'toast-container'; document.body.appendChild(c); } return c; }
  function show(message, type, duration) {
    type = type || 'info'; duration = duration || 4000;
    var container = _getContainer(), toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML = '<i class="fa-solid ' + (iconMap[type] || iconMap.info) + '"></i><span>' + message + '</span><button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';
    container.appendChild(toast);
    toast.querySelector('.toast-dismiss').addEventListener('click', function () { _remove(toast); });
    setTimeout(function () { _remove(toast); }, duration);
  }
  function _remove(toast) { if (!toast || !toast.parentNode) return; toast.style.opacity = '0'; toast.style.transform = 'translateX(20px)'; toast.style.transition = 'all 0.3s ease'; setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 300); }
  return { show: show };
})();

var ThemeManager = (function () {
  'use strict';
  var STORAGE_KEY = 'jinni-Grid-theme', currentTheme = 'dark';
  function init() { var s = localStorage.getItem(STORAGE_KEY); currentTheme = s === 'light' ? 'light' : 'dark'; applyTheme(); updateToggleButton(); var btn = document.getElementById('theme-toggle'); if (btn) btn.addEventListener('click', toggle); }
  function toggle() { currentTheme = currentTheme === 'dark' ? 'light' : 'dark'; localStorage.setItem(STORAGE_KEY, currentTheme); applyTheme(); updateToggleButton(); }
  function applyTheme() { document.body.setAttribute('data-theme', currentTheme); }
  function updateToggleButton() { var btn = document.getElementById('theme-toggle'); if (!btn) return; var icon = btn.querySelector('i'), label = btn.querySelector('span'); if (currentTheme === 'dark') { icon.className = 'fa-solid fa-sun'; label.textContent = 'Light Mode'; } else { icon.className = 'fa-solid fa-moon'; label.textContent = 'Dark Mode'; } }
  function getTheme() { return currentTheme; }
  return { init: init, toggle: toggle, getTheme: getTheme };
})();

/* ===== Chart Helpers ===== */
var ChartHelper = (function () {
  'use strict';
  function _isDark() { return ThemeManager.getTheme() === 'dark'; }
  function gridColor() { return _isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'; }
  function textColor() { return _isDark() ? '#94a3b8' : '#475569'; }
  function tooltipBg() { return _isDark() ? '#1e293b' : '#ffffff'; }
  function tooltipColor() { return _isDark() ? '#e2e8f0' : '#1e293b'; }
  function accentColor() { return _isDark() ? '#06b6d4' : '#0891b2'; }
  function successColor() { return '#10b981'; }
  function dangerColor() { return '#ef4444'; }
  function baseOpts(extraOpts) {
    var o = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: tooltipBg(), titleColor: tooltipColor(), bodyColor: tooltipColor(), borderColor: gridColor(), borderWidth: 1, cornerRadius: 6, padding: 10, titleFont: { family: 'Inter', size: 12 }, bodyFont: { family: 'JetBrains Mono', size: 11 } } },
      scales: { x: { grid: { color: gridColor(), drawBorder: false }, ticks: { color: textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 12 } }, y: { grid: { color: gridColor(), drawBorder: false }, ticks: { color: textColor(), font: { family: 'JetBrains Mono', size: 10 } } } },
      interaction: { mode: 'index', intersect: false },
      animation: { duration: 600 }
    };
    if (extraOpts) { for (var k in extraOpts) o[k] = extraOpts[k]; }
    return o;
  }
  return { gridColor: gridColor, textColor: textColor, accentColor: accentColor, successColor: successColor, dangerColor: dangerColor, baseOpts: baseOpts, tooltipBg: tooltipBg, tooltipColor: tooltipColor };
})();

/* ===== Utility ===== */
function _fmtMoney(v) { if (v === null || v === undefined) return '\u2014'; var s = v >= 0 ? '+' : ''; return s + '$' + Math.abs(v).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
function _fmtPct(v) { if (v === null || v === undefined) return '\u2014'; return v.toFixed(1) + '%'; }
function _fmtNum(n) { if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'; if (n >= 1000) return (n / 1000).toFixed(1) + 'K'; return String(n); }
function _nullVal(val, fb) { if (val === null || val === undefined || val === '') return '<span class="value-null">' + (fb || '\u2014') + '</span>'; return String(val); }
function _formatAge(seconds) { if (seconds === null || seconds === undefined) return '<span class="value-null">\u2014</span>'; var s = Math.round(seconds); if (s < 60) return s + 's ago'; if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago'; return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago'; }

/* ============================================================
   DASHBOARD RENDERER (PRO QUANT TERMINAL)
   ============================================================ */
var DashboardRenderer = (function () {
  'use strict';
  var _intervals = [];
  var _charts = {};
  var _lastFleetWorkers = [];

  function _destroyCharts() { for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } } }

  function _kpiCard(icon, label, value, sentiment, sub) {
    var vc = sentiment === 'positive' ? ' positive' : sentiment === 'negative' ? ' negative' : '';
    return '<div class="portfolio-card"><div class="card-icon ' + sentiment + '"><i class="fa-solid ' + icon + '"></i></div><div class="card-info"><div class="card-value' + vc + '">' + value + '</div><div class="card-label">' + label + '</div>' + (sub ? '<div class="card-sub">' + sub + '</div>' : '') + '</div></div>';
  }

  function _fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count + '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _deployStateClass(state) {
    if (!state) return 'unknown';
    if (state === 'running') return 'online';
    if (state === 'failed') return 'error';
    if (state === 'stopped') return 'offline';
    if (state.indexOf('loading') !== -1 || state.indexOf('fetching') !== -1 || state.indexOf('generating') !== -1 || state.indexOf('warming') !== -1) return 'warning';
    return 'stale';
  }

  function render() {
    var html = '<div class="dashboard">';
    html += '<section><div class="section-header"><i class="fa-solid fa-gauge-high"></i><h2>System Overview</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dash-kpi" class="portfolio-grid"><div class="loading-state" style="min-height:80px;grid-column:1/-1;"><div class="spinner"></div></div></div></section>';
    html += '<div class="dash-split-row">';
    html += '<section class="dash-chart-section"><div class="section-header"><i class="fa-solid fa-chart-area"></i><h2>Equity Curve</h2></div>';
    html += '<div class="chart-container"><div class="chart-wrapper" id="dash-equity-wrap"><canvas id="dash-equity-chart"></canvas></div></div></section>';
    html += '<section class="dash-stats-section"><div class="section-header"><i class="fa-solid fa-chart-pie"></i><h2>Portfolio Stats</h2></div>';
    html += '<div id="dash-port-stats" class="dash-stats-grid"><div class="loading-state" style="min-height:200px;"><div class="spinner"></div></div></div></section>';
    html += '</div>';
    html += '<div class="dash-triple-row">';
    html += '<section><div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Health</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dash-fleet" class="dash-panel-body"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '<section><div class="section-header"><i class="fa-solid fa-diagram-project"></i><h2>Pipeline</h2></div>';
    html += '<div id="dash-pipeline" class="dash-panel-body"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '<section><div class="section-header"><i class="fa-solid fa-crosshairs"></i><h2>Active Strategies</h2></div>';
    html += '<div id="dash-strategies" class="dash-panel-body"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '</div>';
    html += '<div class="dash-dual-row">';
    html += '<section><div class="section-header"><i class="fa-solid fa-receipt"></i><h2>Recent Trades</h2></div>';
    html += '<div id="dash-trades"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '<section><div class="section-header"><i class="fa-solid fa-rocket"></i><h2>Recent Deployments</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dash-deploys"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '</div>';
    html += '</div>';
    document.getElementById('main-content').innerHTML = html;
    _fetchAll();
    _intervals.push(setInterval(_fetchLive, 10000));
    _intervals.push(setInterval(_fetchKPIs, 15000));
  }

  function _fetchAll() { _fetchKPIs(); _fetchEquity(); _fetchPortStats(); _fetchFleet(); _fetchPipeline(); _fetchStrategies(); _fetchTrades(); _fetchDeploys(); }
  function _fetchLive() { _fetchFleet(); _fetchPipeline(); _fetchDeploys(); }

  function _fetchKPIs() {
    Promise.all([
      ApiClient.getPortfolioSummary().catch(function () { return { portfolio: {} }; }),
      ApiClient.getSystemSummary().catch(function () { return {}; }),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; })
    ]).then(function (r) {
      var p = r[0].portfolio || {}, sys = r[1], deps = r[2].deployments || [];
      var running = deps.filter(function (d) { return d.state === 'running'; }).length;
      var el = document.getElementById('dash-kpi'); if (!el) return;
      el.innerHTML =
        _kpiCard('fa-wallet', 'Equity', '$' + _fmtNum(p.total_equity || 0), 'neutral') +
        _kpiCard('fa-chart-line', 'Realized P&L', _fmtMoney(p.realized_pnl), (p.realized_pnl || 0) >= 0 ? 'positive' : 'negative') +
        _kpiCard('fa-clock', 'Floating P&L', _fmtMoney(p.floating_pnl), (p.floating_pnl || 0) >= 0 ? 'positive' : 'negative') +
        _kpiCard('fa-percent', 'Win Rate', _fmtPct(p.win_rate), (p.win_rate || 0) >= 50 ? 'positive' : 'negative') +
        _kpiCard('fa-chart-bar', 'Profit Factor', String(p.profit_factor || 0), (p.profit_factor || 0) >= 1 ? 'positive' : 'negative') +
        _kpiCard('fa-arrow-trend-down', 'Max Drawdown', _fmtPct(p.max_drawdown), 'negative') +
        _kpiCard('fa-server', 'Online Nodes', (sys.online_nodes || 0) + '/' + (sys.total_nodes || 0), (sys.online_nodes || 0) > 0 ? 'positive' : 'warning') +
        _kpiCard('fa-play', 'Running', String(running), running > 0 ? 'positive' : 'neutral');
    });
  }

  function _fetchEquity() {
    ApiClient.getEquityHistory().then(function (data) {
      var hist = data.equity_history || [];
      if (hist.length === 0) {
        var wrap = document.getElementById('dash-equity-wrap');
        if (wrap) wrap.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:12px;gap:10px;"><i class="fa-solid fa-chart-area" style="opacity:0.3;font-size:28px;"></i><div><div style="font-weight:600;margin-bottom:2px;">No Equity Data Yet</div><div style="font-size:10.5px;opacity:0.7;">Trades will build the equity curve as strategies execute.</div></div></div>';
        return;
      }
      var labels = hist.map(function (h) { return h.label || h.timestamp; });
      var values = hist.map(function (h) { return h.equity; });
      var canvas = document.getElementById('dash-equity-chart'); if (!canvas) return;
      if (_charts.equity) _charts.equity.destroy();
      var ctx = canvas.getContext('2d');
      var gradient = ctx.createLinearGradient(0, 0, 0, 280);
      gradient.addColorStop(0, 'rgba(6,182,212,0.25)');
      gradient.addColorStop(1, 'rgba(6,182,212,0.0)');
      _charts.equity = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: [{ data: values, borderColor: ChartHelper.accentColor(), backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHitRadius: 10 }] },
        options: ChartHelper.baseOpts({ scales: { x: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 10 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return '$' + _fmtNum(v); } } } } })
      });
    }).catch(function () {});
  }

  function _fetchPortStats() {
    ApiClient.getPortfolioSummary().then(function (data) {
      var p = data.portfolio || {}, el = document.getElementById('dash-port-stats'); if (!el) return;
      function _stat(l, v, c) { return '<div class="dash-stat-item"><span class="dash-stat-val' + (c ? ' ' + c : '') + '">' + v + '</span><span class="dash-stat-lbl">' + l + '</span></div>'; }
      el.innerHTML =
        _stat('Total Trades', p.total_trades || 0) +
        _stat('Win Rate', _fmtPct(p.win_rate), (p.win_rate || 0) >= 50 ? 'positive' : 'negative') +
        _stat('Profit Factor', p.profit_factor || 0, (p.profit_factor || 0) >= 1 ? 'positive' : 'negative') +
        _stat('Sharpe Est.', p.sharpe_estimate || 0, (p.sharpe_estimate || 0) >= 1 ? 'positive' : 'negative') +
        _stat('Avg Trade', _fmtMoney(p.avg_trade), (p.avg_trade || 0) >= 0 ? 'positive' : 'negative') +
        _stat('Avg Winner', _fmtMoney(p.avg_winner), 'positive') +
        _stat('Avg Loser', _fmtMoney(p.avg_loser), 'negative') +
        _stat('Max DD', _fmtPct(p.max_drawdown), 'negative') +
        _stat('Best Trade', _fmtMoney(p.best_trade), 'positive') +
        _stat('Worst Trade', _fmtMoney(p.worst_trade), 'negative') +
        _stat('Avg Bars', p.avg_bars_held || 0) +
        _stat('Open Pos.', p.open_positions || 0);
    }).catch(function () {});
  }

  function _fetchFleet() {
    ApiClient.getFleetWorkers().then(function (data) {
      var s = data.summary || {}, workers = data.workers || [], el = document.getElementById('dash-fleet'); if (!el) return;
      _lastFleetWorkers = workers;
      var html = '<div class="fleet-summary" style="margin-bottom:12px;">';
      html += _fleetBadge(s.total_workers || 0, 'Total', 'total') + _fleetBadge(s.online_workers || 0, 'Online', 'online') + _fleetBadge(s.stale_workers || 0, 'Stale', 'stale') + _fleetBadge(s.offline_workers || 0, 'Offline', 'offline') + _fleetBadge(s.error_workers || 0, 'Error', 'error');
      html += '</div>';
      if (workers.length > 0) {
        html += '<div class="compact-fleet-wrapper" style="margin-top:0;"><table class="compact-fleet-table"><thead><tr><th>Worker</th><th>State</th><th>MT5</th><th>Strategy</th><th>Heartbeat</th></tr></thead><tbody>';
        workers.forEach(function (w) {
          var name = w.worker_name || w.worker_id, state = w.state || 'unknown';
          var strats = w.active_strategies && w.active_strategies.length > 0 ? w.active_strategies.join(', ') : '<span class="value-null">\u2014</span>';
          var mt5 = w.mt5_state === 'connected' ? '<span style="color:var(--success);">\u25CF</span>' : '<span class="value-null">\u25CB</span>';
          html += '<tr class="clickable" onclick="DashboardRenderer._openWorker(\'' + w.worker_id + '\')"><td class="mono">' + name + '</td><td><span class="state-pill ' + state + '">' + state.toUpperCase() + '</span></td><td>' + mt5 + '</td><td class="mono">' + strats + '</td><td class="mono">' + _formatAge(w.heartbeat_age_seconds) + '</td></tr>';
        });
        html += '</tbody></table></div>';
      } else {
        html += '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;"><i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>No workers connected.</div>';
      }
      html += '<span class="view-fleet-link" onclick="App.navigateTo(\'fleet\')">View Fleet <i class="fa-solid fa-arrow-right"></i></span>';
      el.innerHTML = html;
    }).catch(function () { var el = document.getElementById('dash-fleet'); if (el) el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">Could not load fleet data.</div>'; });
  }

  function _fetchPipeline() {
    ApiClient.getFleetWorkers().then(function (data) {
      var workers = data.workers || [], el = document.getElementById('dash-pipeline'); if (!el) return;
      var totalTicks = 0, totalBars = 0, totalSignals = 0, totalOnBar = 0;
      workers.forEach(function (w) { totalTicks += (w.total_ticks || 0); totalBars += (w.total_bars || 0); totalSignals += (w.signal_count || 0); totalOnBar += (w.on_bar_calls || 0); });
      if (workers.length === 0) {
        el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;padding:24px;color:var(--text-muted);font-size:12px;gap:10px;"><i class="fa-solid fa-diagram-project" style="opacity:0.3;font-size:24px;"></i><div><div style="font-weight:600;margin-bottom:2px;">No Pipeline Data</div><div style="font-size:10.5px;opacity:0.7;">Connect worker agents to see live tick/bar/signal flow.</div></div></div>';
        return;
      }
      el.innerHTML = '<div class="pipeline-flow">' +
        '<div class="pipeline-node"><span class="pipeline-val accent">' + _fmtNum(totalTicks) + '</span><span class="pipeline-lbl">Ticks</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val warning">' + _fmtNum(totalBars) + '</span><span class="pipeline-lbl">Bars</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val success">' + _fmtNum(totalOnBar) + '</span><span class="pipeline-lbl">on_bar()</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val danger">' + _fmtNum(totalSignals) + '</span><span class="pipeline-lbl">Signals</span></div>' +
        '</div>';
    }).catch(function () {});
  }

  function _fetchStrategies() {
    Promise.all([
      ApiClient.getStrategies().catch(function () { return { strategies: [] }; }),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; })
    ]).then(function (r) {
      var strats = r[0].strategies || [], deps = r[1].deployments || [], el = document.getElementById('dash-strategies'); if (!el) return;
      if (strats.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No strategies registered.</div>'; return; }
      var html = '<div style="display:flex;flex-direction:column;gap:8px;">';
      strats.forEach(function (s) {
        var active = deps.filter(function (d) { return d.strategy_id === s.strategy_id && d.state === 'running'; }).length;
        var total = deps.filter(function (d) { return d.strategy_id === s.strategy_id; }).length;
        html += '<div class="dash-strat-row"><div class="dash-strat-info"><span class="mono" style="color:var(--accent);font-weight:600;">' + (s.name || s.strategy_id) + '</span><span class="dash-strat-meta">v' + (s.version || '?') + '</span></div><div class="dash-strat-badges">' +
          (active > 0 ? '<span class="state-pill online">' + active + ' RUNNING</span>' : '') +
          '<span style="font-size:10px;color:var(--text-muted);">' + total + ' deploy' + (total !== 1 ? 's' : '') + '</span></div></div>';
      });
      html += '</div>';
      el.innerHTML = html;
    });
  }

  function _fetchTrades() {
    ApiClient.getPortfolioTrades({ limit: 10 }).then(function (data) {
      var trades = data.trades || [], el = document.getElementById('dash-trades'); if (!el) return;
      if (trades.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No trades yet.</div>'; return; }
      var html = '<div class="compact-fleet-wrapper" style="margin-top:0;"><table class="compact-fleet-table"><thead><tr><th>Symbol</th><th>Dir</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Reason</th></tr></thead><tbody>';
      trades.slice(0, 10).forEach(function (t) {
        var pnlClass = t.profit >= 0 ? 'text-success' : 'text-danger';
        html += '<tr><td class="mono">' + t.symbol + '</td><td><span class="state-pill ' + (t.direction === 'long' ? 'online' : 'error') + '">' + t.direction.toUpperCase() + '</span></td><td class="mono">' + t.entry_price + '</td><td class="mono">' + t.exit_price + '</td><td class="mono ' + pnlClass + '">' + _fmtMoney(t.profit) + '</td><td class="mono" style="font-size:10px;">' + (t.exit_reason || '\u2014') + '</td></tr>';
      });
      html += '</tbody></table></div><span class="view-fleet-link" onclick="App.navigateTo(\'portfolio\')">View Portfolio <i class="fa-solid fa-arrow-right"></i></span>';
      el.innerHTML = html;
    }).catch(function () {});
  }

  function _fetchDeploys() {
    ApiClient.getDeployments().then(function (data) {
      var deps = data.deployments || [], el = document.getElementById('dash-deploys'); if (!el) return;
      if (deps.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No deployments yet.</div>'; return; }
      deps = deps.slice().reverse().slice(0, 8);
      var html = '<div class="compact-fleet-wrapper" style="margin-top:0;"><table class="compact-fleet-table"><thead><tr><th>ID</th><th>Strategy</th><th>Worker</th><th>Symbol</th><th>State</th></tr></thead><tbody>';
      deps.forEach(function (d) {
        var sc = _deployStateClass(d.state);
        html += '<tr><td class="mono">' + d.deployment_id + '</td><td class="mono">' + d.strategy_id + '</td><td class="mono">' + d.worker_id + '</td><td class="mono">' + d.symbol + '</td><td><span class="state-pill ' + sc + '">' + d.state.toUpperCase().replace(/_/g, ' ') + '</span></td></tr>';
      });
      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function () {});
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastFleetWorkers.length; i++) {
      if (_lastFleetWorkers[i].worker_id === workerId) { App.navigateToWorkerDetail(_lastFleetWorkers[i]); return; }
    }
  }

  function destroy() { _intervals.forEach(clearInterval); _intervals = []; _destroyCharts(); }

  return { render: render, destroy: destroy, _openWorker: _openWorker };
})();

/* ============================================================
   FLEET RENDERER
   ============================================================ */
var FleetRenderer = (function () {
  'use strict';
  var _refreshInterval = null, _lastWorkers = [];

  function fleetBadge(count, label, type) { return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count + '</span><span class="badge-label">' + label + '</span></div>'; }

  function renderNodeCard(w) {
    var state = w.state || 'unknown', name = w.worker_name || w.worker_id;
    var strats = w.active_strategies && w.active_strategies.length > 0 ? w.active_strategies.join(', ') : null;
    var pnlVal = w.floating_pnl !== null && w.floating_pnl !== undefined ? _fmtMoney(w.floating_pnl) : '<span class="value-null">\u2014</span>';
    var pnlStyle = w.floating_pnl !== null && w.floating_pnl !== undefined ? (w.floating_pnl >= 0 ? 'color:var(--success)' : 'color:var(--danger)') : '';
    function _row(l, v) { return '<div class="node-info-row"><span class="node-info-label">' + l + '</span><span class="node-info-value">' + v + '</span></div>'; }
    return '<div class="node-card clickable" onclick="FleetRenderer._openWorker(\'' + w.worker_id + '\')">' +
      '<div class="node-card-top ' + state + '"></div><div class="node-card-header"><div class="node-name-group"><span class="node-status-dot ' + state + '"></span><span class="node-name">' + name + '</span></div><span class="node-status-badge ' + state + '">' + (state.charAt(0).toUpperCase() + state.slice(1)) + '</span></div><div class="node-card-body">' +
      _row('Worker ID', '<span class="mono">' + w.worker_id + '</span>') +
      _row('Host', _nullVal(w.host)) +
      _row('MT5', w.mt5_state === 'connected' ? '<span style="color:var(--success);">Connected</span>' : _nullVal(w.mt5_state, 'Not Connected')) +
      _row('Broker', _nullVal(w.broker)) +
      _row('Strategies', _nullVal(strats, 'None')) +
      _row('Positions', '<span style="color:var(--accent);">' + (w.open_positions_count || 0) + '</span>') +
      _row('Float PnL', '<span style="' + pnlStyle + '">' + pnlVal + '</span>') +
      _row('Pipeline', '<span class="mono" style="font-size:10px;">' + (w.total_ticks || 0) + ' ticks / ' + (w.total_bars || 0) + ' bars / ' + (w.signal_count || 0) + ' sig</span>') +
      _row('Heartbeat', _formatAge(w.heartbeat_age_seconds)) +
      '<div class="node-card-action"><i class="fa-solid fa-arrow-right"></i> View / Deploy</div></div></div>';
  }

  function _renderContent(data) {
    var el = document.getElementById('fleet-content'); if (!el) return;
    var workers = data.workers || [], s = data.summary || {}; _lastWorkers = workers;
    var headerEl = document.getElementById('fleet-page-header');
    if (headerEl) { headerEl.style.display = 'flex'; var m = headerEl.querySelector('.last-synced'); if (m) m.textContent = 'Synced: ' + new Date().toLocaleTimeString('en-GB', { hour12: false }); }
    if (workers.length === 0) { el.innerHTML = '<div class="empty-state"><i class="fa-solid fa-server"></i><h3>No Workers Connected</h3><p>Start a worker agent to see fleet data.</p></div>'; return; }
    var html = '<div class="fleet-summary">' + fleetBadge(s.total_workers || 0, 'Total', 'total') + fleetBadge(s.online_workers || 0, 'Online', 'online') + fleetBadge(s.stale_workers || 0, 'Stale', 'stale') + fleetBadge(s.offline_workers || 0, 'Offline', 'offline') + fleetBadge(s.error_workers || 0, 'Error', 'error') + '</div>';
    html += '<div class="fleet-grid">'; workers.forEach(function (w) { html += renderNodeCard(w); }); html += '</div>';
    el.innerHTML = html;
  }

  function _fetch() { ApiClient.getFleetWorkers().then(_renderContent).catch(function () { var el = document.getElementById('fleet-content'); if (el) el.innerHTML = '<div class="error-state"><i class="fa-solid fa-triangle-exclamation"></i><h3>Failed to Load Fleet</h3><button class="retry-btn" onclick="FleetRenderer._retry()">Retry</button></div>'; }); }
  function _openWorker(wid) { for (var i = 0; i < _lastWorkers.length; i++) { if (_lastWorkers[i].worker_id === wid) { App.navigateToWorkerDetail(_lastWorkers[i]); return; } } }
  function render() {
    document.getElementById('main-content').innerHTML = '<div class="fleet-page"><div class="fleet-page-header" id="fleet-page-header" style="display:none;"><span class="fleet-page-title"><i class="fa-solid fa-server" style="color:var(--accent);margin-right:8px;"></i>Fleet Management</span><div class="fleet-page-meta"><div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Auto-refresh</div><span class="last-synced">Synced: --:--:--</span></div></div><div id="fleet-content"><div class="loading-state"><div class="spinner"></div><p>Loading fleet\u2026</p></div></div></div>';
    _fetch(); _refreshInterval = setInterval(_fetch, 5000);
  }
  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }
  return { render: render, destroy: destroy, _retry: _fetch, _openWorker: _openWorker };
})();

/* ============================================================
   STRATEGIES RENDERER
   ============================================================ */
var StrategiesRenderer = (function () {
  'use strict';
  var _refreshInterval = null;
  function render() {
    var html = '<div class="fleet-page"><div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-crosshairs" style="color:var(--accent);margin-right:8px;"></i>Strategy Registry</span><div class="fleet-page-meta"><button class="wd-refresh-btn" id="strat-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';
    html += '<div class="wd-panel"><div class="wd-panel-header">Upload Strategy<span class="panel-badge">REGISTER</span></div><div class="wd-panel-body"><div class="wd-file-upload" id="strat-upload-area"><input type="file" id="strat-file-input" accept=".py" style="display:none" /><i class="fa-solid fa-file-code"></i><h4>Upload Strategy File</h4><p>.py files extending BaseStrategy</p><div id="strat-upload-status"></div></div></div></div>';
    html += '<div id="strat-list-content"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading\u2026</p></div></div></div>';
    document.getElementById('main-content').innerHTML = html;
    _attachEvents(); _fetch(); _refreshInterval = setInterval(_fetch, 10000);
  }
  function _attachEvents() {
    document.getElementById('strat-refresh').addEventListener('click', _fetch);
    var area = document.getElementById('strat-upload-area'), input = document.getElementById('strat-file-input');
    area.addEventListener('click', function () { input.click(); });
    input.addEventListener('change', function () { if (!input.files || !input.files[0]) return; var f = input.files[0]; if (!f.name.endsWith('.py')) { ToastManager.show('Only .py files.', 'error'); return; } _upload(f); });
  }
  function _upload(file) {
    var el = document.getElementById('strat-upload-status');
    el.innerHTML = '<div class="wd-file-status" style="color:var(--accent);"><i class="fa-solid fa-spinner fa-spin"></i> Uploading\u2026</div>';
    ApiClient.uploadStrategy(file).then(function (d) { el.innerHTML = '<div class="wd-file-status" style="color:var(--success);"><i class="fa-solid fa-circle-check"></i> Registered: ' + (d.strategy_name || d.strategy_id) + '</div>'; ToastManager.show('Strategy registered.', 'success'); _fetch(); }).catch(function (e) { el.innerHTML = '<div class="wd-file-status" style="color:var(--danger);"><i class="fa-solid fa-circle-xmark"></i> ' + e.message + '</div>'; });
  }
  function _fetch() {
    var el = document.getElementById('strat-list-content'); if (!el) return;
    ApiClient.getStrategies().then(function (data) {
      var list = data.strategies || [];
      if (list.length === 0) { el.innerHTML = '<div class="empty-state" style="min-height:200px;"><i class="fa-solid fa-crosshairs"></i><h3>No Strategies</h3><p>Upload a .py strategy file to get started.</p></div>'; return; }
      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>ID</th><th>Name</th><th>Version</th><th>Hash</th><th>Uploaded</th></tr></thead><tbody>';
      list.forEach(function (s) { var up = s.uploaded_at ? s.uploaded_at.replace('T', ' ').substring(0, 19) : '\u2014'; html += '<tr><td class="mono">' + s.strategy_id + '</td><td>' + (s.name || s.strategy_id) + '</td><td class="mono">' + (s.version || '\u2014') + '</td><td class="mono" style="font-size:10px;">' + (s.file_hash || '\u2014') + '</td><td class="mono">' + up + '</td></tr>'; });
      html += '</tbody></table></div>'; el.innerHTML = html;
    }).catch(function (e) { el.innerHTML = '<div class="error-state" style="min-height:200px;"><i class="fa-solid fa-triangle-exclamation"></i><h3>Failed to Load</h3><p>' + e.message + '</p></div>'; });
  }
  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }
  return { render: render, destroy: destroy };
})();

/* ============================================================
   PORTFOLIO RENDERER
   ============================================================ */
var PortfolioRenderer = (function () {
  'use strict';
  var _charts = {}, _filters = { strategy_id: '', worker_id: '', symbol: '' }, _viewMode = 'overall';

  function _destroyCharts() { for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } } }

  function render() {
    var html = '<div class="fleet-page" id="portfolio-page">';
    html += '<div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-chart-line" style="color:var(--accent);margin-right:8px;"></i>Portfolio Analytics</span><div class="fleet-page-meta"><button class="wd-refresh-btn" id="port-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';
    html += '<div class="port-tabs" id="port-tabs"><button class="port-tab active" data-mode="overall">Overall</button><button class="port-tab" data-mode="strategy">By Strategy</button><button class="port-tab" data-mode="worker">By Worker</button><button class="port-tab" data-mode="symbol">By Symbol</button></div>';
    html += '<div class="port-filters" id="port-filters"><div class="wd-form-group"><label class="wd-form-label">Strategy</label><select class="wd-form-select port-filter" id="port-f-strategy"><option value="">All</option></select></div><div class="wd-form-group"><label class="wd-form-label">Worker</label><select class="wd-form-select port-filter" id="port-f-worker"><option value="">All</option></select></div><div class="wd-form-group"><label class="wd-form-label">Symbol</label><select class="wd-form-select port-filter" id="port-f-symbol"><option value="">All</option></select></div></div>';
    html += '<div id="port-stats" class="dash-stats-grid" style="margin-bottom:20px;"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div></div></div>';
    html += '<div class="dash-split-row"><section class="dash-chart-section"><div class="section-header"><i class="fa-solid fa-chart-area"></i><h2>Equity Curve</h2></div><div class="chart-container"><div class="chart-wrapper" id="port-equity-wrap"><canvas id="port-equity-chart"></canvas></div></div></section>';
    html += '<section class="dash-chart-section"><div class="section-header"><i class="fa-solid fa-arrow-trend-down"></i><h2>Drawdown</h2></div><div class="chart-container"><div class="chart-wrapper" id="port-dd-wrap"><canvas id="port-dd-chart"></canvas></div></div></section></div>';
    html += '<section><div class="section-header"><i class="fa-solid fa-calendar-days"></i><h2>Daily P&L</h2></div><div class="chart-container"><div class="chart-wrapper" style="height:220px;" id="port-daily-wrap"><canvas id="port-daily-chart"></canvas></div></div></section>';
    html += '<div id="port-breakdown"></div>';
    html += '<section><div class="section-header"><i class="fa-solid fa-list"></i><h2>Trade History</h2></div><div id="port-trades"><div class="loading-state" style="min-height:120px;"><div class="spinner"></div></div></div></section>';
    html += '</div>';
    document.getElementById('main-content').innerHTML = html;
    _attachEvents();
    _loadAll();
  }

  function _attachEvents() {
    document.getElementById('port-refresh').addEventListener('click', _loadAll);
    document.querySelectorAll('.port-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('.port-tab').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        _viewMode = btn.getAttribute('data-mode');
        _loadBreakdown();
      });
    });
    document.querySelectorAll('.port-filter').forEach(function (sel) {
      sel.addEventListener('change', function () {
        _filters.strategy_id = document.getElementById('port-f-strategy').value;
        _filters.worker_id = document.getElementById('port-f-worker').value;
        _filters.symbol = document.getElementById('port-f-symbol').value;
        _loadTrades();
      });
    });
  }

  function _loadAll() { _loadFilters(); _loadStats(); _loadEquity(); _loadDaily(); _loadBreakdown(); _loadTrades(); }

  function _loadFilters() {
    ApiClient.getPortfolioTrades({ limit: 500 }).then(function (data) {
      var trades = data.trades || [];
      var strats = {}, workers = {}, syms = {};
      trades.forEach(function (t) { if (t.strategy_id) strats[t.strategy_id] = 1; if (t.worker_id) workers[t.worker_id] = 1; if (t.symbol) syms[t.symbol] = 1; });
      function _fill(id, obj) {
        var el = document.getElementById(id); if (!el) return;
        var val = el.value;
        el.innerHTML = '<option value="">All</option>';
        Object.keys(obj).sort().forEach(function (k) { el.innerHTML += '<option value="' + k + '"' + (k === val ? ' selected' : '') + '>' + k + '</option>'; });
      }
      _fill('port-f-strategy', strats); _fill('port-f-worker', workers); _fill('port-f-symbol', syms);
    }).catch(function () {});
  }

  function _loadStats() {
    ApiClient.getPortfolioSummary().then(function (data) {
      var p = data.portfolio || {}, el = document.getElementById('port-stats'); if (!el) return;
      function _s(l, v, c) { return '<div class="dash-stat-item"><span class="dash-stat-val' + (c ? ' ' + c : '') + '">' + v + '</span><span class="dash-stat-lbl">' + l + '</span></div>'; }
      el.innerHTML =
        _s('Net Profit', _fmtMoney(p.realized_pnl), (p.realized_pnl || 0) >= 0 ? 'positive' : 'negative') +
        _s('Total Trades', p.total_trades || 0) +
        _s('Win Rate', _fmtPct(p.win_rate), (p.win_rate || 0) >= 50 ? 'positive' : 'negative') +
        _s('Profit Factor', p.profit_factor || 0, (p.profit_factor || 0) >= 1 ? 'positive' : 'negative') +
        _s('Sharpe', p.sharpe_estimate || 0) +
        _s('Max DD', _fmtPct(p.max_drawdown), 'negative') +
        _s('Avg Winner', _fmtMoney(p.avg_winner), 'positive') +
        _s('Avg Loser', _fmtMoney(p.avg_loser), 'negative') +
        _s('Best', _fmtMoney(p.best_trade), 'positive') +
        _s('Worst', _fmtMoney(p.worst_trade), 'negative') +
        _s('Avg Bars', p.avg_bars_held || 0) +
        _s('Open Pos.', p.open_positions || 0);
    }).catch(function () {});
  }

  function _loadEquity() {
    ApiClient.getEquityHistory().then(function (data) {
      var hist = data.equity_history || [];
      if (hist.length === 0) {
        var ew = document.getElementById('port-equity-wrap');
        if (ew) ew.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:12px;gap:10px;"><i class="fa-solid fa-chart-area" style="opacity:0.3;font-size:28px;"></i><div><div style="font-weight:600;margin-bottom:2px;">No Equity Data Yet</div><div style="font-size:10.5px;opacity:0.7;">Trades will build the equity curve.</div></div></div>';
        return;
      }
      var labels = hist.map(function (h) { return h.label || h.timestamp; }), vals = hist.map(function (h) { return h.equity; });
      var c1 = document.getElementById('port-equity-chart'); if (!c1) return;
      if (_charts.equity) _charts.equity.destroy();
      var ctx1 = c1.getContext('2d'), g1 = ctx1.createLinearGradient(0, 0, 0, 280);
      g1.addColorStop(0, 'rgba(6,182,212,0.25)'); g1.addColorStop(1, 'rgba(6,182,212,0)');
      _charts.equity = new Chart(ctx1, { type: 'line', data: { labels: labels, datasets: [{ data: vals, borderColor: ChartHelper.accentColor(), backgroundColor: g1, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0 }] }, options: ChartHelper.baseOpts({ scales: { x: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 10 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return '$' + _fmtNum(v); } } } } }) });
      var peak = 0, dd = [];
      vals.forEach(function (v) { if (v > peak) peak = v; dd.push(peak > 0 ? -((peak - v) / peak * 100) : 0); });
      var c2 = document.getElementById('port-dd-chart'); if (!c2) return;
      if (_charts.dd) _charts.dd.destroy();
      var ctx2 = c2.getContext('2d'), g2 = ctx2.createLinearGradient(0, 0, 0, 280);
      g2.addColorStop(0, 'rgba(239,68,68,0)'); g2.addColorStop(1, 'rgba(239,68,68,0.3)');
      _charts.dd = new Chart(ctx2, { type: 'line', data: { labels: labels, datasets: [{ data: dd, borderColor: ChartHelper.dangerColor(), backgroundColor: g2, borderWidth: 1.5, fill: true, tension: 0.3, pointRadius: 0 }] }, options: ChartHelper.baseOpts({ scales: { x: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 10 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return v.toFixed(1) + '%'; } } } } }) });
    }).catch(function () {});
  }

  function _loadDaily() {
    ApiClient.getPortfolioPerformance().then(function (data) {
      var daily = (data.performance || {}).daily || [];
      if (daily.length === 0) {
        var w = document.getElementById('port-daily-wrap');
        if (w) w.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:12px;"><i class="fa-solid fa-calendar-days" style="margin-right:10px;opacity:0.3;font-size:24px;"></i>No daily performance data yet.</div>';
        return;
      }
      var labels = daily.map(function (d) { return d.date; });
      var vals = daily.map(function (d) { return d.pnl; });
      var colors = vals.map(function (v) { return v >= 0 ? 'rgba(16,185,129,0.7)' : 'rgba(239,68,68,0.7)'; });
      var c = document.getElementById('port-daily-chart'); if (!c) return;
      if (_charts.daily) _charts.daily.destroy();
      _charts.daily = new Chart(c.getContext('2d'), { type: 'bar', data: { labels: labels, datasets: [{ data: vals, backgroundColor: colors, borderRadius: 2, barPercentage: 0.7 }] }, options: ChartHelper.baseOpts({ scales: { x: { grid: { display: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 9 }, maxRotation: 45, maxTicksLimit: 30 } }, y: { grid: { color: ChartHelper.gridColor(), drawBorder: false }, ticks: { color: ChartHelper.textColor(), font: { family: 'JetBrains Mono', size: 10 }, callback: function (v) { return '$' + v; } } } } }) });
    }).catch(function () {});
  }

  function _loadBreakdown() {
    ApiClient.getPortfolioPerformance().then(function (data) {
      var perf = data.performance || {}, el = document.getElementById('port-breakdown'); if (!el) return;
      var key, title;
      if (_viewMode === 'strategy') { key = 'by_strategy'; title = 'Strategy Breakdown'; }
      else if (_viewMode === 'worker') { key = 'by_worker'; title = 'Worker Breakdown'; }
      else if (_viewMode === 'symbol') { key = 'by_symbol'; title = 'Symbol Breakdown'; }
      else { el.innerHTML = ''; return; }
      var rows = perf[key] || [];
      if (rows.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No data.</div>'; return; }
      var idKey = key === 'by_strategy' ? 'strategy_id' : key === 'by_worker' ? 'worker_id' : 'symbol';
      var html = '<section style="margin-top:20px;"><div class="section-header"><i class="fa-solid fa-table-cells"></i><h2>' + title + '</h2></div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>' + idKey.replace('_', ' ').toUpperCase() + '</th><th>Trades</th><th>P&L</th><th>Win Rate</th><th>PF</th><th>Avg Bars</th></tr></thead><tbody>';
      rows.sort(function (a, b) { return b.pnl - a.pnl; });
      rows.forEach(function (r) {
        var pc = r.pnl >= 0 ? 'text-success' : 'text-danger';
        html += '<tr><td class="mono">' + r[idKey] + '</td><td class="mono">' + r.trades + '</td><td class="mono ' + pc + '">' + _fmtMoney(r.pnl) + '</td><td class="mono">' + _fmtPct(r.win_rate) + '</td><td class="mono">' + r.profit_factor + '</td><td class="mono">' + r.avg_bars + '</td></tr>';
      });
      html += '</tbody></table></div></section>';
      el.innerHTML = html;
    }).catch(function () {});
  }

  function _loadTrades() {
    var params = { limit: 200 };
    if (_filters.strategy_id) params.strategy_id = _filters.strategy_id;
    if (_filters.worker_id) params.worker_id = _filters.worker_id;
    if (_filters.symbol) params.symbol = _filters.symbol;
    ApiClient.getPortfolioTrades(params).then(function (data) {
      var trades = data.trades || [], el = document.getElementById('port-trades'); if (!el) return;
      if (trades.length === 0) { el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No trades found.</div>'; return; }
      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>#</th><th>Symbol</th><th>Dir</th><th>Strategy</th><th>Worker</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Bars</th><th>Reason</th></tr></thead><tbody>';
      trades.forEach(function (t) {
        var pc = t.profit >= 0 ? 'text-success' : 'text-danger';
        html += '<tr><td class="mono">' + t.id + '</td><td class="mono">' + t.symbol + '</td><td><span class="state-pill ' + (t.direction === 'long' ? 'online' : 'error') + '">' + t.direction.toUpperCase() + '</span></td><td class="mono" style="font-size:10px;">' + t.strategy_id + '</td><td class="mono" style="font-size:10px;">' + t.worker_id + '</td><td class="mono">' + t.entry_price + '</td><td class="mono">' + t.exit_price + '</td><td class="mono ' + pc + '">' + _fmtMoney(t.profit) + '</td><td class="mono">' + t.bars_held + '</td><td class="mono" style="font-size:10px;">' + (t.exit_reason || '\u2014') + '</td></tr>';
      });
      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function (e) { var el = document.getElementById('port-trades'); if (el) el.innerHTML = '<div style="color:var(--danger);font-size:12px;">Error: ' + e.message + '</div>'; });
  }

  function destroy() { _destroyCharts(); }
  return { render: render, destroy: destroy };
})();

/* ============================================================
   LOGS RENDERER
   ============================================================ */
var LogsRenderer = (function () {
  'use strict';
  var _refreshInterval = null, _autoRefresh = true;

  function render() {
    var html = '<div class="fleet-page" id="logs-page">';
    html += '<div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-scroll" style="color:var(--accent);margin-right:8px;"></i>Event Logs</span><div class="fleet-page-meta"><label class="log-auto-label"><input type="checkbox" id="log-auto-check" checked /> Auto-refresh</label><button class="wd-refresh-btn" id="log-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';
    html += '<div class="log-filters">';
    html += '<div class="wd-form-group"><label class="wd-form-label">Category</label><select class="wd-form-select log-f" id="log-f-cat"><option value="">All</option><option value="system">SYSTEM</option><option value="worker">WORKER</option><option value="execution">EXECUTION</option><option value="strategy">STRATEGY</option><option value="deployment">DEPLOYMENT</option><option value="command">COMMAND</option></select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Level</label><select class="wd-form-select log-f" id="log-f-level"><option value="">All</option><option value="INFO">INFO</option><option value="WARNING">WARNING</option><option value="ERROR">ERROR</option><option value="DEBUG">DEBUG</option></select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Worker</label><input type="text" class="wd-form-input log-f" id="log-f-worker" placeholder="worker id\u2026" /></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Search</label><input type="text" class="wd-form-input log-f" id="log-f-search" placeholder="keyword\u2026" /></div>';
    html += '</div>';
    html += '<div id="log-content"><div class="loading-state" style="min-height:200px;"><div class="spinner"></div><p>Loading events\u2026</p></div></div>';
    html += '</div>';
    document.getElementById('main-content').innerHTML = html;
    _attachEvents();
    _fetch();
    _refreshInterval = setInterval(function () { if (_autoRefresh) _fetch(); }, 5000);
  }

  function _attachEvents() {
    document.getElementById('log-refresh').addEventListener('click', _fetch);
    document.getElementById('log-auto-check').addEventListener('change', function () { _autoRefresh = this.checked; });
    document.querySelectorAll('.log-f').forEach(function (el) {
      el.addEventListener('change', _fetch);
      el.addEventListener('keyup', function (e) { if (e.key === 'Enter') _fetch(); });
    });
  }

  function _fetch() {
    var params = {};
    var cat = document.getElementById('log-f-cat'); if (cat && cat.value) params.category = cat.value;
    var lvl = document.getElementById('log-f-level'); if (lvl && lvl.value) params.level = lvl.value;
    var wk = document.getElementById('log-f-worker'); if (wk && wk.value.trim()) params.worker_id = wk.value.trim();
    var search = document.getElementById('log-f-search'); if (search && search.value.trim()) params.search = search.value.trim();
    params.limit = 300;

    ApiClient.getEvents(params).then(function (data) {
      var events = data.events || [], el = document.getElementById('log-content'); if (!el) return;
      if (events.length === 0) { el.innerHTML = '<div style="padding:24px;color:var(--text-muted);font-size:12px;text-align:center;"><i class="fa-solid fa-circle-info" style="margin-right:6px;"></i>No events found matching filters.</div>'; return; }

      var html = '<div class="log-count">' + (data.count || events.length) + ' events</div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table log-table"><thead><tr><th style="width:150px;">Timestamp</th><th style="width:90px;">Category</th><th style="width:60px;">Level</th><th style="width:100px;">Type</th><th>Message</th><th style="width:80px;">Worker</th></tr></thead><tbody>';

      events.forEach(function (ev, idx) {
        var ts = (ev.timestamp || '').replace('T', ' ').substring(0, 19);
        var evCat = (ev.category || '').toUpperCase();
        var evLvl = ev.level || 'INFO';
        var lvlClass = evLvl === 'ERROR' ? 'text-danger' : evLvl === 'WARNING' ? 'text-warning' : 'text-muted';
        var catClass = '';
        if (evCat === 'EXECUTION') catClass = 'text-success';
        else if (evCat === 'STRATEGY') catClass = 'text-accent';
        else if (evCat === 'WORKER') catClass = 'text-warning';
        var msg = ev.message || '';
        var hasData = ev.data_json && ev.data_json !== 'null';
        var expandId = 'log-expand-' + idx;

        html += '<tr class="log-row' + (hasData ? ' clickable' : '') + '"' + (hasData ? ' onclick="LogsRenderer._toggle(\'' + expandId + '\')"' : '') + '>';
        html += '<td class="mono" style="font-size:10.5px;">' + ts + '</td>';
        html += '<td class="mono ' + catClass + '" style="font-size:10px;">' + evCat + '</td>';
        html += '<td class="mono ' + lvlClass + '" style="font-size:10px;font-weight:600;">' + evLvl + '</td>';
        html += '<td class="mono" style="font-size:10px;">' + (ev.event_type || '') + '</td>';
        html += '<td style="font-size:11px;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + msg + (hasData ? ' <i class="fa-solid fa-chevron-down" style="font-size:8px;opacity:0.4;margin-left:4px;"></i>' : '') + '</td>';
        html += '<td class="mono" style="font-size:10px;">' + (ev.worker_id || '\u2014') + '</td>';
        html += '</tr>';

        if (hasData) {
          var pretty = '';
          try { pretty = JSON.stringify(JSON.parse(ev.data_json), null, 2); } catch (e) { pretty = ev.data_json; }
          html += '<tr class="log-detail-row" id="' + expandId + '" style="display:none;"><td colspan="6"><pre class="log-payload">' + pretty + '</pre></td></tr>';
        }
      });

      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function (e) {
      var el = document.getElementById('log-content');
      if (el) el.innerHTML = '<div style="padding:24px;color:var(--danger);font-size:12px;">Error loading events: ' + e.message + '</div>';
    });
  }

  function _toggle(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = el.style.display === 'none' ? '' : 'none';
  }

  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }
  return { render: render, destroy: destroy, _toggle: _toggle };
})();

/* ============================================================
   SETTINGS + ADMIN RENDERER
   ============================================================ */
var SettingsRenderer = (function () {
  'use strict';

  var _settings = {};
  var _stats = {};
  var _strategies = [];
  var _workers = [];
  var _activeTab = 'general';

  function _fmtBytes(b) {
    if (b >= 1048576) return (b / 1048576).toFixed(2) + ' MB';
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KB';
    return b + ' B';
  }

  function _buildPage() {
    var html = '<div class="fleet-page">';
    html += '<div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-gear" style="margin-right:8px;color:var(--accent);"></i>Settings & Administration</span></div>';
    html += '<div class="port-tabs" id="settings-tabs">';
    html += '<button class="port-tab' + (_activeTab === 'general' ? ' active' : '') + '" data-tab="general">General Settings</button>';
    html += '<button class="port-tab' + (_activeTab === 'admin' ? ' active' : '') + '" data-tab="admin">System Management</button>';
    html += '</div>';
    html += '<div id="settings-content"></div>';
    html += '</div>';
    return html;
  }

  function _renderGeneral() {
    var s = _settings;
    var fields = [
      { key: 'refresh_interval', label: 'Dashboard Refresh Interval', type: 'number', unit: 'seconds', min: 1, max: 60 },
      { key: 'default_symbol', label: 'Default Symbol', type: 'text', placeholder: 'e.g. XAUUSD' },
      { key: 'default_bar_size', label: 'Default Bar Size', type: 'number', unit: 'points', min: 1 },
      { key: 'default_lot_size', label: 'Default Lot Size', type: 'number', step: '0.01', min: 0.01 },
      { key: 'starting_capital', label: 'Starting Capital', type: 'number', unit: '$', min: 100 },
      { key: 'worker_timeout_seconds', label: 'Worker Offline Timeout', type: 'number', unit: 'seconds', min: 10 },
      { key: 'log_verbosity', label: 'Log Verbosity', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'] },
      { key: 'debug_mode', label: 'Debug Mode', type: 'toggle' }
    ];

    var html = '<div class="wd-panel"><div class="wd-panel-header">General Settings</div><div class="wd-panel-body">';
    html += '<div class="wd-form-grid">';

    fields.forEach(function (f) {
      var val = s[f.key] || '';
      html += '<div class="wd-form-group">';
      html += '<label class="wd-form-label">' + f.label + (f.unit ? ' (' + f.unit + ')' : '') + '</label>';

      if (f.type === 'toggle') {
        var checked = val === 'true' || val === true ? ' checked' : '';
        html += '<label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" class="settings-input" data-key="' + f.key + '"' + checked + ' /> <span style="font-size:12px;color:var(--text-muted);">' + (checked ? 'Enabled' : 'Disabled') + '</span></label>';
      } else if (f.type === 'select') {
        html += '<select class="wd-form-select settings-input" data-key="' + f.key + '">';
        f.options.forEach(function (o) {
          html += '<option value="' + o + '"' + (val === o ? ' selected' : '') + '>' + o + '</option>';
        });
        html += '</select>';
      } else {
        var attrs = 'type="' + f.type + '" class="wd-form-input settings-input" data-key="' + f.key + '" value="' + val + '"';
        if (f.min !== undefined) attrs += ' min="' + f.min + '"';
        if (f.max !== undefined) attrs += ' max="' + f.max + '"';
        if (f.step) attrs += ' step="' + f.step + '"';
        if (f.placeholder) attrs += ' placeholder="' + f.placeholder + '"';
        html += '<input ' + attrs + ' />';
      }
      html += '</div>';
    });

    html += '</div>';
    html += '<div style="margin-top:16px;display:flex;gap:10px;">';
    html += '<button class="wd-btn wd-btn-primary" id="save-settings-btn"><i class="fa-solid fa-floppy-disk"></i> Save Settings</button>';
    html += '<button class="wd-btn wd-btn-ghost" id="reset-settings-btn"><i class="fa-solid fa-rotate-left"></i> Reset to Defaults</button>';
    html += '</div>';
    html += '</div></div>';
    return html;
  }

  function _renderAdmin() {
    var html = '';

    // System Stats
    html += '<div class="wd-panel"><div class="wd-panel-header" style="display:flex;justify-content:space-between;align-items:center;">System Overview';
    html += '<button class="wd-btn wd-btn-ghost" id="refresh-stats-btn" style="font-size:11px;padding:4px 10px;"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div><div class="wd-panel-body">';
    html += '<div class="wd-status-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">';
    var statCards = [
      { label: 'Database Size', value: _fmtBytes(_stats.db_size_bytes || 0) },
      { label: 'Strategies', value: _stats.strategies_count || 0 },
      { label: 'Workers', value: _stats.workers_count || 0 },
      { label: 'Active Deploys', value: _stats.active_deployments || 0 },
      { label: 'Total Trades', value: _stats.trades_count || 0 },
      { label: 'Events', value: _stats.events_count || 0 },
      { label: 'Equity Snaps', value: _stats.equity_snapshots_count || 0 },
      { label: 'Settings', value: _stats.settings_count || 0 }
    ];
    statCards.forEach(function (c) {
      html += '<div style="background:var(--bg-secondary);border-radius:8px;padding:12px;text-align:center;"><div class="mono" style="font-size:16px;font-weight:600;color:var(--accent);">' + c.value + '</div><div style="font-size:10px;color:var(--text-muted);margin-top:4px;">' + c.label + '</div></div>';
    });
    html += '</div></div></div>';

    // Strategy Management
    html += '<div class="wd-panel"><div class="wd-panel-header">Strategy Management <span class="panel-badge">' + _strategies.length + ' STRATEGIES</span></div><div class="wd-panel-body">';
    if (_strategies.length === 0) {
      html += '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No strategies registered.</div>';
    } else {
      _strategies.forEach(function (s) {
        html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;margin-bottom:6px;">' +
          '<div><span class="mono" style="color:var(--accent);font-size:12px;">' + (s.name || s.strategy_id) + '</span>' +
          '<span style="font-size:11px;color:var(--text-muted);margin-left:8px;">v' + (s.version || '?') + '</span></div>' +
          '<button class="wd-btn wd-btn-ghost admin-delete-strategy" data-sid="' + s.strategy_id + '" style="font-size:10.5px;color:var(--danger);padding:4px 10px;">' +
          '<i class="fa-solid fa-trash"></i> Delete</button></div>';
      });
    }
    html += '</div></div>';

    // Worker Management
    html += '<div class="wd-panel"><div class="wd-panel-header">Worker Management <span class="panel-badge">' + _workers.length + ' WORKERS</span></div><div class="wd-panel-body">';
    if (_workers.length === 0) {
      html += '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No workers registered.</div>';
    } else {
      _workers.forEach(function (w) {
        var stateClass = w.state || 'unknown';
        html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;margin-bottom:6px;">' +
          '<div><span class="mono" style="font-size:12px;">' + (w.worker_name || w.worker_id) + '</span>' +
          '<span class="state-pill ' + stateClass + '" style="margin-left:8px;">' + stateClass.toUpperCase() + '</span></div>' +
          '<button class="wd-btn wd-btn-ghost admin-remove-worker" data-wid="' + w.worker_id + '" style="font-size:10.5px;color:var(--danger);padding:4px 10px;">' +
          '<i class="fa-solid fa-trash"></i> Remove</button></div>';
      });
    }
    html += '<button class="wd-btn wd-btn-ghost" id="remove-stale-btn" style="margin-top:8px;font-size:11px;"><i class="fa-solid fa-broom"></i> Remove All Stale Workers</button>';
    html += '</div></div>';

    // Portfolio Management
    html += '<div class="wd-panel"><div class="wd-panel-header">Portfolio Management</div><div class="wd-panel-body">';
    html += '<div style="display:flex;flex-wrap:wrap;gap:10px;">';
    html += '<button class="wd-btn wd-btn-ghost" id="admin-clear-trades"><i class="fa-solid fa-eraser"></i> Delete All Trades (' + (_stats.trades_count || 0) + ')</button>';
    html += '<button class="wd-btn wd-btn-ghost" id="admin-reset-portfolio"><i class="fa-solid fa-rotate-left"></i> Reset Portfolio (Trades + Equity)</button>';
    html += '</div></div></div>';

    // Log Management
    html += '<div class="wd-panel"><div class="wd-panel-header">Log Management</div><div class="wd-panel-body">';
    html += '<div style="display:flex;flex-wrap:wrap;gap:10px;">';
    html += '<button class="wd-btn wd-btn-ghost" id="admin-clear-events"><i class="fa-solid fa-eraser"></i> Clear All Events (' + (_stats.events_count || 0) + ')</button>';
    html += '</div></div></div>';

    // Danger Zone
    html += '<div class="wd-panel" style="border:1px solid var(--danger);">';
    html += '<div class="wd-panel-header" style="color:var(--danger);"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px;"></i>Danger Zone</div><div class="wd-panel-body">';
    html += '<p style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">Full system reset deletes ALL trades, events, deployments, and equity data. Workers are set offline. Strategies and settings are preserved.</p>';
    html += '<button class="wd-btn" id="admin-full-reset" style="background:rgba(239,68,68,0.15);color:var(--danger);font-weight:600;border:1px solid var(--danger);"><i class="fa-solid fa-skull-crossbones"></i> Full System Reset</button>';
    html += '</div></div>';

    return html;
  }

  function _renderTab() {
    var el = document.getElementById('settings-content');
    if (!el) return;
    if (_activeTab === 'general') {
      el.innerHTML = _renderGeneral();
      _attachGeneralEvents();
    } else {
      el.innerHTML = _renderAdmin();
      _attachAdminEvents();
    }
  }

  function _attachGeneralEvents() {
    var saveBtn = document.getElementById('save-settings-btn');
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var updated = {};
        document.querySelectorAll('.settings-input').forEach(function (input) {
          var key = input.getAttribute('data-key');
          if (input.type === 'checkbox') {
            updated[key] = input.checked ? 'true' : 'false';
          } else {
            updated[key] = input.value;
          }
        });
        ApiClient.saveSettings(updated).then(function (data) {
          _settings = data.settings || {};
          ToastManager.show('Settings saved.', 'success');
        }).catch(function () { ToastManager.show('Failed to save settings.', 'error'); });
      });
    }
    var resetBtn = document.getElementById('reset-settings-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        var defaults = {
          refresh_interval: '5', default_symbol: 'XAUUSD', default_bar_size: '100',
          default_lot_size: '0.01', starting_capital: '10000', worker_timeout_seconds: '90',
          log_verbosity: 'INFO', debug_mode: 'true'
        };
        ApiClient.saveSettings(defaults).then(function (data) {
          _settings = data.settings || {};
          _renderTab();
          ToastManager.show('Settings reset to defaults.', 'info');
        }).catch(function () { ToastManager.show('Failed to reset settings.', 'error'); });
      });
    }
  }

  function _attachAdminEvents() {
    var refreshBtn = document.getElementById('refresh-stats-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function () { _loadData(); });
    }

    document.querySelectorAll('.admin-delete-strategy').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var sid = btn.getAttribute('data-sid');
        ModalManager.show({
          title: 'Delete Strategy', type: 'danger',
          bodyHtml: '<p>Delete strategy <strong>' + sid + '</strong>? This removes the strategy file and all deployment records.</p>',
          confirmText: 'Delete',
          onConfirm: function () {
            ApiClient.adminDeleteStrategy(sid).then(function () {
              ToastManager.show('Strategy ' + sid + ' deleted.', 'success');
              _loadData();
            }).catch(function () { ToastManager.show('Delete failed.', 'error'); });
          }
        });
      });
    });

    document.querySelectorAll('.admin-remove-worker').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var wid = btn.getAttribute('data-wid');
        ModalManager.show({
          title: 'Remove Worker', type: 'danger',
          bodyHtml: '<p>Remove worker <strong>' + wid + '</strong>? Active deployments will be stopped.</p>',
          confirmText: 'Remove',
          onConfirm: function () {
            ApiClient.adminRemoveWorker(wid).then(function () {
              ToastManager.show('Worker removed.', 'success');
              _loadData();
            }).catch(function () { ToastManager.show('Remove failed.', 'error'); });
          }
        });
      });
    });

    var staleBtn = document.getElementById('remove-stale-btn');
    if (staleBtn) {
      staleBtn.addEventListener('click', function () {
        ModalManager.show({
          title: 'Remove Stale Workers',
          bodyHtml: '<p>Remove all workers that haven\'t sent a heartbeat in over 5 minutes?</p>',
          confirmText: 'Remove Stale',
          onConfirm: function () {
            ApiClient.adminRemoveStaleWorkers().then(function (d) {
              ToastManager.show((d.removed || 0) + ' stale workers removed.', 'success');
              _loadData();
            }).catch(function () { ToastManager.show('Failed.', 'error'); });
          }
        });
      });
    }

    var clearTradesBtn = document.getElementById('admin-clear-trades');
    if (clearTradesBtn) {
      clearTradesBtn.addEventListener('click', function () {
        ModalManager.show({
          title: 'Delete All Trades', type: 'danger',
          bodyHtml: '<p>Delete ALL trade records? This cannot be undone.</p>',
          confirmText: 'Delete All Trades',
          onConfirm: function () {
            ApiClient.adminClearTrades().then(function (d) {
              ToastManager.show((d.trades_deleted || 0) + ' trades deleted.', 'success');
              _loadData();
            }).catch(function () { ToastManager.show('Failed.', 'error'); });
          }
        });
      });
    }

    var resetPortBtn = document.getElementById('admin-reset-portfolio');
    if (resetPortBtn) {
      resetPortBtn.addEventListener('click', function () {
        ModalManager.show({
          title: 'Reset Portfolio', type: 'danger',
          bodyHtml: '<p>Reset entire portfolio? This deletes all trades AND equity history.</p>',
          confirmText: 'Reset Portfolio',
          onConfirm: function () {
            ApiClient.adminResetPortfolio().then(function () {
              ToastManager.show('Portfolio reset.', 'success');
              _loadData();
            }).catch(function () { ToastManager.show('Failed.', 'error'); });
          }
        });
      });
    }

    var clearEventsBtn = document.getElementById('admin-clear-events');
    if (clearEventsBtn) {
      clearEventsBtn.addEventListener('click', function () {
        ModalManager.show({
          title: 'Clear All Events',
          bodyHtml: '<p>Delete all event log entries?</p>',
          confirmText: 'Clear Events',
          onConfirm: function () {
            ApiClient.adminClearEvents().then(function (d) {
              ToastManager.show((d.events_cleared || 0) + ' events cleared.', 'success');
              _loadData();
            }).catch(function () { ToastManager.show('Failed.', 'error'); });
          }
        });
      });
    }

    var fullResetBtn = document.getElementById('admin-full-reset');
    if (fullResetBtn) {
      fullResetBtn.addEventListener('click', function () {
        ModalManager.show({
          title: '\u26A0\uFE0F FULL SYSTEM RESET', type: 'danger',
          bodyHtml: '<p>This will delete <strong>ALL</strong> trades, events, deployments, and equity data.</p>' +
            '<p style="color:var(--danger);font-weight:600;margin-top:8px;"><i class="fa-solid fa-triangle-exclamation"></i> This action is irreversible. Only strategies and settings are preserved.</p>',
          confirmText: 'RESET EVERYTHING',
          onConfirm: function () {
            ApiClient.adminFullReset().then(function () {
              ToastManager.show('System reset complete.', 'warning');
              _loadData();
            }).catch(function () { ToastManager.show('Reset failed.', 'error'); });
          }
        });
      });
    }
  }

  function _loadData() {
    Promise.all([
      ApiClient.getSettings().catch(function () { return { settings: {} }; }),
      ApiClient.getAdminStats().catch(function () { return { stats: {} }; }),
      ApiClient.getStrategies().catch(function () { return { strategies: [] }; }),
      ApiClient.getFleetWorkers().catch(function () { return { workers: [] }; })
    ]).then(function (results) {
      _settings = (results[0] && results[0].settings) || {};
      _stats = (results[1] && results[1].stats) || {};
      _strategies = (results[2] && results[2].strategies) || [];
      var fleetData = results[3] || {};
      _workers = fleetData.workers || [];
      _renderTab();
    }).catch(function () {
      var el = document.getElementById('settings-content');
      if (el) el.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted);"><i class="fa-solid fa-circle-exclamation" style="font-size:32px;opacity:0.3;margin-bottom:12px;display:block;"></i><h3 style="margin-bottom:4px;">Failed to Load</h3><p style="font-size:12px;">Could not reach server.</p></div>';
    });
  }

  function render() {
    var el = document.getElementById('main-content');
    el.innerHTML = _buildPage();

    document.querySelectorAll('#settings-tabs .port-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        _activeTab = tab.getAttribute('data-tab');
        document.querySelectorAll('#settings-tabs .port-tab').forEach(function (t) { t.classList.remove('active'); });
        tab.classList.add('active');
        _renderTab();
      });
    });

    _loadData();
  }

  function destroy() {}

  return { render: render, destroy: destroy };
})();

/* ============================================================
   APP (NAVIGATION)
   ============================================================ */
var App = (function () {
  'use strict';
  var currentPage = 'dashboard', _selectedWorker = null;

  function init() { ThemeManager.init(); setupNavigation(); startClock(); navigateTo('dashboard'); }

  function setupNavigation() {
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.addEventListener('click', function (e) { e.preventDefault(); navigateTo(item.getAttribute('data-page')); });
    });
  }

  function navigateTo(page) {
    if (currentPage === 'dashboard') DashboardRenderer.destroy();
    if (currentPage === 'fleet') FleetRenderer.destroy();
    if (currentPage === 'workerDetail') WorkerDetailRenderer.destroy();
    if (currentPage === 'strategies') StrategiesRenderer.destroy();
    if (currentPage === 'portfolio') PortfolioRenderer.destroy();
    if (currentPage === 'logs') LogsRenderer.destroy();
    if (currentPage === 'settings') SettingsRenderer.destroy();
    currentPage = page;
    var navPage = page === 'workerDetail' ? 'fleet' : page;
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) { item.classList.toggle('active', item.getAttribute('data-page') === navPage); });
    var titleMap = { workerDetail: 'Worker Detail', portfolio: 'Portfolio', logs: 'Logs', settings: 'Settings' };
    document.getElementById('topbar-title').textContent = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));
    if (page === 'dashboard') DashboardRenderer.render();
    else if (page === 'fleet') FleetRenderer.render();
    else if (page === 'workerDetail' && _selectedWorker) WorkerDetailRenderer.render(_selectedWorker);
    else if (page === 'strategies') StrategiesRenderer.render();
    else if (page === 'portfolio') PortfolioRenderer.render();
    else if (page === 'logs') LogsRenderer.render();
    else if (page === 'settings') SettingsRenderer.render();
    else renderPlaceholder(page);
  }

  function navigateToWorkerDetail(workerData) { _selectedWorker = workerData; navigateTo('workerDetail'); }

  function renderPlaceholder(page) {
    document.getElementById('main-content').innerHTML = '<div class="placeholder-page"><i class="fa-solid fa-gear"></i><h2>' + (page.charAt(0).toUpperCase() + page.slice(1)) + '</h2><p>Under development.</p></div>';
  }

  function startClock() { function u() { var n = new Date(); document.getElementById('topbar-clock').textContent = String(n.getHours()).padStart(2, '0') + ':' + String(n.getMinutes()).padStart(2, '0') + ':' + String(n.getSeconds()).padStart(2, '0'); } u(); setInterval(u, 1000); }

  document.addEventListener('DOMContentLoaded', init);
  return { navigateTo: navigateTo, navigateToWorkerDetail: navigateToWorkerDetail };
})();