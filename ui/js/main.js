/* ================================================================
   JINNI GRID — Professional Trading Dashboard
   ui/js/main.js — Complete UI Module (FULL VERSION)
   
   Sections:
   1. ApiClient
   2. ModalManager / ToastManager / ThemeManager
   3. ChartHelper
   4. Formatting Utilities
   5. Reusable UI Components
   6. DashboardRenderer (with Portfolio Summary Strip)
   7. FleetRenderer
   8. StrategiesRenderer
   9. PortfolioRenderer (5 sub-tabs: Overview, Equity&Risk, Strategies, VMs, Trades)
   10. LogsRenderer
   11. SettingsRenderer (General + Admin)
   12. App (Navigation)
   ================================================================ */

/* ================================================================
   1. API CLIENT
   ================================================================ */
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
          try {
            var j = JSON.parse(text);
            if (j.detail) msg = typeof j.detail === 'string' ? j.detail : (j.detail.error || JSON.stringify(j.detail));
          } catch (e) { if (text) msg = text; }
          var err = new Error(msg);
          err.status = res.status;
          throw err;
        });
      }
      return res.json();
    });
  }

  function _queryString(params) {
    var q = [];
    if (params) {
      for (var k in params) {
        if (params[k] !== null && params[k] !== undefined && params[k] !== '') {
          q.push(k + '=' + encodeURIComponent(params[k]));
        }
      }
    }
    return q.length ? '?' + q.join('&') : '';
  }

  function _upload(path, file) {
    var fd = new FormData();
    fd.append('file', file);
    return fetch(path, { method: 'POST', body: fd }).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (t) {
          var m = 'HTTP ' + res.status;
          try { var j = JSON.parse(t); if (j.detail) m = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail); } catch (e) { if (t) m = t; }
          throw new Error(m);
        });
      }
      return res.json();
    });
  }

  return {
    /* Fleet / Workers */
    getFleetWorkers: function () { return _request('GET', '/api/Grid/workers'); },
    getSystemSummary: function () { return _request('GET', '/api/system/summary'); },
    getHealth: function () { return _request('GET', '/api/health'); },

    /* Strategies */
    getStrategies: function () { return _request('GET', '/api/grid/strategies'); },
    getStrategy: function (id) { return _request('GET', '/api/grid/strategies/' + encodeURIComponent(id)); },
    uploadStrategy: function (file) { return _upload('/api/grid/strategies/upload', file); },
    validateStrategy: function (id) { return _request('POST', '/api/grid/strategies/' + encodeURIComponent(id) + '/validate'); },

    /* Deployments */
    createDeployment: function (cfg) { return _request('POST', '/api/grid/deployments', cfg); },
    getDeployments: function () { return _request('GET', '/api/grid/deployments'); },
    getDeployment: function (id) { return _request('GET', '/api/grid/deployments/' + encodeURIComponent(id)); },
    stopDeployment: function (id) { return _request('POST', '/api/grid/deployments/' + encodeURIComponent(id) + '/stop'); },

    /* Portfolio (all accept filter params) */
    getPortfolioSummary: function (params) { return _request('GET', '/api/portfolio/summary' + _queryString(params)); },
    getEquityHistory: function () { return _request('GET', '/api/portfolio/equity-history'); },
    getPortfolioTrades: function (params) { return _request('GET', '/api/portfolio/trades' + _queryString(params)); },
    getPortfolioPerformance: function (params) { return _request('GET', '/api/portfolio/performance' + _queryString(params)); },

    /* Events */
    getEvents: function (params) { return _request('GET', '/api/events' + _queryString(params)); },

    /* Settings */
    getSettings: function () { return _request('GET', '/api/settings'); },
    saveSettings: function (settings) { return _request('PUT', '/api/settings', { settings: settings }); },

    /* Admin */
    getAdminStats: function () { return _request('GET', '/api/admin/stats'); },
    adminDeleteStrategy: function (sid) { return _request('POST', '/api/admin/strategies/' + sid + '/delete'); },
    adminResetPortfolio: function () { return _request('POST', '/api/admin/portfolio/reset'); },
    adminClearTrades: function () { return _request('POST', '/api/admin/trades/clear'); },
    adminRemoveWorker: function (wid) { return _request('POST', '/api/admin/workers/' + wid + '/remove'); },
    adminRemoveStaleWorkers: function () { return _request('POST', '/api/admin/workers/stale/remove'); },
    adminClearEvents: function () { return _request('POST', '/api/admin/events/clear'); },
    adminFullReset: function () { return _request('POST', '/api/admin/system/reset', { confirm: 'RESET_EVERYTHING' }); },
    emergencyStopAll: function () { return _request('POST', '/api/admin/emergency-stop'); }
  };
})();

/* ── DEPLOYMENT CONFIG ──────────────────────────────────────── */
var DeploymentConfig = (function () {
  'use strict';
  return {
    runtimeDefaults: {
      symbol: 'EURUSD',
      lot_size: 0.01,
      tick_lookback_value: 30,
      tick_lookback_unit: 'minutes',
      bar_size_points: 100,
      max_bars_memory: 500
    },
    symbolOptions: [
      'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF',
      'NZDUSD', 'XAUUSD', 'BTCUSD', 'USTEC', 'SPX500', 'DOW30', 'FTSE100'
    ],
    tickLookbackUnits: ['minutes', 'hours', 'days']
  };
})();

/* ================================================================
   2. MODAL / TOAST / THEME MANAGERS
   ================================================================ */
var ModalManager = (function () {
  'use strict';
  var _overlay = null;

  function show(options) {
    hide();
    var title = options.title || 'Confirm';
    var bodyHtml = options.bodyHtml || '';
    var confirmText = options.confirmText || 'Confirm';
    var cancelText = options.cancelText || 'Cancel';
    var type = options.type || 'default';
    var onConfirm = options.onConfirm || function () {};
    var confirmStyle = type === 'danger' ? ' style="background:var(--danger);"' : '';

    _overlay = document.createElement('div');
    _overlay.className = 'modal-overlay';
    _overlay.innerHTML =
      '<div class="modal-card">' +
        '<div class="modal-header">' +
          '<span class="modal-title">' + title + '</span>' +
          '<button class="modal-close" id="modal-close">&times;</button>' +
        '</div>' +
        '<div class="modal-body">' + bodyHtml + '</div>' +
        '<div class="modal-footer">' +
          '<button class="wd-btn wd-btn-ghost" id="modal-cancel">' + cancelText + '</button>' +
          '<button class="wd-btn wd-btn-primary" id="modal-confirm"' + confirmStyle + '>' + confirmText + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(_overlay);
    _overlay.querySelector('#modal-close').addEventListener('click', hide);
    _overlay.querySelector('#modal-cancel').addEventListener('click', hide);
    _overlay.querySelector('#modal-confirm').addEventListener('click', function () { onConfirm(); hide(); });
    _overlay.addEventListener('click', function (e) { if (e.target === _overlay) hide(); });
  }

  function hide() {
    if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay);
    _overlay = null;
  }

  return { show: show, hide: hide };
})();

var ToastManager = (function () {
  'use strict';
  var iconMap = {
    success: 'fa-circle-check',
    info: 'fa-circle-info',
    warning: 'fa-triangle-exclamation',
    error: 'fa-circle-xmark'
  };

  function _getContainer() {
    var c = document.querySelector('.toast-container');
    if (!c) { c = document.createElement('div'); c.className = 'toast-container'; document.body.appendChild(c); }
    return c;
  }

  function show(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;
    var container = _getContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML = '<i class="fa-solid ' + (iconMap[type] || iconMap.info) + '"></i><span>' + message + '</span><button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';
    container.appendChild(toast);
    toast.querySelector('.toast-dismiss').addEventListener('click', function () { _remove(toast); });
    setTimeout(function () { _remove(toast); }, duration);
  }

  function _remove(toast) {
    if (!toast || !toast.parentNode) return;
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 300);
  }

  return { show: show };
})();

var ThemeManager = (function () {
  'use strict';
  var STORAGE_KEY = 'jinni-Grid-theme';
  var currentTheme = 'dark';

  function init() {
    var saved = localStorage.getItem(STORAGE_KEY);
    currentTheme = saved === 'light' ? 'light' : 'dark';
    applyTheme();
    updateToggleButton();
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggle);
  }

  function toggle() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, currentTheme);
    applyTheme();
    updateToggleButton();
  }

  function applyTheme() { document.body.setAttribute('data-theme', currentTheme); }

  function updateToggleButton() {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var icon = btn.querySelector('i');
    var label = btn.querySelector('span');
    if (currentTheme === 'dark') {
      icon.className = 'fa-solid fa-sun';
      label.textContent = 'Light Mode';
    } else {
      icon.className = 'fa-solid fa-moon';
      label.textContent = 'Dark Mode';
    }
  }

  function getTheme() { return currentTheme; }
  return { init: init, toggle: toggle, getTheme: getTheme };
})();


/* ================================================================
   3. CHART HELPER
   ================================================================ */
var ChartHelper = (function () {
  'use strict';
  function _isDark() { return ThemeManager.getTheme() === 'dark'; }

  function gridColor() { return _isDark() ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'; }
  function textColor() { return _isDark() ? '#94a3b8' : '#475569'; }
  function accentColor() { return '#06b6d4'; }
  function successColor() { return '#10b981'; }
  function dangerColor() { return '#ef4444'; }
  function warningColor() { return '#f59e0b'; }
  function purpleColor() { return '#8b5cf6'; }
  function tooltipBg() { return _isDark() ? '#1e293b' : '#ffffff'; }
  function tooltipColor() { return _isDark() ? '#e2e8f0' : '#1e293b'; }

  function baseLineOpts(extraOpts) {
    var o = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltipBg(),
          titleColor: tooltipColor(),
          bodyColor: tooltipColor(),
          borderColor: gridColor(),
          borderWidth: 1,
          cornerRadius: 6,
          padding: 10,
          titleFont: { family: 'Inter', size: 11 },
          bodyFont: { family: 'JetBrains Mono', size: 10 },
          callbacks: {
            label: function (ctx) { return '$' + (ctx.parsed.y || 0).toFixed(2); }
          }
        }
      },
      scales: {
        x: {
          grid: { color: gridColor(), drawBorder: false },
          ticks: { color: textColor(), font: { family: 'JetBrains Mono', size: 9 }, maxRotation: 0, maxTicksLimit: 12 }
        },
        y: {
          grid: { color: gridColor(), drawBorder: false },
          ticks: { color: textColor(), font: { family: 'JetBrains Mono', size: 9 } }
        }
      },
      interaction: { mode: 'index', intersect: false },
      animation: { duration: 500 }
    };
    if (extraOpts) { for (var k in extraOpts) o[k] = extraOpts[k]; }
    return o;
  }

  return {
    gridColor: gridColor, textColor: textColor, accentColor: accentColor,
    successColor: successColor, dangerColor: dangerColor, warningColor: warningColor,
    purpleColor: purpleColor, tooltipBg: tooltipBg, tooltipColor: tooltipColor,
    baseLineOpts: baseLineOpts
  };
})();


/* ================================================================
   4. FORMATTING UTILITIES (2-decimal, no float garbage)
   ================================================================ */
function _fmtMoney(v) {
  if (v === null || v === undefined) return '\u2014';
  var n = Math.round(Number(v) * 100) / 100;
  if (isNaN(n)) return '\u2014';
  var abs = Math.abs(n).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  if (n > 0) return '+$' + abs;
  if (n < 0) return '-$' + abs;
  return '$0.00';
}

function _fmtPct(v) {
  if (v === null || v === undefined) return '\u2014';
  return (Math.round(v * 10) / 10).toFixed(1) + '%';
}

function _fmtNum(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return String(Math.round(n * 100) / 100);
}

function _fmtAge(seconds) {
  if (seconds === null || seconds === undefined) return '\u2014';
  var s = Math.round(seconds);
  if (s < 60) return s + 's ago';
  if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
  return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
}

function _nullVal(val, fallback) {
  if (val === null || val === undefined || val === '') {
    return '<span style="opacity:0.4;">' + (fallback || '\u2014') + '</span>';
  }
  return String(val);
}


/* ================================================================
   5. REUSABLE UI COMPONENTS
   ================================================================ */
function _spinner(minHeight) {
  return '<div class="loading-state" style="min-height:' + (minHeight || 120) + 'px;"><div class="spinner"></div></div>';
}

function _emptyState(icon, title, subtitle) {
  return '<div style="padding:48px 24px;text-align:center;color:var(--text-muted);">' +
    '<i class="fa-solid ' + icon + '" style="font-size:36px;opacity:0.15;display:block;margin-bottom:14px;"></i>' +
    '<div style="font-weight:600;font-size:13px;margin-bottom:4px;">' + title + '</div>' +
    (subtitle ? '<div style="font-size:11px;opacity:0.6;">' + subtitle + '</div>' : '') +
    '</div>';
}

function _metricItem(label, value, colorClass) {
  return '<div style="text-align:center;min-width:80px;">' +
    '<div class="mono' + (colorClass ? ' ' + colorClass : '') + '" style="font-size:15px;font-weight:700;line-height:1.2;">' + value + '</div>' +
    '<div style="font-size:10px;color:var(--text-muted);margin-top:3px;white-space:nowrap;">' + label + '</div>' +
    '</div>';
}

function _metricPill(label, value, colorClass) {
  return '<div class="metric-pill">' +
    '<div class="metric-pill-value mono' + (colorClass ? ' ' + colorClass : '') + '">' + value + '</div>' +
    '<div class="metric-pill-label">' + label + '</div>' +
    '</div>';
}

function _statPill(text, type) {
  return '<span class="state-pill ' + (type || '') + '">' + text + '</span>';
}

function _sectionHeader(icon, title, badge) {
  return '<div class="section-header"><i class="fa-solid ' + icon + '"></i><h2>' + title + '</h2>' +
    (badge ? '<span class="section-badge">' + badge + '</span>' : '') +
    '</div>';
}

function _fleetBadge(count, label, type) {
  return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count + '</span><span class="badge-label">' + label + '</span></div>';
}


/* ================================================================
   6. DASHBOARD RENDERER (with Portfolio Summary Strip)
   ================================================================ */
var DashboardRenderer = (function () {
  'use strict';
  var _intervals = [];
  var _charts = {};
  var _lastFleetWorkers = [];

  function _destroyCharts() {
    for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } }
  }

  function render() {
    var html = '<div class="dashboard">';

    /* ── Top Dashboard Strip (Portfolio + System — unified) ─── */
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;" id="dash-top-strip">';

    /* Left: Portfolio */
    html += '<div class="dash-panel">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">';
    html += '<div style="display:flex;align-items:center;gap:8px;"><i class="fa-solid fa-briefcase" style="color:var(--accent);font-size:13px;"></i><span style="font-weight:600;font-size:13px;">Portfolio</span><span class="section-badge">LIVE</span></div>';
    html += '<button class="wd-btn wd-btn-ghost" onclick="App.navigateTo(\'portfolio\')" style="font-size:10px;padding:3px 8px;">Analytics <i class="fa-solid fa-arrow-right" style="margin-left:3px;"></i></button>';
    html += '</div>';
    html += '<div id="dash-strip-content" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:10px;">' + _spinner(50) + '</div>';
    html += '</div>';

    /* Right: System Health */
    html += '<div class="dash-panel">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">';
    html += '<div style="display:flex;align-items:center;gap:8px;"><i class="fa-solid fa-gauge-high" style="color:var(--accent);font-size:13px;"></i><span style="font-weight:600;font-size:13px;">System Health</span><span class="section-badge">LIVE</span></div>';
    html += '<button class="wd-btn" id="dash-emergency-stop" style="background:rgba(239,68,68,0.1);color:var(--danger);font-size:10px;padding:3px 8px;border:1px solid rgba(239,68,68,0.3);font-weight:600;"><i class="fa-solid fa-circle-stop"></i> STOP</button>';
    html += '</div>';
    html += '<div id="dash-kpi" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:10px;">' + _spinner(50) + '</div>';
    html += '</div>';

    html += '</div>';

    /* ── Charts Row ──────────────────────────────────────────── */
    html += '<div class="dash-split-row">';
    html += '<section class="dash-chart-section dash-panel">' + _sectionHeader('fa-chart-area', 'Equity Curve');
    html += '<div style="margin-top:12px;"><div class="chart-wrapper" id="dash-equity-wrap"><canvas id="dash-equity-chart"></canvas></div></div></section>';
    html += '<section class="dash-stats-section dash-panel">' + _sectionHeader('fa-chart-pie', 'Portfolio Stats');
    html += '<div id="dash-port-stats" class="dash-stats-grid">' + _spinner(200) + '</div></section>';
    html += '</div>';

    /* ── Fleet + Pipeline + Strategies Row ────────────────────── */
    html += '<div class="dash-triple-row">';
    html += '<section class="dash-panel">' + _sectionHeader('fa-server', 'Fleet Health', 'LIVE') + '<div id="dash-fleet" class="dash-panel-body">' + _spinner() + '</div></section>';
    html += '<section class="dash-panel">' + _sectionHeader('fa-diagram-project', 'Pipeline') + '<div id="dash-pipeline" class="dash-panel-body">' + _spinner() + '</div></section>';
    html += '<section class="dash-panel">' + _sectionHeader('fa-crosshairs', 'Active Strategies') + '<div id="dash-strategies" class="dash-panel-body">' + _spinner() + '</div></section>';
    html += '</div>';

    /* ── Trades + Deployments Row ─────────────────────────────── */
    html += '<div class="dash-dual-row">';
    html += '<section class="dash-panel">' + _sectionHeader('fa-receipt', 'Recent Trades') + '<div id="dash-trades" class="dash-panel-body">' + _spinner() + '</div></section>';
    html += '<section class="dash-panel">' + _sectionHeader('fa-rocket', 'Deployments', 'LIVE') + '<div id="dash-deploys" class="dash-panel-body">' + _spinner() + '</div></section>';
    html += '</div>';

    html += '</div>';
    document.getElementById('main-content').innerHTML = html;

    /* Emergency stop handler */
    document.getElementById('dash-emergency-stop').addEventListener('click', function () {
      ModalManager.show({
        title: '\u26A0 EMERGENCY STOP ALL',
        type: 'danger',
        bodyHtml: '<p style="font-weight:600;color:var(--danger);">This will immediately:</p>' +
          '<ul style="font-size:12px;color:var(--text-muted);margin:8px 0;">' +
          '<li>Stop all running strategies</li>' +
          '<li>Close ALL open positions at market</li>' +
          '<li>Set all deployments to STOPPED</li></ul>',
        confirmText: 'STOP EVERYTHING',
        onConfirm: function () {
          ApiClient.emergencyStopAll().then(function (r) {
            ToastManager.show('Emergency stop: ' + (r.deployments_stopped || 0) + ' deployments stopped, ' + (r.commands_sent || 0) + ' commands sent.', 'warning', 8000);
          }).catch(function (e) { ToastManager.show('Failed: ' + e.message, 'error'); });
        }
      });
    });

    _fetchAll();
    _intervals.push(setInterval(_fetchLive, 10000));
  }

  function _fetchAll() {
    _fetchPortfolioStrip();
    _fetchKPIs();
    _fetchEquity();
    _fetchPortStats();
    _fetchFleet();
    _fetchPipeline();
    _fetchStrategies();
    _fetchTrades();
    _fetchDeploys();
  }

  function _fetchLive() {
    _fetchPortfolioStrip();
    _fetchKPIs();
    _fetchFleet();
    _fetchPipeline();
    _fetchDeploys();
  }

  /* ── Portfolio Summary Strip ──────────────────────────────── */
  function _fetchPortfolioStrip() {
    ApiClient.getPortfolioSummary().catch(function () { return { portfolio: {} }; }).then(function (r) {
      var p = r.portfolio || {};
      var el = document.getElementById('dash-strip-content');
      if (!el) return;
      var hasAcc = p.has_account_data;
      el.innerHTML =
        _metricPill('Equity', hasAcc ? ('$' + _fmtNum(p.total_equity || 0)) : (p.net_pnl ? _fmtMoney(p.net_pnl) : 'N/A'), hasAcc ? '' : ((p.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger')) +
        _metricPill('Balance', hasAcc ? ('$' + _fmtNum(p.total_balance || 0)) : '\u2014') +
        _metricPill('Realized', _fmtMoney(p.net_pnl), (p.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger') +
        _metricPill('Floating', _fmtMoney(p.floating_pnl), (p.floating_pnl || 0) >= 0 ? 'text-success' : 'text-danger') +
        _metricPill('Max DD', _fmtPct(p.max_drawdown_pct), 'text-danger') +
        _metricPill('PF', String(p.profit_factor || 0), (p.profit_factor || 0) >= 1 ? 'text-success' : '') +
        _metricPill('Expectancy', _fmtMoney(p.expectancy), (p.expectancy || 0) >= 0 ? 'text-success' : 'text-danger') +
        _metricPill('Trades', String(p.total_trades || 0));
    });
  }

  function _fetchKPIs() {
    Promise.all([
      ApiClient.getFleetWorkers().catch(function () { return { workers: [], summary: {} }; }),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; }),
      ApiClient.getEvents({ limit: 1, level: 'ERROR' }).catch(function () { return { events: [] }; })
    ]).then(function (r) {
      var workers = r[0].workers || [];
      var fleet = r[0].summary || {};
      var deps = r[1].deployments || [];
      var lastErrors = r[2].events || [];
      var el = document.getElementById('dash-kpi');
      if (!el) return;

      var running = deps.filter(function (d) { return d.state === 'running'; }).length;
      var totalDeps = deps.length;
      var totalPositions = 0;
      var totalTicks = 0;
      var totalBars = 0;
      var totalBarsInMem = 0;
      var totalSignals = 0;
      var totalOnBar = 0;
      var mt5Connected = 0;
      var freshestHb = Infinity;
      var errorWorkers = 0;

      workers.forEach(function (w) {
        totalPositions += (w.open_positions_count || 0);
        totalTicks += (w.total_ticks || 0);
        totalBars += (w.total_bars || 0);
        totalBarsInMem += (w.current_bars_in_memory || 0);
        totalSignals += (w.signal_count || 0);
        totalOnBar += (w.on_bar_calls || 0);
        if (w.mt5_state === 'connected') mt5Connected++;
        if (w.errors && w.errors.length > 0) errorWorkers++;
        var age = w.heartbeat_age_seconds || 999;
        if (age < freshestHb) freshestHb = age;
      });

      var hbLabel = workers.length === 0 ? 'N/A' : (freshestHb < 60 ? Math.round(freshestHb) + 's' : Math.round(freshestHb / 60) + 'm');
      var lastErrLabel = 'None';
      if (lastErrors.length > 0 && lastErrors[0].timestamp) {
        try { lastErrLabel = lastErrors[0].timestamp.replace('T', ' ').substring(11, 19); } catch (e) { lastErrLabel = 'Error'; }
      }

      var barsLabel = _fmtNum(totalBars) + (totalBarsInMem > 0 ? ' (' + totalBarsInMem + ')' : '');

      el.innerHTML =
        _metricPill('Workers', (fleet.online_workers || 0) + '/' + (fleet.total_workers || 0), (fleet.online_workers || 0) > 0 ? 'text-success' : '') +
        _metricPill('MT5', mt5Connected + '/' + workers.length, mt5Connected === workers.length && workers.length > 0 ? 'text-success' : mt5Connected > 0 ? 'text-warning' : '') +
        _metricPill('Strategies', running + ' running', running > 0 ? 'text-success' : '') +
        _metricPill('Deploys', totalDeps + ' total') +
        _metricPill('Positions', String(totalPositions), totalPositions > 0 ? 'text-accent' : '') +
        _metricPill('Ticks', _fmtNum(totalTicks)) +
        _metricPill('Bars', barsLabel) +
        _metricPill('Signals', _fmtNum(totalSignals), totalSignals > 0 ? 'text-success' : '') +
        _metricPill('Last HB', hbLabel, freshestHb < 30 ? 'text-success' : freshestHb < 90 ? 'text-warning' : 'text-danger') +
        _metricPill('Last Error', lastErrLabel, lastErrors.length > 0 ? 'text-danger' : 'text-success');
    }).catch(function (err) {
      console.error('[DASHBOARD] System Health KPIs failed:', err);
      var el = document.getElementById('dash-kpi');
      if (el) el.innerHTML = '<div style="color:var(--danger);font-size:11px;padding:8px;"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px;"></i>Failed to load system health.</div>';
    });
  }

  /* ── Equity Chart ─────────────────────────────────────────── */
  function _fetchEquity() {
    ApiClient.getEquityHistory().then(function (data) {
      var hist = data.equity_history || [];
      if (hist.length === 0) {
        var wrap = document.getElementById('dash-equity-wrap');
        if (wrap) wrap.innerHTML = _emptyState('fa-chart-area', 'No Equity Data Yet', 'Trades will build the equity curve as strategies execute.');
        return;
      }
      var labels = hist.map(function (h) { return h.label || ''; });
      var values = hist.map(function (h) { return h.equity; });
      var canvas = document.getElementById('dash-equity-chart');
      if (!canvas) return;
      if (_charts.equity) _charts.equity.destroy();
      var ctx = canvas.getContext('2d');
      var gradient = ctx.createLinearGradient(0, 0, 0, 280);
      gradient.addColorStop(0, 'rgba(6,182,212,0.2)');
      gradient.addColorStop(1, 'rgba(6,182,212,0)');
      _charts.equity = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: [{ data: values, borderColor: ChartHelper.accentColor(), backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHitRadius: 10 }] },
        options: ChartHelper.baseLineOpts({ scales: { y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
      });
    }).catch(function (err) { console.error('[DASHBOARD] Equity fetch failed:', err); });
  }

  /* ── Portfolio Stats Grid ─────────────────────────────────── */
  function _fetchPortStats() {
    ApiClient.getPortfolioSummary().then(function (data) {
      var p = data.portfolio || {};
      var el = document.getElementById('dash-port-stats');
      if (!el) return;
      el.innerHTML =
        _metricPill('Trades', p.total_trades || 0) +
        _metricPill('Win Rate', _fmtPct(p.win_rate)) +
        _metricPill('PF', p.profit_factor || 0, (p.profit_factor || 0) >= 1 ? 'text-success' : '') +
        _metricPill('Sharpe', p.sharpe_estimate || 0) +
        _metricPill('Sortino', p.sortino_estimate || 0) +
        _metricPill('Avg Trade', _fmtMoney(p.avg_trade), (p.avg_trade || 0) >= 0 ? 'text-success' : 'text-danger') +
        _metricPill('Avg Winner', _fmtMoney(p.avg_winner), 'text-success') +
        _metricPill('Avg Loser', _fmtMoney(p.avg_loser), 'text-danger') +
        _metricPill('Max DD', _fmtPct(p.max_drawdown_pct), 'text-danger') +
        _metricPill('Best', _fmtMoney(p.best_trade), 'text-success') +
        _metricPill('Worst', _fmtMoney(p.worst_trade), 'text-danger') +
        _metricPill('Open Pos', p.open_positions || 0);
    }).catch(function (err) { console.error('[DASHBOARD] Portfolio stats failed:', err); });
  }

  /* ── Fleet Panel ──────────────────────────────────────────── */
  function _fetchFleet() {
    ApiClient.getFleetWorkers().then(function (data) {
      var workers = data.workers || [];
      var s = data.summary || {};
      var el = document.getElementById('dash-fleet');
      if (!el) return;
      _lastFleetWorkers = workers;

      if (workers.length === 0) {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;"><i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>No workers connected.</div>';
        return;
      }

      var html = '<div class="fleet-summary" style="margin-bottom:10px;">';
      html += _fleetBadge(s.online_workers || 0, 'Online', 'online');
      html += _fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
      html += _fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
      html += '</div>';

      html += '<table class="compact-fleet-table" style="margin-top:8px;"><thead><tr><th>Worker</th><th>State</th><th>Balance</th><th>Heartbeat</th></tr></thead><tbody>';
      workers.slice(0, 6).forEach(function (w) {
        var name = w.worker_name || w.worker_id;
        var state = w.state || 'unknown';
        var bal = w.account_balance > 0 ? ('$' + w.account_balance.toFixed(0)) : '<span style="opacity:.4;">\u2014</span>';
        html += '<tr class="clickable" onclick="DashboardRenderer._openWorker(\'' + w.worker_id + '\')">' +
          '<td class="mono">' + name + '</td>' +
          '<td>' + _statPill(state.toUpperCase(), state) + '</td>' +
          '<td class="mono">' + bal + '</td>' +
          '<td class="mono" style="font-size:10px;">' + _fmtAge(w.heartbeat_age_seconds) + '</td></tr>';
      });
      html += '</tbody></table>';
      html += '<span class="view-fleet-link" onclick="App.navigateTo(\'fleet\')">View Fleet <i class="fa-solid fa-arrow-right"></i></span>';''
      el.innerHTML = html;
    }).catch(function (err) { console.error('[DASHBOARD] Fleet fetch failed:', err); });
  }

  /* ── Pipeline Panel ───────────────────────────────────────── */
  function _fetchPipeline() {
    ApiClient.getFleetWorkers().then(function (data) {
      var workers = data.workers || [];
      var el = document.getElementById('dash-pipeline');
      if (!el) return;
      var totalTicks = 0, totalBars = 0, totalBarsInMem = 0, totalSignals = 0, totalOnBar = 0;
      workers.forEach(function (w) {
        totalTicks += (w.total_ticks || 0);
        totalBars += (w.total_bars || 0);
        totalBarsInMem += (w.current_bars_in_memory || 0);
        totalSignals += (w.signal_count || 0);
        totalOnBar += (w.on_bar_calls || 0);
      });
      if (workers.length === 0) {
        el.innerHTML = _emptyState('fa-diagram-project', 'No Pipeline Data', 'Connect worker agents to see live flow.');
        return;
      }
      var barsMemNote = totalBarsInMem > 0 ? '<div style="font-size:10px;color:var(--text-muted);margin-top:2px;">' + totalBarsInMem + ' in mem</div>' : '';
      el.innerHTML = '<div class="pipeline-flow">' +
        '<div class="pipeline-node"><span class="pipeline-val accent">' + _fmtNum(totalTicks) + '</span><span class="pipeline-lbl">Ticks</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val warning">' + _fmtNum(totalBars) + '</span><span class="pipeline-lbl">Bars Gen\u2019d</span>' + barsMemNote + '</div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val success">' + _fmtNum(totalOnBar) + '</span><span class="pipeline-lbl">on_bar()</span></div>' +
        '<div class="pipeline-arrow"><i class="fa-solid fa-arrow-right"></i></div>' +
        '<div class="pipeline-node"><span class="pipeline-val danger">' + _fmtNum(totalSignals) + '</span><span class="pipeline-lbl">Signals</span></div></div>';
    }).catch(function (err) { console.error('[DASHBOARD] Pipeline fetch failed:', err); });
  }

  /* ── Strategies Panel ─────────────────────────────────────── */
  function _fetchStrategies() {
    Promise.all([
      ApiClient.getStrategies().catch(function () { return { strategies: [] }; }),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; })
    ]).then(function (r) {
      var strats = r[0].strategies || [];
      var deps = r[1].deployments || [];
      var el = document.getElementById('dash-strategies');
      if (!el) return;
      if (strats.length === 0) {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No strategies registered.</div>';
        return;
      }
      var html = '<div style="display:flex;flex-direction:column;gap:8px;">';
      strats.forEach(function (s) {
        var active = deps.filter(function (d) { return d.strategy_id === s.strategy_id && d.state === 'running'; }).length;
        var total = deps.filter(function (d) { return d.strategy_id === s.strategy_id; }).length;
        html += '<div class="dash-strat-row">' +
          '<div class="dash-strat-info">' +
            '<span class="mono" style="color:var(--accent);font-weight:600;">' + (s.name || s.strategy_id) + '</span>' +
            '<span class="dash-strat-meta">v' + (s.version || '?') + '</span>' +
          '</div>' +
          '<div class="dash-strat-badges">' +
            (active > 0 ? _statPill(active + ' RUNNING', 'online') : '') +
            '<span style="font-size:10px;color:var(--text-muted);">' + total + ' deploy' + (total !== 1 ? 's' : '') + '</span>' +
          '</div></div>';
      });
      html += '</div>';
      el.innerHTML = html;
    });
  }

  /* ── Recent Trades Panel ──────────────────────────────────── */
  function _fetchTrades() {
    ApiClient.getPortfolioTrades({ limit: 8 }).then(function (data) {
      var trades = data.trades || [];
      var el = document.getElementById('dash-trades');
      if (!el) return;
      if (trades.length === 0) {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No trades yet.</div>';
        return;
      }
      var html = '<table class="compact-fleet-table"><thead><tr><th>Symbol</th><th>Dir</th><th>P&L</th><th>Reason</th></tr></thead><tbody>';
      trades.slice(0, 8).forEach(function (t) {
        var pnlClass = t.profit >= 0 ? 'text-success' : 'text-danger';
        html += '<tr>' +
          '<td class="mono">' + t.symbol + '</td>' +
          '<td>' + _statPill(t.direction.toUpperCase(), t.direction === 'long' ? 'online' : 'error') + '</td>' +
          '<td class="mono ' + pnlClass + '">' + _fmtMoney(t.profit) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.exit_reason || '\u2014') + '</td></tr>';
      });
      html += '</tbody></table>';
      html += '<span class="view-fleet-link" onclick="App.navigateTo(\'portfolio\')">View Portfolio <i class="fa-solid fa-arrow-right"></i></span>';
      el.innerHTML = html;
    }).catch(function (err) { console.error('[DASHBOARD] Trades fetch failed:', err); });
  }

  /* ── Recent Deployments Panel ─────────────────────────────── */
  function _fetchDeploys() {
    ApiClient.getDeployments().then(function (data) {
      var deps = data.deployments || [];
      var el = document.getElementById('dash-deploys');
      if (!el) return;
      if (deps.length === 0) {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">No deployments yet.</div>';
        return;
      }
      /* API returns DESC by created_at — take newest 6 directly */
      deps = deps.slice(0, 6);
      var html = '<table class="compact-fleet-table"><thead><tr><th>Strategy</th><th>Worker</th><th>Symbol</th><th>State</th><th>Created</th></tr></thead><tbody>';
      deps.forEach(function (d) {
        var state = d.state || 'unknown';
        var sc = state === 'running' ? 'online' : state === 'failed' ? 'error' : state === 'stopped' ? 'offline' : 'stale';
        var created = d.created_at ? d.created_at.replace('T', ' ').substring(0, 16) : '\u2014';
        var stratLabel = d.strategy_name || d.strategy_id || '\u2014';
        if (d.strategy_version) stratLabel += ' v' + d.strategy_version;
        html += '<tr>' +
          '<td class="mono">' + stratLabel + '</td>' +
          '<td class="mono">' + (d.worker_id || '\u2014') + '</td>' +
          '<td class="mono">' + (d.symbol || '\u2014') + '</td>' +
          '<td>' + _statPill(state.toUpperCase().replace(/_/g, ' '), sc) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + created + '</td></tr>';
      });
      html += '</tbody></table>';
      el.innerHTML = html;
    }).catch(function (err) {
      console.error('[DASHBOARD] Failed to load deployments:', err);
      var el = document.getElementById('dash-deploys');
      if (el) el.innerHTML = '<div style="padding:16px 0;color:var(--danger);font-size:12px;"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px;"></i>Failed to load deployments. Check console.</div>';
    });
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastFleetWorkers.length; i++) {
      if (_lastFleetWorkers[i].worker_id === workerId) {
        App.navigateToWorkerDetail(_lastFleetWorkers[i]);
        return;
      }
    }
  }

  function destroy() {
    _intervals.forEach(clearInterval);
    _intervals = [];
    _destroyCharts();
  }

  return { render: render, destroy: destroy, _openWorker: _openWorker };
})();


/* ================================================================
   7. FLEET RENDERER
   ================================================================ */
var FleetRenderer = (function () {
  'use strict';
  var _refreshInterval = null;
  var _lastWorkers = [];

  function renderNodeCard(w) {
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;
    var pnlVal = w.floating_pnl !== null && w.floating_pnl !== undefined ? _fmtMoney(w.floating_pnl) : _nullVal(null);
    var pnlStyle = w.floating_pnl !== null && w.floating_pnl !== undefined ? (w.floating_pnl >= 0 ? 'color:var(--success)' : 'color:var(--danger)') : '';
    var bal = w.account_balance > 0 ? ('$' + w.account_balance.toFixed(2)) : '\u2014';

    function _row(l, v) { return '<div class="node-info-row"><span class="node-info-label">' + l + '</span><span class="node-info-value">' + v + '</span></div>'; }

    return '<div class="node-card clickable" onclick="FleetRenderer._openWorker(\'' + w.worker_id + '\')">' +
      '<div class="node-card-top ' + state + '"></div>' +
      '<div class="node-card-header">' +
        '<div class="node-name-group"><span class="node-status-dot ' + state + '"></span><span class="node-name">' + name + '</span></div>' +
        '<span class="node-status-badge ' + state + '">' + (state.charAt(0).toUpperCase() + state.slice(1)) + '</span>' +
      '</div>' +
      '<div class="node-card-body">' +
        _row('Worker ID', '<span class="mono">' + w.worker_id + '</span>') +
        _row('Host', _nullVal(w.host)) +
        _row('MT5', w.mt5_state === 'connected' ? '<span style="color:var(--success);">Connected</span>' : _nullVal(w.mt5_state, 'Not Connected')) +
        _row('Broker', _nullVal(w.broker)) +
        _row('Balance', bal) +
        _row('Positions', '<span style="color:var(--accent);">' + (w.open_positions_count || 0) + '</span>') +
        _row('Float PnL', '<span style="' + pnlStyle + '">' + pnlVal + '</span>') +
        _row('Pipeline', '<span class="mono" style="font-size:10px;">' + (w.total_ticks || 0) + ' ticks / ' + (w.total_bars || 0) + ' bars (' + (w.current_bars_in_memory || 0) + ' mem) / ' + (w.signal_count || 0) + ' sig</span>') +
        _row('Heartbeat', _fmtAge(w.heartbeat_age_seconds)) +
        '<div class="node-card-action"><i class="fa-solid fa-arrow-right"></i> View / Deploy</div>' +
      '</div></div>';
  }

  function _renderContent(data) {
    var el = document.getElementById('fleet-content');
    if (!el) return;
    var workers = data.workers || [];
    var s = data.summary || {};
    _lastWorkers = workers;

    if (workers.length === 0) {
      el.innerHTML = _emptyState('fa-server', 'No Workers Connected', 'Start a worker agent to see fleet data.');
      return;
    }

    var html = '<div class="fleet-summary">';
    html += _fleetBadge(s.total_workers || 0, 'Total', 'total');
    html += _fleetBadge(s.online_workers || 0, 'Online', 'online');
    html += _fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
    html += _fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
    html += _fleetBadge(s.error_workers || 0, 'Error', 'error');
    html += '</div>';

    html += '<div class="fleet-grid">';
    workers.forEach(function (w) { html += renderNodeCard(w); });
    html += '</div>';
    el.innerHTML = html;
  }

  function _fetch() {
    ApiClient.getFleetWorkers().then(_renderContent).catch(function () {
      var el = document.getElementById('fleet-content');
      if (el) el.innerHTML = '<div class="error-state"><i class="fa-solid fa-triangle-exclamation"></i><h3>Failed to Load Fleet</h3><button class="retry-btn" onclick="FleetRenderer._retry()">Retry</button></div>';
    });
  }

  function _openWorker(wid) {
    for (var i = 0; i < _lastWorkers.length; i++) {
      if (_lastWorkers[i].worker_id === wid) { App.navigateToWorkerDetail(_lastWorkers[i]); return; }
    }
  }

  function render() {
    document.getElementById('main-content').innerHTML =
      '<div class="fleet-page">' +
        '<div class="fleet-page-header" id="fleet-page-header">' +
          '<span class="fleet-page-title"><i class="fa-solid fa-server" style="color:var(--accent);margin-right:8px;"></i>Fleet Management</span>' +
          '<div class="fleet-page-meta"><div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Auto-refresh</div></div>' +
        '</div>' +
        '<div id="fleet-content">' + _spinner() + '</div>' +
      '</div>';
    _fetch();
    _refreshInterval = setInterval(_fetch, 5000);
  }

  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }

  return { render: render, destroy: destroy, _retry: _fetch, _openWorker: _openWorker };
})();


/* ================================================================
   8. STRATEGIES RENDERER
   ================================================================ */
var StrategiesRenderer = (function () {
  'use strict';
  var _refreshInterval = null;

  function render() {
    var html = '<div class="fleet-page">';
    html += '<div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-crosshairs" style="color:var(--accent);margin-right:8px;"></i>Strategy Registry</span>';
    html += '<div class="fleet-page-meta"><button class="wd-refresh-btn" id="strat-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';

    html += '<div class="wd-panel"><div class="wd-panel-header">Upload Strategy<span class="panel-badge">REGISTER</span></div><div class="wd-panel-body">';
    html += '<div class="wd-file-upload" id="strat-upload-area"><input type="file" id="strat-file-input" accept=".py" style="display:none" />';
    html += '<i class="fa-solid fa-file-code"></i><h4>Upload Strategy File</h4><p>.py files extending BaseStrategy</p><div id="strat-upload-status"></div></div></div></div>';

    html += '<div id="strat-list-content">' + _spinner() + '</div>';
    html += '</div>';
    document.getElementById('main-content').innerHTML = html;

    document.getElementById('strat-refresh').addEventListener('click', _fetch);
    var area = document.getElementById('strat-upload-area');
    var input = document.getElementById('strat-file-input');
    area.addEventListener('click', function () { input.click(); });
    input.addEventListener('change', function () {
      if (!input.files || !input.files[0]) return;
      var f = input.files[0];
      if (!f.name.endsWith('.py')) { ToastManager.show('Only .py files.', 'error'); return; }
      _upload(f);
    });

    _fetch();
    _refreshInterval = setInterval(_fetch, 10000);
  }

  function _upload(file) {
    var el = document.getElementById('strat-upload-status');
    el.innerHTML = '<div style="color:var(--accent);"><i class="fa-solid fa-spinner fa-spin"></i> Uploading\u2026</div>';
    ApiClient.uploadStrategy(file).then(function (d) {
      el.innerHTML = '<div style="color:var(--success);"><i class="fa-solid fa-circle-check"></i> Registered: ' + (d.strategy_name || d.strategy_id) + '</div>';
      ToastManager.show('Strategy registered.', 'success');
      _fetch();
    }).catch(function (e) {
      el.innerHTML = '<div style="color:var(--danger);"><i class="fa-solid fa-circle-xmark"></i> ' + e.message + '</div>';
    });
  }

  function _fetch() {
    var el = document.getElementById('strat-list-content');
    if (!el) return;
    ApiClient.getStrategies().then(function (data) {
      var list = data.strategies || [];
      if (list.length === 0) {
        el.innerHTML = _emptyState('fa-crosshairs', 'No Strategies', 'Upload a .py strategy file to get started.');
        return;
      }
      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>ID</th><th>Name</th><th>Version</th><th>Hash</th><th>Uploaded</th></tr></thead><tbody>';
      list.forEach(function (s) {
        var up = s.uploaded_at ? s.uploaded_at.replace('T', ' ').substring(0, 19) : '\u2014';
        html += '<tr><td class="mono">' + s.strategy_id + '</td><td>' + (s.name || s.strategy_id) + '</td><td class="mono">' + (s.version || '\u2014') + '</td><td class="mono" style="font-size:10px;">' + (s.file_hash || '\u2014') + '</td><td class="mono">' + up + '</td></tr>';
      });
      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function (e) {
      el.innerHTML = '<div style="padding:20px;color:var(--danger);font-size:12px;">Failed: ' + e.message + '</div>';
    });
  }

  function destroy() { if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; } }
  return { render: render, destroy: destroy };
})();


/* ================================================================
   9. PORTFOLIO RENDERER — PROFESSIONAL ANALYTICS MODULE
      Sub-tabs: Overview | Equity & Risk | Strategies | VMs | Trades
   ================================================================ */
var PortfolioRenderer = (function () {
  'use strict';
  var _charts = {};
  var _activeTab = 'overview';
  var _filters = { strategy_id: '', worker_id: '', symbol: '' };
  var _allTrades = [];

  function _destroyCharts() {
    for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } }
  }

  function _getFilterParams() {
    var p = {};
    if (_filters.strategy_id) p.strategy_id = _filters.strategy_id;
    if (_filters.worker_id) p.worker_id = _filters.worker_id;
    if (_filters.symbol) p.symbol = _filters.symbol;
    return p;
  }

  /* ── Main Render ──────────────────────────────────────────── */
  function render() {
    var html = '<div class="fleet-page" id="portfolio-page">';

    /* Header */
    html += '<div class="fleet-page-header">';
    html += '<span class="fleet-page-title"><i class="fa-solid fa-chart-line" style="color:var(--accent);margin-right:8px;"></i>Portfolio Analytics</span>';
    html += '<div class="fleet-page-meta">';
    html += '<button class="wd-btn wd-btn-ghost" id="port-csv-export" style="font-size:11px;"><i class="fa-solid fa-download"></i> CSV</button>';
    html += '<button class="wd-refresh-btn" id="port-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button>';
    html += '</div></div>';

    /* Filters */
    html += '<div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">';
    html += '<div class="wd-form-group" style="margin:0;"><select class="wd-form-select port-filter" id="port-f-strategy" style="min-width:150px;"><option value="">All Strategies</option></select></div>';
    html += '<div class="wd-form-group" style="margin:0;"><select class="wd-form-select port-filter" id="port-f-worker" style="min-width:150px;"><option value="">All VMs / Workers</option></select></div>';
    html += '<div class="wd-form-group" style="margin:0;"><select class="wd-form-select port-filter" id="port-f-symbol" style="min-width:130px;"><option value="">All Symbols</option></select></div>';
    html += '</div>';

    /* Tabs */
    html += '<div class="port-tabs" id="port-tabs">';
    var tabDefs = [
      { key: 'overview', label: 'Overview' },
      { key: 'equity', label: 'Equity & Risk' },
      { key: 'strategies', label: 'Strategies' },
      { key: 'fleet', label: 'VMs' },
      { key: 'trades', label: 'Trades' }
    ];
    tabDefs.forEach(function (t) {
      html += '<button class="port-tab' + (t.key === _activeTab ? ' active' : '') + '" data-tab="' + t.key + '">' + t.label + '</button>';
    });
    html += '</div>';

    /* Content area */
    html += '<div id="port-content">' + _spinner() + '</div>';
    html += '</div>';

    document.getElementById('main-content').innerHTML = html;

    /* Attach events */
    document.getElementById('port-refresh').addEventListener('click', _loadAll);
    document.getElementById('port-csv-export').addEventListener('click', _exportCSV);

    document.querySelectorAll('#port-tabs .port-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        _activeTab = btn.getAttribute('data-tab');
        document.querySelectorAll('#port-tabs .port-tab').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        _renderActiveTab();
      });
    });

    document.querySelectorAll('.port-filter').forEach(function (sel) {
      sel.addEventListener('change', function () {
        _filters.strategy_id = document.getElementById('port-f-strategy').value;
        _filters.worker_id = document.getElementById('port-f-worker').value;
        _filters.symbol = document.getElementById('port-f-symbol').value;
        _loadAll();
      });
    });

    _loadFilters();
    _loadAll();
  }

  function _loadFilters() {
    ApiClient.getPortfolioTrades({ limit: 1000 }).then(function (data) {
      var trades = data.trades || [];
      var strats = {}, workers = {}, syms = {};
      trades.forEach(function (t) {
        if (t.strategy_id) strats[t.strategy_id] = 1;
        if (t.worker_id) workers[t.worker_id] = 1;
        if (t.symbol) syms[t.symbol] = 1;
      });
      function _fill(id, obj, defaultLabel) {
        var el = document.getElementById(id);
        if (!el) return;
        var val = el.value;
        el.innerHTML = '<option value="">' + defaultLabel + '</option>';
        Object.keys(obj).sort().forEach(function (k) {
          el.innerHTML += '<option value="' + k + '"' + (k === val ? ' selected' : '') + '>' + k + '</option>';
        });
      }
      _fill('port-f-strategy', strats, 'All Strategies');
      _fill('port-f-worker', workers, 'All VMs / Workers');
      _fill('port-f-symbol', syms, 'All Symbols');
    }).catch(function () {});
  }

  function _loadAll() { _destroyCharts(); _renderActiveTab(); }

  function _renderActiveTab() {
    var el = document.getElementById('port-content');
    if (!el) return;
    el.innerHTML = _spinner();
    if (_activeTab === 'overview') _tabOverview(el);
    else if (_activeTab === 'equity') _tabEquityRisk(el);
    else if (_activeTab === 'strategies') _tabStrategies(el);
    else if (_activeTab === 'fleet') _tabFleet(el);
    else if (_activeTab === 'trades') _tabTrades(el);
  }

  /* ── OVERVIEW TAB ─────────────────────────────────────────── */
  function _tabOverview(container) {
    Promise.all([
      ApiClient.getPortfolioSummary(_getFilterParams()).catch(function () { return { portfolio: {} }; }),
      ApiClient.getEquityHistory().catch(function () { return { equity_history: [] }; }),
      ApiClient.getPortfolioPerformance(_getFilterParams()).catch(function () { return { performance: {} }; })
    ]).then(function (results) {
      var p = results[0].portfolio || {};
      var eqHist = results[1].equity_history || [];
      var perf = results[2].performance || {};

      if (p.total_trades === 0 && (perf.by_strategy || []).length === 0) {
        container.innerHTML = _emptyState('fa-chart-line', 'No Portfolio Data', 'Run strategies to generate trade data and analytics.');
        return;
      }

      var html = '';

      /* Key metrics — text style row */
      html += '<div style="display:flex;flex-wrap:wrap;gap:20px;padding:16px 0;border-bottom:1px solid var(--border);margin-bottom:20px;">';
      html += _metricItem('Net P&L', _fmtMoney(p.net_pnl), (p.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger');
      html += _metricItem('Gross Profit', _fmtMoney(p.gross_profit), 'text-success');
      html += _metricItem('Gross Loss', _fmtMoney(p.gross_loss), 'text-danger');
      html += _metricItem('Profit Factor', String(p.profit_factor || 0), (p.profit_factor || 0) >= 1 ? 'text-success' : '');
      html += _metricItem('Expectancy', _fmtMoney(p.expectancy), (p.expectancy || 0) >= 0 ? 'text-success' : 'text-danger');
      html += _metricItem('Max DD', _fmtPct(p.max_drawdown_pct), 'text-danger');
      html += _metricItem('Sharpe', String(p.sharpe_estimate || 0));
      html += _metricItem('Sortino', String(p.sortino_estimate || 0));
      html += _metricItem('Recovery', String(p.recovery_factor || 0));
      html += _metricItem('Trades', String(p.total_trades || 0));
      html += _metricItem('Wins/Losses', (p.wins || 0) + '/' + (p.losses || 0));
      html += _metricItem('Trades/Day', String(p.trades_per_day || 0));
      html += _metricItem('Current DD', _fmtPct(p.current_drawdown_pct), (p.current_drawdown_pct || 0) > 5 ? 'text-danger' : '');
      html += _metricItem('Peak Equity', p.peak_equity ? ('$' + _fmtNum(p.peak_equity)) : '\u2014');
      html += '</div>';

      /* Extended metrics row */
      html += '<div style="display:flex;flex-wrap:wrap;gap:20px;padding:12px 0;border-bottom:1px solid var(--border);margin-bottom:20px;">';
      html += _metricItem('Avg Trade', _fmtMoney(p.avg_trade), (p.avg_trade || 0) >= 0 ? 'text-success' : 'text-danger');
      html += _metricItem('Avg Winner', _fmtMoney(p.avg_winner), 'text-success');
      html += _metricItem('Avg Loser', _fmtMoney(p.avg_loser), 'text-danger');
      html += _metricItem('Best Trade', _fmtMoney(p.best_trade), 'text-success');
      html += _metricItem('Worst Trade', _fmtMoney(p.worst_trade), 'text-danger');
      html += _metricItem('Max DD ($)', _fmtMoney(-Math.abs(p.max_drawdown_usd || 0)), 'text-danger');
      html += _metricItem('Avg Bars', String(p.avg_bars_held || 0));
      html += _metricItem('Consec Wins', String(p.max_consec_wins || 0), 'text-success');
      html += _metricItem('Consec Losses', String(p.max_consec_losses || 0), 'text-danger');
      html += _metricItem('Floating', _fmtMoney(p.floating_pnl), (p.floating_pnl || 0) >= 0 ? 'text-success' : 'text-danger');
      html += _metricItem('Open Pos', String(p.open_positions || 0));
      html += _metricItem('Active Workers', String(p.active_workers || 0));
      html += '</div>';

      /* Hero equity chart */
      html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">Equity Curve</div>';
      html += '<div class="chart-container"><div class="chart-wrapper" id="ov-equity-wrap"><canvas id="ov-equity-chart"></canvas></div></div></div>';

      /* Best / Worst day cards */
      if (p.best_day || p.worst_day) {
        html += '<div style="display:flex;gap:12px;margin-bottom:20px;">';
        if (p.best_day) {
          html += '<div style="flex:1;padding:14px;background:var(--bg-secondary);border-radius:8px;border-left:3px solid var(--success);">' +
            '<div style="font-size:10px;color:var(--text-muted);">Best Day</div>' +
            '<div class="mono text-success" style="font-size:16px;font-weight:700;">' + _fmtMoney(p.best_day.pnl) + '</div>' +
            '<div class="mono" style="font-size:10px;color:var(--text-muted);">' + p.best_day.date + '</div></div>';
        }
        if (p.worst_day) {
          html += '<div style="flex:1;padding:14px;background:var(--bg-secondary);border-radius:8px;border-left:3px solid var(--danger);">' +
            '<div style="font-size:10px;color:var(--text-muted);">Worst Day</div>' +
            '<div class="mono text-danger" style="font-size:16px;font-weight:700;">' + _fmtMoney(p.worst_day.pnl) + '</div>' +
            '<div class="mono" style="font-size:10px;color:var(--text-muted);">' + p.worst_day.date + '</div></div>';
        }
        html += '</div>';
      }

      /* Composition tables */
      var sections = [
        { key: 'by_strategy', idField: 'strategy_id', title: 'Composition — Strategy' },
        { key: 'by_worker', idField: 'worker_id', title: 'Composition — VM' },
        { key: 'by_symbol', idField: 'symbol', title: 'Composition — Symbol' }
      ];

      sections.forEach(function (sec) {
        var rows = perf[sec.key] || [];
        if (rows.length === 0) return;
        rows.sort(function (a, b) { return b.pnl - a.pnl; });
        html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">' + sec.title + '</div>';
        html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>' + sec.idField.replace('_', ' ').toUpperCase() + '</th><th>Trades</th><th>P&L</th><th>Win Rate</th><th>PF</th><th>Avg Bars</th></tr></thead><tbody>';
        rows.forEach(function (r) {
          var pc = r.pnl >= 0 ? 'text-success' : 'text-danger';
          html += '<tr><td class="mono" style="font-weight:600;color:var(--accent);">' + r[sec.idField] + '</td><td class="mono">' + r.trades + '</td><td class="mono ' + pc + '">' + _fmtMoney(r.pnl) + '</td><td class="mono">' + _fmtPct(r.win_rate) + '</td><td class="mono">' + r.profit_factor + '</td><td class="mono">' + r.avg_bars + '</td></tr>';
        });
        html += '</tbody></table></div></div>';
      });

      container.innerHTML = html;

      /* Render equity chart */
      if (eqHist.length > 1 && !(eqHist.length === 1 && eqHist[0].source === 'initial')) {
        var canvas = document.getElementById('ov-equity-chart');
        if (canvas) {
          var ctx = canvas.getContext('2d');
          var gradient = ctx.createLinearGradient(0, 0, 0, 300);
          gradient.addColorStop(0, 'rgba(6,182,212,0.2)');
          gradient.addColorStop(1, 'rgba(6,182,212,0)');
          _charts.ovEquity = new Chart(ctx, {
            type: 'line',
            data: {
              labels: eqHist.map(function (h) { return h.label || ''; }),
              datasets: [{ data: eqHist.map(function (h) { return h.equity; }), borderColor: ChartHelper.accentColor(), backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0 }]
            },
            options: ChartHelper.baseLineOpts({ scales: { y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
          });
        }
      } else {
        var wrap = document.getElementById('ov-equity-wrap');
        if (wrap) wrap.innerHTML = _emptyState('fa-chart-area', 'No Equity Data', 'Trades will build the curve.');
      }
    });
  }

  /* ── EQUITY & RISK TAB ────────────────────────────────────── */
  function _tabEquityRisk(container) {
    Promise.all([
      ApiClient.getEquityHistory().catch(function () { return { equity_history: [] }; }),
      ApiClient.getPortfolioSummary(_getFilterParams()).catch(function () { return { portfolio: {} }; }),
      ApiClient.getPortfolioPerformance(_getFilterParams()).catch(function () { return { performance: {} }; })
    ]).then(function (results) {
      var eqHist = results[0].equity_history || [];
      var p = results[1].portfolio || {};
      var perf = results[2].performance || {};
      var daily = perf.daily || [];
      var monthly = perf.monthly || [];

      if (eqHist.length <= 1 && daily.length === 0) {
        container.innerHTML = _emptyState('fa-chart-area', 'No Data Yet', 'Execute trades to see equity and risk analytics.');
        return;
      }

      var html = '';

      /* Risk metrics */
      html += '<div style="display:flex;flex-wrap:wrap;gap:20px;padding:14px 0;border-bottom:1px solid var(--border);margin-bottom:20px;">';
      html += _metricItem('Max DD ($)', _fmtMoney(-Math.abs(p.max_drawdown_usd || 0)), 'text-danger');
      html += _metricItem('Max DD (%)', _fmtPct(p.max_drawdown_pct), 'text-danger');
      html += _metricItem('Recovery Factor', String(p.recovery_factor || 0));
      html += _metricItem('Sharpe', String(p.sharpe_estimate || 0));
      html += _metricItem('Sortino', String(p.sortino_estimate || 0));
      html += _metricItem('Current DD', _fmtPct(p.current_drawdown_pct), (p.current_drawdown_pct || 0) > 5 ? 'text-danger' : '');
      html += _metricItem('Peak Equity', p.peak_equity ? ('$' + _fmtNum(p.peak_equity)) : '\u2014');
      html += _metricItem('Consec Wins', String(p.max_consec_wins || 0), 'text-success');
      html += _metricItem('Consec Losses', String(p.max_consec_losses || 0), 'text-danger');
      html += _metricItem('Avg Bars Held', String(p.avg_bars_held || 0));
      html += '</div>';

      /* Equity chart */
      html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">Equity Curve</div>';
      html += '<div class="chart-container"><div class="chart-wrapper" id="eq-chart-wrap"><canvas id="eq-chart-canvas"></canvas></div></div></div>';

      /* Drawdown chart */
      html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">Drawdown</div>';
      html += '<div class="chart-container"><div class="chart-wrapper" id="dd-chart-wrap"><canvas id="dd-chart-canvas"></canvas></div></div></div>';

      /* Daily PnL */
      html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">Daily P&L</div>';
      html += '<div class="chart-container"><div class="chart-wrapper" style="height:220px;" id="daily-chart-wrap"><canvas id="daily-chart-canvas"></canvas></div></div></div>';

      /* Monthly returns */
      if (monthly.length > 0) {
        html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">Monthly Returns</div>';
        html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr><th>Month</th><th>P&L</th><th>Cumulative</th><th>Trades</th><th>Win Rate</th></tr></thead><tbody>';
        var cumMo = 0;
        monthly.forEach(function (m) {
          cumMo += m.pnl;
          var bg = m.pnl >= 0 ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)';
          var tc = m.pnl >= 0 ? 'text-success' : 'text-danger';
          html += '<tr style="background:' + bg + ';"><td class="mono">' + m.month + '</td><td class="mono ' + tc + '">' + _fmtMoney(m.pnl) + '</td><td class="mono">' + _fmtMoney(cumMo) + '</td><td class="mono">' + m.trades + '</td><td class="mono">' + _fmtPct(m.win_rate) + '</td></tr>';
        });
        html += '</tbody></table></div></div>';
      }

      container.innerHTML = html;

      /* Render charts */
      if (eqHist.length > 1) {
        var labels = eqHist.map(function (h) { return h.label || ''; });
        var values = eqHist.map(function (h) { return h.equity; });

        /* Equity line */
        var cv1 = document.getElementById('eq-chart-canvas');
        if (cv1) {
          var ctx1 = cv1.getContext('2d');
          var g1 = ctx1.createLinearGradient(0, 0, 0, 280);
          g1.addColorStop(0, 'rgba(6,182,212,0.2)');
          g1.addColorStop(1, 'rgba(6,182,212,0)');
          _charts.eqLine = new Chart(ctx1, {
            type: 'line',
            data: { labels: labels, datasets: [{ data: values, borderColor: ChartHelper.accentColor(), backgroundColor: g1, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0 }] },
            options: ChartHelper.baseLineOpts({ scales: { y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
          });
        }

        /* Drawdown */
        var cv2 = document.getElementById('dd-chart-canvas');
        if (cv2) {
          var peak = 0, dd = [];
          values.forEach(function (v) { if (v > peak) peak = v; dd.push(peak > 0 ? -((peak - v) / peak * 100) : 0); });
          var ctx2 = cv2.getContext('2d');
          var g2 = ctx2.createLinearGradient(0, 0, 0, 280);
          g2.addColorStop(0, 'rgba(239,68,68,0)');
          g2.addColorStop(1, 'rgba(239,68,68,0.25)');
          _charts.ddLine = new Chart(ctx2, {
            type: 'line',
            data: { labels: labels, datasets: [{ data: dd, borderColor: ChartHelper.dangerColor(), backgroundColor: g2, borderWidth: 1.5, fill: true, tension: 0.3, pointRadius: 0 }] },
            options: ChartHelper.baseLineOpts({ scales: { y: { ticks: { callback: function (v) { return v.toFixed(1) + '%'; } } } } })
          });
        }
      }

      /* Daily PnL bars */
      if (daily.length > 0) {
        var cv3 = document.getElementById('daily-chart-canvas');
        if (cv3) {
          var dailyVals = daily.map(function (d) { return d.pnl; });
          var dailyColors = dailyVals.map(function (v) { return v >= 0 ? 'rgba(16,185,129,0.65)' : 'rgba(239,68,68,0.65)'; });
          _charts.dailyBar = new Chart(cv3.getContext('2d'), {
            type: 'bar',
            data: { labels: daily.map(function (d) { return d.date; }), datasets: [{ data: dailyVals, backgroundColor: dailyColors, borderRadius: 2, barPercentage: 0.7 }] },
            options: ChartHelper.baseLineOpts({ scales: { y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
          });
        }
      }
    });
  }

  /* ── STRATEGIES TAB ───────────────────────────────────────── */
  function _tabStrategies(container) {
    Promise.all([
      ApiClient.getPortfolioPerformance(_getFilterParams()).catch(function () { return { performance: {} }; }),
      ApiClient.getPortfolioSummary(_getFilterParams()).catch(function () { return { portfolio: {} }; })
    ]).then(function (results) {
      var byStrategy = (results[0].performance || {}).by_strategy || [];

      if (byStrategy.length === 0) {
        container.innerHTML = _emptyState('fa-crosshairs', 'No Strategy Data', 'Deploy and run strategies to see performance analytics.');
        return;
      }

      byStrategy.sort(function (a, b) { return b.pnl - a.pnl; });

      var html = '<div style="font-weight:600;font-size:13px;margin-bottom:12px;">Strategy Leaderboard</div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      html += '<th>Strategy</th><th>Trades</th><th>Net P&L</th><th>Win Rate</th><th>PF</th><th>Avg Bars</th><th>Wins</th><th>Losses</th>';
      html += '</tr></thead><tbody>';
      byStrategy.forEach(function (s) {
        var pc = s.pnl >= 0 ? 'text-success' : 'text-danger';
        html += '<tr>' +
          '<td class="mono" style="font-weight:600;color:var(--accent);">' + s.strategy_id + '</td>' +
          '<td class="mono">' + s.trades + '</td>' +
          '<td class="mono ' + pc + '">' + _fmtMoney(s.pnl) + '</td>' +
          '<td class="mono">' + _fmtPct(s.win_rate) + '</td>' +
          '<td class="mono">' + s.profit_factor + '</td>' +
          '<td class="mono">' + s.avg_bars + '</td>' +
          '<td class="mono text-success">' + s.wins + '</td>' +
          '<td class="mono text-danger">' + s.losses + '</td>' +
          '</tr>';
      });
      html += '</tbody></table></div>';
      container.innerHTML = html;
    });
  }

  /* ── VM / FLEET TAB ───────────────────────────────────────── */
  function _tabFleet(container) {
    Promise.all([
      ApiClient.getFleetWorkers().catch(function () { return { workers: [] }; }),
      ApiClient.getPortfolioPerformance(_getFilterParams()).catch(function () { return { performance: {} }; })
    ]).then(function (results) {
      var workers = results[0].workers || [];
      var byWorker = (results[1].performance || {}).by_worker || [];

      if (workers.length === 0 && byWorker.length === 0) {
        container.innerHTML = _emptyState('fa-server', 'No VMs Connected', 'Connect worker agents to see VM analytics.');
        return;
      }

      var perfMap = {};
      byWorker.forEach(function (w) { perfMap[w.worker_id] = w; });

      var html = '<div style="font-weight:600;font-size:13px;margin-bottom:14px;">VM Performance</div>';
      html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;">';

      workers.forEach(function (w) {
        var wp = perfMap[w.worker_id] || {};
        var state = w.state || 'unknown';
        var borderColor = (state === 'online' || state === 'running') ? 'var(--success)' : state === 'stale' ? 'var(--warning)' : 'var(--text-muted)';

        html += '<div style="background:var(--bg-secondary);border-radius:10px;padding:16px;border:1px solid var(--border);border-top:3px solid ' + borderColor + ';">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">';
        html += '<span class="mono" style="font-weight:600;font-size:13px;">' + (w.worker_name || w.worker_id) + '</span>';
        html += _statPill(state.toUpperCase(), state === 'online' || state === 'running' ? 'online' : state);
        html += '</div>';

        html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">';
        html += _metricItem('Balance', w.account_balance > 0 ? ('$' + w.account_balance.toFixed(0)) : '\u2014');
        html += _metricItem('Equity', w.account_equity > 0 ? ('$' + w.account_equity.toFixed(0)) : '\u2014');
        html += _metricItem('Float P&L', _fmtMoney(w.floating_pnl), (w.floating_pnl || 0) >= 0 ? 'text-success' : 'text-danger');
        html += _metricItem('Positions', String(w.open_positions_count || 0));
        if (wp.pnl !== undefined) {
          html += _metricItem('Realized P&L', _fmtMoney(wp.pnl), (wp.pnl || 0) >= 0 ? 'text-success' : 'text-danger');
          html += _metricItem('Trades', String(wp.trades || 0));
          html += _metricItem('Win Rate', _fmtPct(wp.win_rate));
          html += _metricItem('PF', String(wp.profit_factor || 0));
        }
        html += '</div></div>';
      });

      html += '</div>';
      container.innerHTML = html;
    });
  }

  /* ── TRADES TAB ───────────────────────────────────────────── */
  function _tabTrades(container) {
    var params = _getFilterParams();
    params.limit = 500;

    ApiClient.getPortfolioTrades(params).then(function (data) {
      var trades = data.trades || [];
      _allTrades = trades;

      if (trades.length === 0) {
        container.innerHTML = _emptyState('fa-list', 'No Trades', 'Execute strategies to see trade history.');
        return;
      }

      var html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">';
      html += '<div style="font-weight:600;font-size:13px;">' + trades.length + ' Trades</div>';
      html += '</div>';

      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      html += '<th>#</th><th>Symbol</th><th>Dir</th><th>Strategy</th><th>Worker</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Commission</th><th>Bars</th><th>Reason</th>';
      html += '</tr></thead><tbody>';

      trades.forEach(function (t) {
        var pnlClass = t.profit >= 0 ? 'text-success' : 'text-danger';
        html += '<tr>' +
          '<td class="mono">' + (t.id || t.trade_id || '') + '</td>' +
          '<td class="mono">' + t.symbol + '</td>' +
          '<td>' + _statPill(t.direction.toUpperCase(), t.direction === 'long' ? 'online' : 'error') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.strategy_id || '\u2014') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.worker_id || '\u2014') + '</td>' +
          '<td class="mono">' + t.entry_price + '</td>' +
          '<td class="mono">' + t.exit_price + '</td>' +
          '<td class="mono ' + pnlClass + '">' + _fmtMoney(t.profit) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + _fmtMoney(t.commission || 0) + '</td>' +
          '<td class="mono">' + (t.bars_held || 0) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.exit_reason || '\u2014') + '</td>' +
          '</tr>';
      });

      html += '</tbody></table></div>';
      container.innerHTML = html;
    }).catch(function (e) {
      container.innerHTML = '<div style="color:var(--danger);font-size:12px;padding:20px;">Error loading trades: ' + e.message + '</div>';
    });
  }

  /* ── CSV Export ────────────────────────────────────────────── */
  function _exportCSV() {
    if (!_allTrades || _allTrades.length === 0) {
      ToastManager.show('No trades to export.', 'info');
      return;
    }
    var cols = ['id', 'symbol', 'direction', 'strategy_id', 'worker_id', 'entry_price', 'exit_price', 'profit', 'commission', 'swap', 'bars_held', 'exit_reason', 'entry_time', 'exit_time'];
    var csv = cols.join(',') + '\n';
    _allTrades.forEach(function (t) {
      csv += cols.map(function (c) { return '"' + (t[c] !== undefined && t[c] !== null ? t[c] : '') + '"'; }).join(',') + '\n';
    });
    var blob = new Blob([csv], { type: 'text/csv' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'jinni_trades_' + new Date().toISOString().slice(0, 10) + '.csv';
    a.click();
    ToastManager.show('Exported ' + _allTrades.length + ' trades.', 'success');
  }

  function destroy() { _destroyCharts(); }
  return { render: render, destroy: destroy };
})();


/* ================================================================
   10. LOGS RENDERER
   ================================================================ */
var LogsRenderer = (function () {
  'use strict';
  var _refreshInterval = null;
  var _autoRefresh = true;

  function render() {
    var html = '<div class="fleet-page" id="logs-page">';
    html += '<div class="fleet-page-header"><span class="fleet-page-title"><i class="fa-solid fa-scroll" style="color:var(--accent);margin-right:8px;"></i>Event Logs</span>';
    html += '<div class="fleet-page-meta"><label class="log-auto-label"><input type="checkbox" id="log-auto-check" checked /> Auto-refresh</label>';
    html += '<button class="wd-refresh-btn" id="log-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button></div></div>';

    html += '<div class="log-filters">';
    html += '<div class="wd-form-group"><label class="wd-form-label">Category</label><select class="wd-form-select log-f" id="log-f-cat"><option value="">All</option><option value="system">SYSTEM</option><option value="worker">WORKER</option><option value="execution">EXECUTION</option><option value="strategy">STRATEGY</option><option value="deployment">DEPLOYMENT</option><option value="command">COMMAND</option></select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Level</label><select class="wd-form-select log-f" id="log-f-level"><option value="">All</option><option value="INFO">INFO</option><option value="WARNING">WARNING</option><option value="ERROR">ERROR</option><option value="DEBUG">DEBUG</option></select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Worker</label><input type="text" class="wd-form-input log-f" id="log-f-worker" placeholder="worker id\u2026" /></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Search</label><input type="text" class="wd-form-input log-f" id="log-f-search" placeholder="keyword\u2026" /></div>';
    html += '</div>';

    html += '<div id="log-content">' + _spinner() + '</div>';
    html += '</div>';
    document.getElementById('main-content').innerHTML = html;

    document.getElementById('log-refresh').addEventListener('click', _fetch);
    document.getElementById('log-auto-check').addEventListener('change', function () { _autoRefresh = this.checked; });
    document.querySelectorAll('.log-f').forEach(function (el) {
      el.addEventListener('change', _fetch);
      el.addEventListener('keyup', function (e) { if (e.key === 'Enter') _fetch(); });
    });

    _fetch();
    _refreshInterval = setInterval(function () { if (_autoRefresh) _fetch(); }, 5000);
  }

  function _fetch() {
    var params = { limit: 300 };
    var cat = document.getElementById('log-f-cat');
    if (cat && cat.value) params.category = cat.value;
    var lvl = document.getElementById('log-f-level');
    if (lvl && lvl.value) params.level = lvl.value;
    var wk = document.getElementById('log-f-worker');
    if (wk && wk.value.trim()) params.worker_id = wk.value.trim();
    var search = document.getElementById('log-f-search');
    if (search && search.value.trim()) params.search = search.value.trim();

    ApiClient.getEvents(params).then(function (data) {
      var events = data.events || [];
      var el = document.getElementById('log-content');
      if (!el) return;

      if (events.length === 0) {
        el.innerHTML = '<div style="padding:24px;color:var(--text-muted);font-size:12px;text-align:center;"><i class="fa-solid fa-circle-info" style="margin-right:6px;"></i>No events found matching filters.</div>';
        return;
      }

      var html = '<div class="log-count">' + (data.count || events.length) + ' events</div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table log-table"><thead><tr><th style="width:150px;">Timestamp</th><th style="width:90px;">Category</th><th style="width:60px;">Level</th><th style="width:100px;">Type</th><th>Message</th><th style="width:80px;">Worker</th></tr></thead><tbody>';

      events.forEach(function (ev, idx) {
        var ts = (ev.timestamp || '').replace('T', ' ').substring(0, 19);
        var evCat = (ev.category || '').toUpperCase();
        var evLvl = ev.level || 'INFO';
        var lvlClass = evLvl === 'ERROR' ? 'text-danger' : evLvl === 'WARNING' ? 'text-warning' : 'text-muted';
        var catClass = evCat === 'EXECUTION' ? 'text-success' : evCat === 'STRATEGY' ? 'text-accent' : evCat === 'WORKER' ? 'text-warning' : '';
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


/* ================================================================
   11. SETTINGS + ADMIN RENDERER
   ================================================================ */
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
    html += '</div><div id="settings-content">' + _spinner() + '</div></div>';
    return html;
  }

  function _renderGeneral() {
    var s = _settings;
    var fields = [
      { key: 'refresh_interval', label: 'Dashboard Refresh Interval', type: 'number', unit: 'seconds', min: 1, max: 60, help: 'How often the UI polls for updates.' },
      { key: 'default_symbol', label: 'Default Symbol', type: 'text', placeholder: 'e.g. XAUUSD', help: 'Pre-filled when creating deployments.' },
      { key: 'default_bar_size', label: 'Default Bar Size', type: 'number', unit: 'points', min: 1, help: 'Default range bar size for new deployments.' },
      { key: 'default_lot_size', label: 'Default Lot Size', type: 'number', step: '0.01', min: 0.01, help: 'Default lot size for new deployments.' },
      { key: 'worker_timeout_seconds', label: 'Worker Offline Timeout', type: 'number', unit: 'seconds', min: 10, help: 'Workers not seen for this long are marked offline.' },
      { key: 'log_verbosity', label: 'Log Verbosity', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR'], help: 'Minimum event level shown in logs.' },
      { key: 'debug_mode', label: 'Debug Mode', type: 'toggle', help: 'Enable verbose logging on workers.' }
    ];

    var html = '<div class="wd-panel"><div class="wd-panel-header">General Settings</div><div class="wd-panel-body"><div class="wd-form-grid">';

    fields.forEach(function (f) {
      var val = s[f.key] || '';
      html += '<div class="wd-form-group"><label class="wd-form-label">' + f.label + (f.unit ? ' (' + f.unit + ')' : '') + '</label>';

      if (f.type === 'toggle') {
        var checked = val === 'true' || val === true ? ' checked' : '';
        html += '<label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" class="settings-input" data-key="' + f.key + '"' + checked + ' /> <span style="font-size:12px;color:var(--text-muted);">' + (checked ? 'Enabled' : 'Disabled') + '</span></label>';
      } else if (f.type === 'select') {
        html += '<select class="wd-form-select settings-input" data-key="' + f.key + '">';
        f.options.forEach(function (o) { html += '<option value="' + o + '"' + (val === o ? ' selected' : '') + '>' + o + '</option>'; });
        html += '</select>';
      } else {
        var attrs = 'type="' + f.type + '" class="wd-form-input settings-input" data-key="' + f.key + '" value="' + val + '"';
        if (f.min !== undefined) attrs += ' min="' + f.min + '"';
        if (f.max !== undefined) attrs += ' max="' + f.max + '"';
        if (f.step) attrs += ' step="' + f.step + '"';
        if (f.placeholder) attrs += ' placeholder="' + f.placeholder + '"';
        html += '<input ' + attrs + ' />';
      }
      if (f.help) html += '<div style="font-size:10px;color:var(--text-muted);margin-top:2px;opacity:0.7;">' + f.help + '</div>';
      html += '</div>';
    });

    html += '</div><div style="margin-top:16px;display:flex;gap:10px;">';
    html += '<button class="wd-btn wd-btn-primary" id="save-settings-btn"><i class="fa-solid fa-floppy-disk"></i> Save Settings</button>';
    html += '<button class="wd-btn wd-btn-ghost" id="reset-settings-btn"><i class="fa-solid fa-rotate-left"></i> Reset to Defaults</button>';
    html += '</div></div></div>';
    return html;
  }

  function _renderAdmin() {
    var html = '';

    /* System Stats */
    html += '<div class="wd-panel"><div class="wd-panel-header" style="display:flex;justify-content:space-between;align-items:center;">System Overview';
    html += '<button class="wd-btn wd-btn-ghost" id="refresh-stats-btn" style="font-size:11px;padding:4px 10px;"><i class="fa-solid fa-arrows-rotate"></i></button></div><div class="wd-panel-body">';
    html += '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">';
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

    /* Emergency Stop */
    html += '<div class="wd-panel" style="border:1px solid var(--warning);"><div class="wd-panel-header" style="color:var(--warning);"><i class="fa-solid fa-circle-stop" style="margin-right:6px;"></i>Emergency Controls</div><div class="wd-panel-body">';
    html += '<p style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">Stop all strategies and close all open positions across all workers at market price.</p>';
    html += '<button class="wd-btn" id="admin-emergency-stop" style="background:rgba(239,68,68,0.15);color:var(--danger);font-weight:600;border:1px solid var(--danger);"><i class="fa-solid fa-circle-stop"></i> EMERGENCY STOP ALL</button>';
    html += '</div></div>';

    /* Strategy Management */
    html += '<div class="wd-panel"><div class="wd-panel-header">Strategy Management <span class="panel-badge">' + _strategies.length + ' STRATEGIES</span></div><div class="wd-panel-body">';
    if (_strategies.length === 0) {
      html += '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No strategies registered.</div>';
    } else {
      _strategies.forEach(function (s) {
        html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;margin-bottom:6px;">' +
          '<div><span class="mono" style="color:var(--accent);font-size:12px;">' + (s.name || s.strategy_id) + '</span>' +
          '<span style="font-size:11px;color:var(--text-muted);margin-left:8px;">v' + (s.version || '?') + '</span></div>' +
          '<button class="wd-btn wd-btn-ghost admin-delete-strategy" data-sid="' + s.strategy_id + '" style="font-size:10.5px;color:var(--danger);padding:4px 10px;"><i class="fa-solid fa-trash"></i> Delete</button></div>';
      });
    }
    html += '</div></div>';

    /* Worker Management */
    html += '<div class="wd-panel"><div class="wd-panel-header">Worker Management <span class="panel-badge">' + _workers.length + ' WORKERS</span></div><div class="wd-panel-body">';
    if (_workers.length === 0) {
      html += '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No workers registered.</div>';
    } else {
      _workers.forEach(function (w) {
        var stateClass = w.state || 'unknown';
        html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;margin-bottom:6px;">' +
          '<div><span class="mono" style="font-size:12px;">' + (w.worker_name || w.worker_id) + '</span>' +
          '<span class="state-pill ' + stateClass + '" style="margin-left:8px;">' + stateClass.toUpperCase() + '</span></div>' +
          '<button class="wd-btn wd-btn-ghost admin-remove-worker" data-wid="' + w.worker_id + '" style="font-size:10.5px;color:var(--danger);padding:4px 10px;"><i class="fa-solid fa-trash"></i> Remove</button></div>';
      });
    }
    html += '<button class="wd-btn wd-btn-ghost" id="remove-stale-btn" style="margin-top:8px;font-size:11px;"><i class="fa-solid fa-broom"></i> Remove All Stale Workers</button>';
    html += '</div></div>';

    /* Portfolio Management */
    html += '<div class="wd-panel"><div class="wd-panel-header">Portfolio Management</div><div class="wd-panel-body">';
    html += '<div style="display:flex;flex-wrap:wrap;gap:10px;">';
    html += '<button class="wd-btn wd-btn-ghost" id="admin-clear-trades"><i class="fa-solid fa-eraser"></i> Delete All Trades (' + (_stats.trades_count || 0) + ')</button>';
    html += '<button class="wd-btn wd-btn-ghost" id="admin-reset-portfolio"><i class="fa-solid fa-rotate-left"></i> Reset Portfolio (Trades + Equity)</button>';
    html += '</div></div></div>';

    /* Log Management */
    html += '<div class="wd-panel"><div class="wd-panel-header">Log Management</div><div class="wd-panel-body">';
    html += '<button class="wd-btn wd-btn-ghost" id="admin-clear-events"><i class="fa-solid fa-eraser"></i> Clear All Events (' + (_stats.events_count || 0) + ')</button>';
    html += '</div></div>';

    /* Danger Zone */
    html += '<div class="wd-panel" style="border:1px solid var(--danger);">';
    html += '<div class="wd-panel-header" style="color:var(--danger);"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px;"></i>Danger Zone</div><div class="wd-panel-body">';
    html += '<p style="font-size:12px;color:var(--text-muted);margin-bottom:12px;">Full system reset deletes ALL data: strategies, trades, events, deployments, equity history, workers. Only settings are preserved.</p>';
    html += '<button class="wd-btn" id="admin-full-reset" style="background:rgba(239,68,68,0.15);color:var(--danger);font-weight:600;border:1px solid var(--danger);"><i class="fa-solid fa-skull-crossbones"></i> Full System Reset (Factory Reset)</button>';
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
          if (input.type === 'checkbox') updated[key] = input.checked ? 'true' : 'false';
          else updated[key] = input.value;
        });
        ApiClient.saveSettings(updated).then(function (data) {
          _settings = data.settings || {};
          ToastManager.show('Settings saved and applied.', 'success');
        }).catch(function () { ToastManager.show('Failed to save settings.', 'error'); });
      });
    }
    var resetBtn = document.getElementById('reset-settings-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        var defaults = { refresh_interval: '5', default_symbol: 'XAUUSD', default_bar_size: '100', default_lot_size: '0.01', worker_timeout_seconds: '90', log_verbosity: 'INFO', debug_mode: 'true' };
        ApiClient.saveSettings(defaults).then(function (data) {
          _settings = data.settings || {};
          _renderTab();
          ToastManager.show('Settings reset to defaults.', 'info');
        }).catch(function () { ToastManager.show('Failed.', 'error'); });
      });
    }
  }

  function _attachAdminEvents() {
    var refreshBtn = document.getElementById('refresh-stats-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', _loadData);

    /* Emergency Stop */
    var esBtn = document.getElementById('admin-emergency-stop');
    if (esBtn) {
      esBtn.addEventListener('click', function () {
        ModalManager.show({
          title: '\u26A0 EMERGENCY STOP ALL', type: 'danger',
          bodyHtml: '<p style="font-weight:600;color:var(--danger);">This will immediately:</p><ul style="font-size:12px;color:var(--text-muted);margin:8px 0;"><li>Stop all running strategies</li><li>Close ALL open positions at market price</li><li>Set all deployments to STOPPED</li></ul><p style="font-size:11px;color:var(--danger);margin-top:8px;">This cannot be undone.</p>',
          confirmText: 'STOP EVERYTHING',
          onConfirm: function () {
            ApiClient.emergencyStopAll().then(function (r) {
              ToastManager.show('Emergency stop: ' + (r.deployments_stopped || 0) + ' stopped, ' + (r.commands_sent || 0) + ' commands sent.', 'warning', 8000);
              _loadData();
            }).catch(function (e) { ToastManager.show('Failed: ' + e.message, 'error'); });
          }
        });
      });
    }

    /* Delete Strategy */
    document.querySelectorAll('.admin-delete-strategy').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var sid = btn.getAttribute('data-sid');
        ModalManager.show({
          title: 'Delete Strategy', type: 'danger',
          bodyHtml: '<p>Permanently delete strategy <strong>' + sid + '</strong>?</p><p style="font-size:11px;color:var(--text-muted);margin-top:8px;">Removes the strategy file, all deployments, and all associated trades.</p>',
          confirmText: 'Delete',
          onConfirm: function () {
            ApiClient.adminDeleteStrategy(sid).then(function () { ToastManager.show('Strategy ' + sid + ' deleted.', 'success'); _loadData(); }).catch(function () { ToastManager.show('Delete failed.', 'error'); });
          }
        });
      });
    });

    /* Remove Worker */
    document.querySelectorAll('.admin-remove-worker').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var wid = btn.getAttribute('data-wid');
        ModalManager.show({
          title: 'Remove Worker', type: 'danger',
          bodyHtml: '<p>Remove worker <strong>' + wid + '</strong>?</p>',
          confirmText: 'Remove',
          onConfirm: function () {
            ApiClient.adminRemoveWorker(wid).then(function () { ToastManager.show('Worker removed.', 'success'); _loadData(); }).catch(function () { ToastManager.show('Failed.', 'error'); });
          }
        });
      });
    });

    /* Remove Stale Workers */
    var staleBtn = document.getElementById('remove-stale-btn');
    if (staleBtn) {
      staleBtn.addEventListener('click', function () {
        ModalManager.show({
          title: 'Remove Stale Workers',
          bodyHtml: '<p>Remove workers that haven\'t sent a heartbeat in over 5 minutes?</p>',
          confirmText: 'Remove Stale',
          onConfirm: function () {
            ApiClient.adminRemoveStaleWorkers().then(function (d) { ToastManager.show((d.removed || 0) + ' stale workers removed.', 'success'); _loadData(); }).catch(function () { ToastManager.show('Failed.', 'error'); });
          }
        });
      });
    }

    /* Clear Trades */
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
            }).catch(function () { ToastManager.show('Failed to delete trades.', 'error'); });
          }
        });
      });
    }

    /* Reset Portfolio */
    var resetPortBtn = document.getElementById('admin-reset-portfolio');
    if (resetPortBtn) {
      resetPortBtn.addEventListener('click', function () {
        ModalManager.show({
          title: 'Reset Portfolio', type: 'danger',
          bodyHtml: '<p>Delete all trades AND equity history? This cannot be undone.</p>',
          confirmText: 'Reset Portfolio',
          onConfirm: function () {
            ApiClient.adminResetPortfolio().then(function () {
              ToastManager.show('Portfolio reset complete.', 'success');
              _loadData();
            }).catch(function () { ToastManager.show('Failed to reset portfolio.', 'error'); });
          }
        });
      });
    }

    /* Clear Events */
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
            }).catch(function () { ToastManager.show('Failed to clear events.', 'error'); });
          }
        });
      });
    }

    /* Full System Reset */
    var fullResetBtn = document.getElementById('admin-full-reset');
    if (fullResetBtn) {
      fullResetBtn.addEventListener('click', function () {
        ModalManager.show({
          title: '\u26A0\uFE0F FULL SYSTEM RESET (FACTORY RESET)', type: 'danger',
          bodyHtml: '<p>This will delete <strong>EVERYTHING</strong>:</p>' +
            '<ul style="font-size:12px;color:var(--text-muted);margin:8px 0;">' +
            '<li>All strategies and strategy files</li>' +
            '<li>All deployments</li>' +
            '<li>All trades and equity history</li>' +
            '<li>All worker registrations</li>' +
            '<li>All events/logs</li></ul>' +
            '<p style="color:var(--danger);font-weight:600;margin-top:8px;">Only settings are preserved. This is completely irreversible.</p>',
          confirmText: 'RESET EVERYTHING',
          onConfirm: function () {
            ApiClient.adminFullReset().then(function () {
              ToastManager.show('Full system reset complete. All data cleared.', 'warning', 8000);
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
      _workers = (results[3] && results[3].workers) || [];
      _renderTab();
    }).catch(function () {
      var el = document.getElementById('settings-content');
      if (el) el.innerHTML = _emptyState('fa-circle-exclamation', 'Failed to Load', 'Could not fetch settings data. Try refreshing.');
    });
  }

  function render() {
    document.getElementById('main-content').innerHTML = _buildPage();

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


/* ================================================================
   12. APP — NAVIGATION + INITIALIZATION
   ================================================================ */
var App = (function () {
  'use strict';
  var currentPage = 'dashboard';
  var _selectedWorker = null;

  function init() {
    ThemeManager.init();
    setupNavigation();
    startClock();
    navigateTo('dashboard');
  }

  function setupNavigation() {
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        navigateTo(item.getAttribute('data-page'));
      });
    });
  }

  function navigateTo(page) {
    /* Destroy current page */
    if (currentPage === 'dashboard') DashboardRenderer.destroy();
    if (currentPage === 'fleet') FleetRenderer.destroy();
    if (currentPage === 'workerDetail' && typeof WorkerDetailRenderer !== 'undefined') WorkerDetailRenderer.destroy();
    if (currentPage === 'strategies') StrategiesRenderer.destroy();
    if (currentPage === 'portfolio') PortfolioRenderer.destroy();
    if (currentPage === 'logs') LogsRenderer.destroy();
    if (currentPage === 'settings') SettingsRenderer.destroy();

    currentPage = page;

    /* Highlight active nav item */
    var navPage = page === 'workerDetail' ? 'fleet' : page;
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.classList.toggle('active', item.getAttribute('data-page') === navPage);
    });

    /* Update topbar title */
    var titleMap = {
      dashboard: 'Dashboard',
      fleet: 'Fleet Management',
      workerDetail: 'Worker Detail',
      strategies: 'Strategy Registry',
      portfolio: 'Portfolio Analytics',
      logs: 'Event Logs',
      settings: 'Settings & Admin'
    };
    document.getElementById('topbar-title').textContent = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));

    /* Render new page */
    if (page === 'dashboard') {
      DashboardRenderer.render();
    } else if (page === 'fleet') {
      FleetRenderer.render();
    } else if (page === 'workerDetail' && _selectedWorker) {
      if (typeof WorkerDetailRenderer !== 'undefined') {
        WorkerDetailRenderer.render(_selectedWorker);
      } else {
        document.getElementById('main-content').innerHTML = _emptyState('fa-circle-exclamation', 'Worker Detail Unavailable', 'workerDetailRenderer.js may not be loaded. Check your HTML script tags.');
      }
    } else if (page === 'strategies') {
      StrategiesRenderer.render();
    } else if (page === 'portfolio') {
      PortfolioRenderer.render();
    } else if (page === 'logs') {
      LogsRenderer.render();
    } else if (page === 'settings') {
      SettingsRenderer.render();
    } else {
      renderPlaceholder(page);
    }
  }

  function navigateToWorkerDetail(workerData) {
    _selectedWorker = workerData;
    navigateTo('workerDetail');
  }

  function renderPlaceholder(page) {
    document.getElementById('main-content').innerHTML = _emptyState(
      'fa-gear',
      page.charAt(0).toUpperCase() + page.slice(1),
      'This page is under development.'
    );
  }

  function startClock() {
    function update() {
      var now = new Date();
      document.getElementById('topbar-clock').textContent =
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0') + ':' +
        String(now.getSeconds()).padStart(2, '0');
    }
    update();
    setInterval(update, 1000);
  }

  document.addEventListener('DOMContentLoaded', init);

  return {
    navigateTo: navigateTo,
    navigateToWorkerDetail: navigateToWorkerDetail
  };
})();