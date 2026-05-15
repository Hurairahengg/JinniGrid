/* ================================================================
   JINNI GRID — Mother Server Dashboard  (main.js)
   Combined: Renderers, ApiClient, Helpers, Router, Init.
   ================================================================ */

/* ── Deployment Config Constants ─────────────────────────────── */

var DeploymentConfig = {
  tickLookbackUnits: ['minutes', 'hours', 'days'],
  runtimeDefaults: {
    symbol: 'XAUUSD',
    lot_size: 0.01,
    bar_size_points: 100,
    max_bars_memory: 500,
    tick_lookback_value: 30,
    tick_lookback_unit: 'minutes',
  },
};

/* ── Global Settings (reads from backend /api/settings) ──────── */

var GlobalSettings = (function () {
  var _cache = null;
  function _fetch() {
    return fetch('/api/settings').then(function (r) { return r.json(); }).then(function (d) {
      _cache = d.settings || {};
      return _cache;
    }).catch(function () { _cache = {}; return _cache; });
  }
  function _get(key, fallback) {
    if (!_cache) return fallback;
    var v = _cache[key];
    return (v !== undefined && v !== null && v !== '') ? v : fallback;
  }
  function getDeploymentDefaults() {
    return {
      symbol: _get('default_symbol', 'XAUUSD'),
      lot_size: parseFloat(_get('default_lot_size', '0.01')),
      bar_size_points: parseFloat(_get('default_bar_size', '100')),
      max_bars_memory: parseInt(_get('default_max_bars', '500'), 10),
      tick_lookback_value: parseInt(_get('default_tick_lookback_value', '30'), 10),
      tick_lookback_unit: _get('default_tick_lookback_unit', 'minutes'),
    };
  }
  function getValidationDefaults() {
    var d = getDeploymentDefaults();
    d.spread_points = parseFloat(_get('default_spread', '0'));
    d.commission_per_lot = parseFloat(_get('default_commission', '0'));
    return d;
  }
  return { fetch: _fetch, get: _get, getDeploymentDefaults: getDeploymentDefaults, getValidationDefaults: getValidationDefaults };
})();

/* ── Toast Manager ───────────────────────────────────────────── */

var ToastManager = (function () {
  function _ensureContainer() {
    var c = document.getElementById('toast-container');
    if (!c) { c = document.createElement('div'); c.id = 'toast-container'; c.className = 'toast-container'; document.body.appendChild(c); }
    return c;
  }
  function show(message, type) {
    type = type || 'info';
    var container = _ensureContainer();
    var icons = { success: 'fa-circle-check', error: 'fa-circle-xmark', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };
    var el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.innerHTML = '<i class="fa-solid ' + (icons[type] || icons.info) + '"></i><span>' + message + '</span>' +
      '<button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';
    container.appendChild(el);
    el.querySelector('.toast-dismiss').addEventListener('click', function () { el.remove(); });
    setTimeout(function () { el.remove(); }, 5000);
  }
  return { show: show };
})();

/* ── Modal Manager ───────────────────────────────────────────── */

var ModalManager = (function () {
  function show(opts) {
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = '<div class="modal-card">' +
      '<div class="modal-header"><span class="modal-title">' + (opts.title || 'Confirm') + '</span>' +
      '<button class="modal-close"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body">' + (opts.bodyHtml || '') + '</div>' +
      '<div class="modal-footer">' +
      '<button class="wd-btn wd-btn-ghost modal-cancel-btn">Cancel</button>' +
      '<button class="wd-btn wd-btn-primary modal-confirm-btn" style="' + (opts.type === 'danger' ? 'background:var(--danger);' : '') + '">' + (opts.confirmText || 'Confirm') + '</button>' +
      '</div></div>';
    document.body.appendChild(overlay);
    function close() { overlay.remove(); }
    overlay.querySelector('.modal-close').addEventListener('click', close);
    overlay.querySelector('.modal-cancel-btn').addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    overlay.querySelector('.modal-confirm-btn').addEventListener('click', function () {
      close();
      if (opts.onConfirm) opts.onConfirm();
    });
  }
  return { show: show };
})();

/* ── Chart.js Helper ─────────────────────────────────────────── */

var ChartHelper = {
  accentColor: function () { return getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#06b6d4'; },
  successColor: function () { return getComputedStyle(document.documentElement).getPropertyValue('--success').trim() || '#10b981'; },
  dangerColor: function () { return getComputedStyle(document.documentElement).getPropertyValue('--danger').trim() || '#ef4444'; },
  mutedColor: function () { return getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#64748b'; },
  gridColor: function () { return getComputedStyle(document.documentElement).getPropertyValue('--border-subtle').trim() || '#162033'; },
  baseLineOpts: function (extra) {
    var base = {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false, bodyFont: { family: "'JetBrains Mono', monospace", size: 11 } } },
      scales: { x: { grid: { color: ChartHelper.gridColor() }, ticks: { color: ChartHelper.mutedColor(), font: { size: 10 } } }, y: { grid: { color: ChartHelper.gridColor() }, ticks: { color: ChartHelper.mutedColor(), font: { family: "'JetBrains Mono', monospace", size: 10 } } } },
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
    };
    if (extra) {
      if (extra.scales) { for (var k in extra.scales) { base.scales[k] = Object.assign(base.scales[k] || {}, extra.scales[k]); } }
      for (var k2 in extra) { if (k2 !== 'scales') base[k2] = extra[k2]; }
    }
    return base;
  }
};

/* ══════════════════════════════════════════════════════════════
   Shared UI Helpers (global — used by App + ValidationRenderer)
   ══════════════════════════════════════════════════════════════ */

function _spinner(size) {
  size = size || 60;
  return '<div class="loading-state"><div class="spinner" style="width:' + size + 'px;height:' + size + 'px;"></div></div>';
}

function _emptyState(icon, title, subtitle) {
  return '<div class="empty-state"><i class="fa-solid ' + icon + '"></i><h3>' + (title || '') + '</h3><p>' + (subtitle || '') + '</p></div>';
}

function _statPill(text, cls) {
  return '<span class="state-pill ' + (cls || '') + '">' + text + '</span>';
}

function _fmtMoney(v) {
  if (v === null || v === undefined) return '\u2014';
  return '$' + Number(v).toFixed(2);
}

function _fmtPct(v) {
  if (v === null || v === undefined) return '\u2014';
  return Number(v).toFixed(2) + '%';
}

function _metricItem(label, value, cls) {
  return '<div style="min-width:100px;">' +
    '<div class="mono ' + (cls || '') + '" style="font-size:14px;font-weight:600;">' + (value || '\u2014') + '</div>' +
    '<div style="font-size:10px;color:var(--text-muted);margin-top:2px;">' + label + '</div></div>';
}

/* ── API Client ──────────────────────────────────────────────── */

var ApiClient = (function () {
  function _json(url, opts) {
    return fetch(url, opts).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }
  return {
    getSystemSummary: function () { return _json('/api/system/summary'); },
    getFleetWorkers: function () { return _json('/api/Grid/workers'); },
    getPortfolioSummary: function (p) {
      var q = [];
      if (p) { if (p.strategy_id) q.push('strategy_id=' + p.strategy_id); if (p.worker_id) q.push('worker_id=' + p.worker_id); if (p.symbol) q.push('symbol=' + p.symbol); }
      return _json('/api/portfolio/summary' + (q.length ? '?' + q.join('&') : ''));
    },
    getEquityHistory: function () { return _json('/api/portfolio/equity-history'); },
    getPortfolioTrades: function (p) {
      var q = ['limit=500'];
      if (p) { if (p.strategy_id) q.push('strategy_id=' + p.strategy_id); if (p.worker_id) q.push('worker_id=' + p.worker_id); if (p.symbol) q.push('symbol=' + p.symbol); }
      return _json('/api/portfolio/trades?' + q.join('&'));
    },
    getPortfolioPerformance: function (p) {
      var q = [];
      if (p) { if (p.strategy_id) q.push('strategy_id=' + p.strategy_id); if (p.worker_id) q.push('worker_id=' + p.worker_id); if (p.symbol) q.push('symbol=' + p.symbol); }
      return _json('/api/portfolio/performance' + (q.length ? '?' + q.join('&') : ''));
    },
    getStrategies: function () { return _json('/api/grid/strategies'); },
    getStrategy: function (id) { return _json('/api/grid/strategies/' + id); },
    getDeployments: function () { return _json('/api/grid/deployments'); },
    createDeployment: function (payload) {
      return _json('/api/grid/deployments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    },
    stopDeployment: function (id) { return _json('/api/grid/deployments/' + id + '/stop', { method: 'POST' }); },
    getEvents: function (params) {
      var q = [];
      if (params) {
        if (params.category) q.push('category=' + params.category);
        if (params.level) q.push('level=' + params.level);
        if (params.worker_id) q.push('worker_id=' + params.worker_id);
        if (params.search) q.push('search=' + encodeURIComponent(params.search));
        if (params.limit) q.push('limit=' + params.limit);
      }
      return _json('/api/events' + (q.length ? '?' + q.join('&') : ''));
    },
    getSettings: function () { return _json('/api/settings'); },
    saveSettings: function (s) { return _json('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings: s }) }); },
    getAdminStats: function () { return _json('/api/admin/stats'); },
    adminDeleteStrategy: function (id) { return _json('/api/admin/strategies/' + id + '/delete', { method: 'POST' }); },
    adminResetPortfolio: function () { return _json('/api/admin/portfolio/reset', { method: 'POST' }); },
    adminClearTrades: function () { return _json('/api/admin/trades/clear', { method: 'POST' }); },
    adminRemoveWorker: function (id) { return _json('/api/admin/workers/' + id + '/remove', { method: 'POST' }); },
    adminRemoveStale: function () { return _json('/api/admin/workers/stale/remove', { method: 'POST' }); },
    adminClearEvents: function () { return _json('/api/admin/events/clear', { method: 'POST' }); },
    adminFullReset: function () { return _json('/api/admin/system/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: 'RESET_EVERYTHING' }) }); },
    emergencyStop: function () { return _json('/api/admin/emergency-stop', { method: 'POST' }); },
  };
})();

/* ══════════════════════════════════════════════════════════════
   App Router + Page Renderers
   ══════════════════════════════════════════════════════════════ */

var App = (function () {
  'use strict';
  var _currentPage = 'dashboard';
  var _refreshInterval = null;
  var _charts = {};

  function _destroyCharts() { for (var k in _charts) { if (_charts[k]) _charts[k].destroy(); } _charts = {}; }

  /* ── Private Helpers ──────────────────────────────────── */

  function _portfolioCard(icon, value, label, tone, isMoney, suffix) {
    var fmtVal;
    if (value === null || value === undefined) fmtVal = '\u2014';
    else if (isMoney) fmtVal = '$' + Number(value).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    else fmtVal = String(Number(value).toFixed(2));
    if (suffix) fmtVal += suffix;
    var valClass = '';
    if (tone === 'positive' && value > 0) valClass = ' positive';
    else if (tone === 'negative') valClass = ' negative';
    return '<div class="portfolio-card"><div class="card-icon ' + tone + '"><i class="fa-solid ' + icon + '"></i></div>' +
      '<div class="card-info"><span class="card-value' + valClass + '">' + fmtVal + '</span><span class="card-label">' + label + '</span></div></div>';
  }

  function _dashStat(value, label, isMoney) {
    var v = (value !== null && value !== undefined) ? Number(value) : 0;
    var txt = isMoney ? '$' + v.toFixed(2) : v.toFixed(2);
    var cls = '';
    if (isMoney) cls = v >= 0 ? ' positive' : ' negative';
    return '<div class="dash-stat-item"><span class="dash-stat-val' + cls + '">' + txt + '</span><span class="dash-stat-lbl">' + label + '</span></div>';
  }

  function _fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count + '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _fmtPnl(v) { if (v === null || v === undefined) return '\u2014'; var s = v >= 0 ? '+' : ''; return s + '$' + v.toFixed(2); }
  function _fmtAge(s) { if (s === null || s === undefined) return '\u2014'; s = Math.round(s); if (s < 60) return s + 's'; if (s < 3600) return Math.floor(s / 60) + 'm'; return Math.floor(s / 3600) + 'h'; }
  function _fmtNum(n) { if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'; if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'; return String(n); }
  function _escWorker(w) {
    return JSON.stringify(w).replace(/'/g, "\\'").replace(/"/g, '&quot;');
  }

  /* ── Page Titles ──────────────────────────────────────── */

  var _pageTitles = {
    dashboard: 'Dashboard', fleet: 'Fleet Management', charts: 'Charts', /* ★ NEW */
    portfolio: 'Portfolio', validation: 'Validation', strategies: 'Strategies',
    logs: 'Event Logs', settings: 'Settings',
  };

  /* ── Navigation ───────────────────────────────────────── */

  function navigateTo(page, data) {
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
    _destroyCharts();

    /* Destroy sub-renderers */
    if (_currentPage === 'worker-detail') WorkerDetailRenderer.destroy();
    if (_currentPage === 'validation') ValidationRenderer.destroy();
    if (_currentPage === 'charts') ChartRenderer.destroy(); /* ★ NEW */

    _currentPage = page;

    var navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(function (item) {
      var p = item.getAttribute('data-page');
      if (p === page || (page === 'worker-detail' && p === 'fleet')) item.classList.add('active');
      else item.classList.remove('active');
    });

    var titleEl = document.getElementById('topbar-title');
    if (titleEl) titleEl.textContent = _pageTitles[page] || page.charAt(0).toUpperCase() + page.slice(1);

    switch (page) {
      case 'dashboard': _renderDashboard(); break;
      case 'fleet': _renderFleet(); break;
      case 'charts': ChartRenderer.render(); break; /* ★ NEW */
      case 'worker-detail': WorkerDetailRenderer.render(data); break;
      case 'portfolio': _renderPortfolio(); break;
      case 'validation': ValidationRenderer.render(); break;
      case 'strategies': _renderStrategies(); break;
      case 'logs': _renderLogs(); break;
      case 'settings': _renderSettings(); break;
      default: _renderPlaceholder(page);
    }
  }

  /* ══════════════════════════════════════════════════════════
     DASHBOARD
     ══════════════════════════════════════════════════════════ */

  function _renderDashboard() {
    var content = document.getElementById('main-content');
    content.innerHTML = '<div class="dashboard" id="dashboard-root">' + _spinner() + '</div>';
    _fetchDashboard();
    _refreshInterval = setInterval(_fetchDashboard, 5000);
  }

  function _fetchDashboard() {
    Promise.all([
      ApiClient.getPortfolioSummary(),
      ApiClient.getFleetWorkers(),
      ApiClient.getEquityHistory(),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; }),
      ApiClient.getStrategies().catch(function () { return { strategies: [] }; }),
    ]).then(function (results) {
      var portfolio = results[0].portfolio || {};
      var fleet = results[1];
      var eqHistory = results[2].equity_history || [];
      var deployments = results[3].deployments || [];
      var strategies = results[4].strategies || [];
      _buildDashboard(portfolio, fleet, eqHistory, deployments, strategies);
    }).catch(function () {
      var root = document.getElementById('dashboard-root');
      if (root) root.innerHTML =
        '<div class="error-state"><i class="fa-solid fa-circle-exclamation"></i><h3>Failed to load dashboard</h3><p>Check server connection.</p>' +
        '<button class="retry-btn" onclick="App.navigateTo(\'dashboard\')">Retry</button></div>';
    });
  }

  function _buildDashboard(p, fleet, eqHistory, deployments, strategies) {
    var root = document.getElementById('dashboard-root');
    if (!root) return;
    var workers = fleet.workers || [];
    var summary = fleet.summary || {};

    var html = '';

    /* ── Row 1: Portfolio Cards ──────────────────────── */
    html += '<div><div class="section-header"><i class="fa-solid fa-chart-pie"></i><h2>Portfolio Overview</h2></div>';
    html += '<div class="portfolio-grid">';
    html += _portfolioCard('fa-wallet', p.total_balance, 'TOTAL BALANCE', 'neutral', true);
    html += _portfolioCard('fa-chart-line', p.total_equity, 'TOTAL EQUITY', 'neutral', true);
    html += _portfolioCard('fa-arrow-trend-up', p.net_pnl, 'NET P&L', (p.net_pnl || 0) >= 0 ? 'positive' : 'negative', true);
    html += _portfolioCard('fa-arrows-spin', p.floating_pnl, 'FLOATING P&L', (p.floating_pnl || 0) >= 0 ? 'positive' : 'negative', true);
    html += _portfolioCard('fa-percent', p.win_rate, 'WIN RATE', (p.win_rate || 0) >= 50 ? 'positive' : 'warning', false, '%');
    html += _portfolioCard('fa-scale-balanced', p.profit_factor, 'PROFIT FACTOR', (p.profit_factor || 0) >= 1 ? 'positive' : 'negative');
    html += _portfolioCard('fa-arrow-down', p.max_drawdown_pct, 'MAX DRAWDOWN', 'negative', false, '%');
    html += _portfolioCard('fa-hashtag', p.total_trades, 'TOTAL TRADES', 'neutral');
    html += '</div></div>';

    /* ── Row 2: Equity Chart + Stats Grid ────────────── */
    html += '<div class="dash-split-row">';

    /* Chart */
    html += '<section class="dash-chart-section"><div class="section-header"><i class="fa-solid fa-chart-area"></i><h2>Equity Curve</h2></div>';
    html += '<div class="chart-container"><div class="chart-wrapper"><canvas id="dash-equity-chart"></canvas></div></div></section>';

    /* Stats Grid */
    html += '<section class="dash-stats-section"><div class="section-header"><i class="fa-solid fa-calculator"></i><h2>Performance Stats</h2></div>';
    html += '<div class="dash-stats-grid">';
    html += _dashStat(p.avg_trade, 'Avg Trade', true);
    html += _dashStat(p.avg_winner, 'Avg Winner', true);
    html += _dashStat(p.avg_loser, 'Avg Loser', true);
    html += _dashStat(p.best_trade, 'Best Trade', true);
    html += _dashStat(p.worst_trade, 'Worst Trade', true);
    html += _dashStat(p.expectancy, 'Expectancy', true);
    html += _dashStat(p.sharpe_estimate, 'Sharpe');
    html += _dashStat(p.sortino_estimate, 'Sortino');
    html += _dashStat(p.recovery_factor, 'Recovery');
    html += _dashStat(p.avg_bars_held, 'Avg Bars');
    html += _dashStat(p.max_consec_wins, 'Max W Streak');
    html += _dashStat(p.max_consec_losses, 'Max L Streak');
    html += '</div></section>';
    html += '</div>';

    /* ── Row 3: Fleet Summary ────────────────────────── */
    html += '<div class="dashboard-fleet-section">';
    html += '<div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Overview</h2><span class="section-badge">' + (summary.total_workers || 0) + ' NODES</span></div>';
    html += '<div class="fleet-summary">';
    html += _fleetBadge(summary.total_workers || 0, 'Total', 'total');
    html += _fleetBadge(summary.online_workers || 0, 'Online', 'online');
    html += _fleetBadge(summary.warning_workers || 0, 'Warning', 'warning');
    html += _fleetBadge(summary.stale_workers || 0, 'Stale', 'stale');
    html += _fleetBadge(summary.offline_workers || 0, 'Offline', 'offline');
    html += _fleetBadge(summary.error_workers || 0, 'Error', 'error');
    html += '</div>';

    if (workers.length > 0) {
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      html += '<th>Worker</th><th>Status</th><th>Strategy</th><th>Symbol</th><th>Ticks</th><th>Bars</th><th>Signals</th><th>Price</th><th>P&L</th><th>Heartbeat</th>';
      html += '</tr></thead><tbody>';
      workers.forEach(function (w) {
        var strats = (w.active_strategies && w.active_strategies.length > 0) ? w.active_strategies.join(', ') : '<span class="value-null">\u2014</span>';
        var price = (w.current_price !== null && w.current_price !== undefined) ? w.current_price.toFixed(2) : '\u2014';
        var pnl = _fmtPnl(w.floating_pnl);
        var pnlClass = (w.floating_pnl || 0) >= 0 ? 'text-success' : 'text-danger';
        var hb = _fmtAge(w.heartbeat_age_seconds);
        html += '<tr class="clickable" onclick="App.navigateTo(\'worker-detail\', ' + _escWorker(w) + ')">';
        html += '<td class="mono">' + (w.worker_name || w.worker_id) + '</td>';
        html += '<td>' + _statPill((w.state || 'unknown').toUpperCase(), w.state) + '</td>';
        html += '<td class="mono" style="font-size:11px;">' + strats + '</td>';
        html += '<td class="mono">\u2014</td>';
        html += '<td class="mono">' + _fmtNum(w.total_ticks || 0) + '</td>';
        html += '<td class="mono">' + _fmtNum(w.total_bars || 0) + '</td>';
        html += '<td class="mono">' + (w.signal_count || 0) + '</td>';
        html += '<td class="mono">' + price + '</td>';
        html += '<td class="mono ' + pnlClass + '">' + pnl + '</td>';
        html += '<td>' + hb + '</td>';
        html += '</tr>';
      });
      html += '</tbody></table></div>';
      html += '<span class="view-fleet-link" onclick="App.navigateTo(\'fleet\')"><i class="fa-solid fa-arrow-right"></i> View full fleet</span>';
    }
    html += '</div>';

    root.innerHTML = html;

    /* ── Equity Chart ────────────────────────────────── */
    if (eqHistory.length > 1) {
      var labels = eqHistory.map(function (pt) { return pt.label || ''; });
      var values = eqHistory.map(function (pt) { return pt.equity; });
      var ctx = document.getElementById('dash-equity-chart');
      if (ctx) {
        var gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 280);
        gradient.addColorStop(0, 'rgba(6, 182, 212, 0.2)');
        gradient.addColorStop(1, 'rgba(6, 182, 212, 0)');
        _charts.dashEquity = new Chart(ctx, {
          type: 'line',
          data: { labels: labels, datasets: [{ data: values, borderColor: ChartHelper.accentColor(), backgroundColor: gradient, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0 }] },
          options: ChartHelper.baseLineOpts({ scales: { x: { display: false }, y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
        });
      }
    }
  }

  /* ══════════════════════════════════════════════════════════
     FLEET
     ══════════════════════════════════════════════════════════ */

  function _renderFleet() {
    var content = document.getElementById('main-content');
    content.innerHTML = '<div class="fleet-page" id="fleet-root">' + _spinner() + '</div>';
    _fetchFleet();
    _refreshInterval = setInterval(_fetchFleet, 5000);
  }

  function _fetchFleet() {
    ApiClient.getFleetWorkers().then(function (data) {
      var workers = data.workers || [];
      var summary = data.summary || {};
      _buildFleet(workers, summary);
    }).catch(function () {
      var root = document.getElementById('fleet-root');
      if (root) root.innerHTML = '<div class="error-state"><i class="fa-solid fa-circle-exclamation"></i><h3>Failed to load fleet</h3><button class="retry-btn" onclick="App.navigateTo(\'fleet\')">Retry</button></div>';
    });
  }

  function _buildFleet(workers, summary) {
    var root = document.getElementById('fleet-root');
    if (!root) return;
    var html = '<div class="fleet-page-header"><span class="fleet-page-title">Fleet Management</span>' +
      '<div class="fleet-page-meta"><div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Auto-refresh 5s</div></div></div>';

    html += '<div class="fleet-summary">';
    html += _fleetBadge(summary.total_workers || 0, 'Total', 'total');
    html += _fleetBadge(summary.online_workers || 0, 'Online', 'online');
    html += _fleetBadge(summary.stale_workers || 0, 'Stale', 'stale');
    html += _fleetBadge(summary.offline_workers || 0, 'Offline', 'offline');
    html += _fleetBadge(summary.error_workers || 0, 'Error', 'error');
    html += '</div>';

    if (workers.length === 0) {
      html += _emptyState('fa-server', 'No Workers Registered', 'Start a worker agent and it will appear here.');
    } else {
      html += '<div class="fleet-grid">';
      workers.forEach(function (w) {
        var state = w.state || 'unknown';
        var name = w.worker_name || w.worker_id;
        var strats = (w.active_strategies && w.active_strategies.length > 0) ? w.active_strategies.join(', ') : '\u2014';
        var price = (w.current_price !== null && w.current_price !== undefined) ? w.current_price.toFixed(2) : '\u2014';
        var pnl = _fmtPnl(w.floating_pnl);
        var pnlClass = (w.floating_pnl || 0) >= 0 ? 'text-success' : 'text-danger';

        html += '<div class="node-card clickable" onclick="App.navigateTo(\'worker-detail\', ' + _escWorker(w) + ')">';
        html += '<div class="node-card-top ' + state + '"></div>';
        html += '<div class="node-card-header"><div class="node-name-group"><span class="node-status-dot ' + state + '"></span><span class="node-name">' + name + '</span></div>';
        html += '<span class="node-status-badge ' + state + '">' + state.toUpperCase() + '</span></div>';
        html += '<div class="node-card-body">';
        html += '<div class="node-info-row"><span class="node-info-label">ID</span><span class="node-info-value">' + w.worker_id + '</span></div>';
        html += '<div class="node-info-row"><span class="node-info-label">Host</span><span class="node-info-value">' + (w.host || '\u2014') + '</span></div>';
        html += '<div class="node-info-row"><span class="node-info-label">Strategy</span><span class="node-info-value strategy">' + strats + '</span></div>';
        html += '<div class="node-info-row"><span class="node-info-label">Price</span><span class="node-info-value">' + price + '</span></div>';
        html += '<div class="node-info-row"><span class="node-info-label">P&L</span><span class="node-info-value ' + pnlClass + '">' + pnl + '</span></div>';
        html += '<div class="node-info-row"><span class="node-info-label">Heartbeat</span><span class="node-info-value">' + _fmtAge(w.heartbeat_age_seconds) + '</span></div>';
        html += '<div class="node-card-action"><i class="fa-solid fa-arrow-right"></i> View Details</div>';
        html += '</div></div>';
      });
      html += '</div>';
    }
    root.innerHTML = html;
  }

  /* ══════════════════════════════════════════════════════════
     PORTFOLIO
     ══════════════════════════════════════════════════════════ */

  function _renderPortfolio() {
    var content = document.getElementById('main-content');
    content.innerHTML = '<div class="fleet-page" id="portfolio-root">' + _spinner() + '</div>';
    _fetchPortfolio();
  }

  function _fetchPortfolio(filters) {
    Promise.all([
      ApiClient.getPortfolioSummary(filters),
      ApiClient.getPortfolioTrades(filters),
      ApiClient.getPortfolioPerformance(filters),
      ApiClient.getEquityHistory(),
    ]).then(function (r) {
      _buildPortfolio(r[0].portfolio || {}, r[1].trades || [], r[2].performance || {}, r[3].equity_history || [], filters);
    }).catch(function () {
      var root = document.getElementById('portfolio-root');
      if (root) root.innerHTML = '<div class="error-state"><i class="fa-solid fa-circle-exclamation"></i><h3>Failed to load portfolio</h3><button class="retry-btn" onclick="App.navigateTo(\'portfolio\')">Retry</button></div>';
    });
  }

  function _buildPortfolio(p, trades, perf, eqHistory, filters) {
    var root = document.getElementById('portfolio-root');
    if (!root) return;
    filters = filters || {};
    var html = '<div class="fleet-page-header"><span class="fleet-page-title">Portfolio</span></div>';

    /* ── Filter Panel ──────────────────────────────── */
    var byStrat = perf.by_strategy || [];
    var byWorker = perf.by_worker || [];
    var bySymbol = perf.by_symbol || [];

    html += '<div class="wd-panel" style="margin-bottom:16px;"><div class="wd-panel-body"><div class="wd-form-grid" style="grid-template-columns:1fr 1fr 1fr 1fr;">';

    /* Strategy filter */
    html += '<div class="wd-form-group"><label class="wd-form-label">Strategy</label>';
    html += '<select class="wd-form-select" id="pf-filter-strategy"><option value="">All</option>';
    byStrat.forEach(function (s) {
      var sel = (filters.strategy_id === s.strategy_id) ? ' selected' : '';
      html += '<option value="' + s.strategy_id + '"' + sel + '>' + s.strategy_id + '</option>';
    });
    html += '</select></div>';

    /* Worker filter */
    html += '<div class="wd-form-group"><label class="wd-form-label">Worker</label>';
    html += '<select class="wd-form-select" id="pf-filter-worker"><option value="">All</option>';
    byWorker.forEach(function (w) {
      var sel = (filters.worker_id === w.worker_id) ? ' selected' : '';
      html += '<option value="' + w.worker_id + '"' + sel + '>' + w.worker_id + '</option>';
    });
    html += '</select></div>';

    /* Symbol filter */
    html += '<div class="wd-form-group"><label class="wd-form-label">Symbol</label>';
    html += '<select class="wd-form-select" id="pf-filter-symbol"><option value="">All</option>';
    bySymbol.forEach(function (s) {
      var sel = (filters.symbol === s.symbol) ? ' selected' : '';
      html += '<option value="' + s.symbol + '"' + sel + '>' + s.symbol + '</option>';
    });
    html += '</select></div>';

    /* Apply */
    html += '<div class="wd-form-group" style="align-self:flex-end;"><button class="wd-btn wd-btn-primary" id="pf-filter-apply"><i class="fa-solid fa-filter"></i> Apply</button></div>';
    html += '</div></div></div>';

    /* ── Cards ─────────────────────────────────────── */
    html += '<div class="portfolio-grid">';
    html += _portfolioCard('fa-wallet', p.total_balance, 'BALANCE', 'neutral', true);
    html += _portfolioCard('fa-chart-line', p.total_equity, 'EQUITY', 'neutral', true);
    html += _portfolioCard('fa-arrow-trend-up', p.net_pnl, 'NET P&L', (p.net_pnl || 0) >= 0 ? 'positive' : 'negative', true);
    html += _portfolioCard('fa-percent', p.win_rate, 'WIN RATE', (p.win_rate || 0) >= 50 ? 'positive' : 'warning', false, '%');
    html += _portfolioCard('fa-scale-balanced', p.profit_factor, 'PROFIT FACTOR', (p.profit_factor || 0) >= 1 ? 'positive' : 'negative');
    html += _portfolioCard('fa-arrow-down', p.max_drawdown_pct, 'MAX DD', 'negative', false, '%');
    html += _portfolioCard('fa-hashtag', p.total_trades, 'TRADES', 'neutral');
    html += _portfolioCard('fa-arrows-spin', p.floating_pnl, 'FLOATING', (p.floating_pnl || 0) >= 0 ? 'positive' : 'negative', true);
    html += '</div>';

    /* ── Equity Curve ──────────────────────────────── */
    if (eqHistory.length > 1) {
      html += '<div class="chart-container" style="margin-top:20px;"><div class="chart-header"><span class="chart-title">Equity Curve</span></div>';
      html += '<div class="chart-wrapper"><canvas id="port-eq-chart"></canvas></div></div>';
    }

    /* ── Daily P&L ─────────────────────────────────── */
    var daily = perf.daily || [];
    if (daily.length > 0) {
      html += '<div class="chart-container" style="margin-top:20px;"><div class="chart-header"><span class="chart-title">Daily P&L</span></div>';
      html += '<div class="chart-wrapper"><canvas id="port-daily-chart"></canvas></div></div>';
    }

    /* ── Monthly Performance ───────────────────────── */
    var monthly = perf.monthly || [];
    if (monthly.length > 0) {
      html += '<div style="margin-top:20px;"><div class="section-header"><i class="fa-solid fa-calendar-days"></i><h2>Monthly Performance</h2></div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      html += '<th>Month</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>P&L</th>';
      html += '</tr></thead><tbody>';
      monthly.forEach(function (m) {
        var pc = (m.pnl || 0) >= 0 ? 'text-success' : 'text-danger';
        html += '<tr><td class="mono">' + m.month + '</td><td class="mono">' + m.trades + '</td><td class="mono">' + (m.wins || 0) + '</td>' +
          '<td class="mono">' + _fmtPct(m.win_rate) + '</td><td class="mono ' + pc + '">' + _fmtMoney(m.pnl) + '</td></tr>';
      });
      html += '</tbody></table></div></div>';
    }

    /* ── Breakdowns ────────────────────────────────── */
    function _breakdownTable(title, items, keyField) {
      if (!items || items.length === 0) return '';
      var out = '<div style="margin-top:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">' + title + '</div>';
      out += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      out += '<th>' + keyField + '</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>PF</th><th>Avg Bars</th><th>P&L</th>';
      out += '</tr></thead><tbody>';
      items.forEach(function (item) {
        var pc = (item.pnl || 0) >= 0 ? 'text-success' : 'text-danger';
        out += '<tr><td class="mono">' + (item[keyField.toLowerCase().replace(' ', '_')] || item[Object.keys(item)[0]] || '') + '</td>' +
          '<td class="mono">' + (item.trades || 0) + '</td>' +
          '<td class="mono">' + (item.wins || 0) + '</td>' +
          '<td class="mono">' + _fmtPct(item.win_rate) + '</td>' +
          '<td class="mono">' + (item.profit_factor || 0) + '</td>' +
          '<td class="mono">' + (item.avg_bars || 0) + '</td>' +
          '<td class="mono ' + pc + '">' + _fmtMoney(item.pnl) + '</td></tr>';
      });
      out += '</tbody></table></div></div>';
      return out;
    }

    html += _breakdownTable('By Strategy', byStrat, 'strategy_id');
    html += _breakdownTable('By Worker', byWorker, 'worker_id');
    html += _breakdownTable('By Symbol', bySymbol, 'symbol');

    /* ── Trades Table ──────────────────────────────── */
    if (trades.length > 0) {
      html += '<div style="margin-top:20px;"><div class="section-header"><i class="fa-solid fa-receipt"></i><h2>Recent Trades</h2><span class="section-badge">' + trades.length + '</span></div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      html += '<th>ID</th><th>Symbol</th><th>Dir</th><th>Entry</th><th>Exit</th><th>SL</th><th>TP</th><th>P&L</th><th>Bars</th><th>Reason</th><th>Time</th>';
      html += '</tr></thead><tbody>';
      trades.slice(0, 100).forEach(function (t) {
        var pc = (t.profit || 0) >= 0 ? 'text-success' : 'text-danger';
        var et = t.exit_time ? String(t.exit_time).substring(0, 19) : '\u2014';
        html += '<tr><td class="mono">' + (t.trade_id || t.id || '') + '</td>' +
          '<td class="mono">' + (t.symbol || '') + '</td>' +
          '<td>' + _statPill((t.direction || '').toUpperCase(), t.direction === 'long' ? 'online' : 'error') + '</td>' +
          '<td class="mono">' + (t.entry_price || '') + '</td>' +
          '<td class="mono">' + (t.exit_price || '') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.sl || t.sl_level || '\u2014') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.tp || t.tp_level || '\u2014') + '</td>' +
          '<td class="mono ' + pc + '">' + _fmtMoney(t.profit) + '</td>' +
          '<td class="mono">' + (t.bars_held || 0) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.exit_reason || '') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + et + '</td></tr>';
      });
      html += '</tbody></table></div></div>';
    }

    root.innerHTML = html;

    /* ── Render Charts ─────────────────────────────── */
    if (eqHistory.length > 1) {
      var eqCtx = document.getElementById('port-eq-chart');
      if (eqCtx) {
        var eqLabels = eqHistory.map(function (pt) { return pt.label || ''; });
        var eqValues = eqHistory.map(function (pt) { return pt.equity; });
        var g = eqCtx.getContext('2d').createLinearGradient(0, 0, 0, 280);
        g.addColorStop(0, 'rgba(6,182,212,0.2)');
        g.addColorStop(1, 'rgba(6,182,212,0)');
        _charts.portEq = new Chart(eqCtx, {
          type: 'line',
          data: { labels: eqLabels, datasets: [{ data: eqValues, borderColor: ChartHelper.accentColor(), backgroundColor: g, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0 }] },
          options: ChartHelper.baseLineOpts({ scales: { x: { display: false }, y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
        });
      }
    }

    if (daily.length > 0) {
      var dailyCtx = document.getElementById('port-daily-chart');
      if (dailyCtx) {
        var dLabels = daily.map(function (d) { return d.date; });
        var dValues = daily.map(function (d) { return d.pnl; });
        var dColors = dValues.map(function (v) { return v >= 0 ? ChartHelper.successColor() : ChartHelper.dangerColor(); });
        _charts.portDaily = new Chart(dailyCtx, {
          type: 'bar',
          data: { labels: dLabels, datasets: [{ data: dValues, backgroundColor: dColors, borderRadius: 3 }] },
          options: ChartHelper.baseLineOpts({ scales: { x: { display: daily.length <= 60, ticks: { maxRotation: 45 } }, y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
        });
      }
    }

    /* ── Filter Events ─────────────────────────────── */
    var applyBtn = document.getElementById('pf-filter-apply');
    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        _destroyCharts();
        _fetchPortfolio({
          strategy_id: document.getElementById('pf-filter-strategy').value || undefined,
          worker_id: document.getElementById('pf-filter-worker').value || undefined,
          symbol: document.getElementById('pf-filter-symbol').value || undefined,
        });
      });
    }
  }

  /* ══════════════════════════════════════════════════════════
     STRATEGIES
     ══════════════════════════════════════════════════════════ */

  function _renderStrategies() {
    var content = document.getElementById('main-content');
    content.innerHTML = '<div class="fleet-page" id="strat-root">' + _spinner() + '</div>';
    _fetchStrategies();
  }

  function _fetchStrategies() {
    ApiClient.getStrategies().then(function (data) {
      var strats = data.strategies || [];
      _buildStrategies(strats);
    }).catch(function () {
      var root = document.getElementById('strat-root');
      if (root) root.innerHTML = '<div class="error-state"><i class="fa-solid fa-circle-exclamation"></i><h3>Failed to load strategies</h3><button class="retry-btn" onclick="App.navigateTo(\'strategies\')">Retry</button></div>';
    });
  }

  function _buildStrategies(strats) {
    var root = document.getElementById('strat-root');
    if (!root) return;
    var html = '<div class="fleet-page-header"><span class="fleet-page-title">Strategies</span>' +
      '<div class="fleet-page-meta"><label class="wd-btn wd-btn-primary" style="cursor:pointer;"><i class="fa-solid fa-upload"></i> Upload .py<input type="file" accept=".py" id="strat-upload-input" style="display:none;" /></label></div></div>';

    if (strats.length === 0) {
      html += _emptyState('fa-crosshairs', 'No Strategies', 'Upload a <code>.py</code> file containing a class extending <code>BaseStrategy</code>.');
    } else {
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      html += '<th>ID</th><th>Name</th><th>Version</th><th>Class</th><th>Params</th><th>Lookback</th><th>Status</th><th>Uploaded</th><th></th>';
      html += '</tr></thead><tbody>';
      strats.forEach(function (s) {
        var st = s.validation_status === 'validated' ? 'online' : 'error';
        html += '<tr><td class="mono" style="color:var(--accent);">' + s.strategy_id + '</td>' +
          '<td>' + (s.strategy_name || s.name || '') + '</td>' +
          '<td class="mono">' + (s.version || '') + '</td>' +
          '<td class="mono">' + (s.class_name || '') + '</td>' +
          '<td class="mono">' + (s.parameter_count || 0) + '</td>' +
          '<td class="mono">' + (s.min_lookback || 0) + '</td>' +
          '<td>' + _statPill((s.validation_status || 'unknown').toUpperCase(), st) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (s.uploaded_at || '').substring(0, 16) + '</td>' +
          '<td><button class="wd-btn wd-btn-ghost strat-del-btn" data-sid="' + s.strategy_id + '" style="font-size:10px;color:var(--danger);"><i class="fa-solid fa-trash"></i></button></td></tr>';
      });
      html += '</tbody></table></div>';
    }
    root.innerHTML = html;

    /* Upload handler */
    var uploadInput = document.getElementById('strat-upload-input');
    if (uploadInput) {
      uploadInput.addEventListener('change', function () {
        if (!uploadInput.files.length) return;
        var file = uploadInput.files[0];
        var formData = new FormData();
        formData.append('file', file);
        fetch('/api/grid/strategies/upload', { method: 'POST', body: formData })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d.ok) { ToastManager.show('Strategy uploaded: ' + d.strategy_id, 'success'); _fetchStrategies(); }
            else ToastManager.show('Upload failed: ' + (d.error || d.detail || 'Unknown'), 'error');
          }).catch(function (e) { ToastManager.show('Upload error: ' + e.message, 'error'); });
        uploadInput.value = '';
      });
    }

    /* Delete handlers */
    document.querySelectorAll('.strat-del-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var sid = btn.getAttribute('data-sid');
        ModalManager.show({
          title: 'Delete Strategy', type: 'danger',
          bodyHtml: '<p>Delete strategy <strong>' + sid + '</strong> and all associated data?</p>',
          confirmText: 'Delete',
          onConfirm: function () {
            ApiClient.adminDeleteStrategy(sid).then(function () { ToastManager.show('Deleted.', 'success'); _fetchStrategies(); });
          }
        });
      });
    });
  }

  /* ══════════════════════════════════════════════════════════
     LOGS
     ══════════════════════════════════════════════════════════ */

  function _renderLogs() {
    var content = document.getElementById('main-content');
    content.innerHTML = '<div class="fleet-page" id="logs-root">' + _spinner() + '</div>';
    _fetchLogs();
  }

  function _fetchLogs(params) {
    ApiClient.getEvents(params).then(function (data) {
      _buildLogs(data.events || [], data.count || 0, params);
    }).catch(function () {
      var root = document.getElementById('logs-root');
      if (root) root.innerHTML = '<div class="error-state"><i class="fa-solid fa-circle-exclamation"></i><h3>Failed to load logs</h3></div>';
    });
  }

  function _buildLogs(events, count, filters) {
    var root = document.getElementById('logs-root');
    if (!root) return;
    filters = filters || {};
    var html = '<div class="fleet-page-header"><span class="fleet-page-title">Event Logs</span><span class="section-badge">' + count + ' EVENTS</span></div>';

    /* Filters */
    html += '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;align-items:flex-end;">';
    html += '<div class="wd-form-group"><label class="wd-form-label">Category</label><select class="wd-form-select" id="log-cat-filter"><option value="">All</option>';
    ['execution', 'strategy', 'deployment', 'worker', 'command', 'system', 'validation'].forEach(function (c) {
      var sel = (filters.category === c) ? ' selected' : '';
      html += '<option value="' + c + '"' + sel + '>' + c + '</option>';
    });
    html += '</select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Level</label><select class="wd-form-select" id="log-level-filter"><option value="">All</option>';
    ['INFO', 'WARNING', 'ERROR'].forEach(function (l) {
      var sel = (filters.level === l) ? ' selected' : '';
      html += '<option value="' + l + '"' + sel + '>' + l + '</option>';
    });
    html += '</select></div>';
    html += '<div class="wd-form-group"><label class="wd-form-label">Search</label><input type="text" class="wd-form-input" id="log-search-filter" placeholder="Search\u2026" value="' + (filters.search || '') + '" /></div>';
    html += '<div class="wd-form-group"><button class="wd-btn wd-btn-ghost" id="log-filter-btn"><i class="fa-solid fa-filter"></i> Filter</button></div>';
    html += '</div>';

    if (events.length === 0) {
      html += _emptyState('fa-scroll', 'No Events', 'No events match your filters.');
    } else {
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table log-table"><thead><tr>';
      html += '<th>Time</th><th>Cat</th><th>Type</th><th>Level</th><th>Message</th>';
      html += '</tr></thead><tbody>';
      events.forEach(function (e) {
        var lvlClass = e.level === 'ERROR' ? 'text-danger' : (e.level === 'WARNING' ? 'text-warning' : '');
        var ts = e.timestamp ? e.timestamp.substring(11, 19) : '';
        html += '<tr class="log-row"><td class="mono" style="font-size:10px;">' + ts + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (e.category || '') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (e.event_type || '') + '</td>' +
          '<td class="' + lvlClass + '" style="font-size:10px;font-weight:600;">' + (e.level || '') + '</td>' +
          '<td style="font-size:11px;max-width:500px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (e.message || '') + '</td></tr>';
      });
      html += '</tbody></table></div>';
    }
    root.innerHTML = html;

    document.getElementById('log-filter-btn').addEventListener('click', function () {
      _fetchLogs({
        category: document.getElementById('log-cat-filter').value,
        level: document.getElementById('log-level-filter').value,
        search: document.getElementById('log-search-filter').value,
      });
    });
  }

  /* ══════════════════════════════════════════════════════════
     SETTINGS
     ══════════════════════════════════════════════════════════ */

  function _renderSettings() {
    var content = document.getElementById('main-content');
    content.innerHTML = '<div class="fleet-page" id="settings-root">' + _spinner() + '</div>';
    ApiClient.getSettings().then(function (data) {
      _buildSettings(data.settings || {});
    }).catch(function () {
      document.getElementById('settings-root').innerHTML = '<div class="error-state"><h3>Failed to load settings</h3></div>';
    });
  }

  function _buildSettings(settings) {
    var root = document.getElementById('settings-root');
    if (!root) return;
    var html = '<div class="fleet-page-header"><span class="fleet-page-title">System Settings</span></div>';

    /* ── Config Panel ──────────────────────────────── */
    html += '<div class="wd-panel"><div class="wd-panel-header">Configuration</div><div class="wd-panel-body"><div class="wd-form-grid">';

    var fields = [
      { key: 'default_symbol', label: 'Default Symbol', type: 'text' },
      { key: 'default_bar_size', label: 'Default Bar Size', type: 'number' },
      { key: 'default_lot_size', label: 'Default Lot Size', type: 'number' },
      { key: 'default_max_bars', label: 'Default Max Bars', type: 'number' },
      { key: 'default_tick_lookback_value', label: 'Tick Lookback Value', type: 'number' },
      { key: 'default_tick_lookback_unit', label: 'Tick Lookback Unit', type: 'text' },
      { key: 'default_spread', label: 'Default Spread', type: 'number' },
      { key: 'default_commission', label: 'Default Commission', type: 'number' },
      { key: 'worker_timeout_seconds', label: 'Worker Timeout (s)', type: 'number' },
      { key: 'refresh_interval', label: 'Refresh Interval (s)', type: 'number' },
      { key: 'log_verbosity', label: 'Log Verbosity', type: 'text' },
    ];

    fields.forEach(function (f) {
      html += '<div class="wd-form-group"><label class="wd-form-label">' + f.label + '</label>' +
        '<input type="' + f.type + '" class="wd-form-input settings-input" data-key="' + f.key + '" value="' + (settings[f.key] || '') + '" /></div>';
    });

    html += '</div></div>';
    html += '<div class="wd-action-bar"><div class="wd-action-bar-left"></div><div class="wd-action-bar-right">' +
      '<button class="wd-btn wd-btn-primary" id="settings-save"><i class="fa-solid fa-floppy-disk"></i> Save Settings</button></div></div></div>';

    /* ── Danger Zone ───────────────────────────────── */
    html += '<div class="wd-panel" style="margin-top:20px;"><div class="wd-panel-header" style="color:var(--danger);">Danger Zone</div><div class="wd-panel-body">' +
      '<div style="display:flex;flex-wrap:wrap;gap:10px;">' +
      '<button class="wd-btn wd-btn-ghost" id="admin-clear-trades" style="color:var(--danger);border-color:var(--danger);"><i class="fa-solid fa-trash"></i> Clear Trades</button>' +
      '<button class="wd-btn wd-btn-ghost" id="admin-clear-events" style="color:var(--danger);border-color:var(--danger);"><i class="fa-solid fa-trash"></i> Clear Events</button>' +
      '<button class="wd-btn wd-btn-ghost" id="admin-remove-stale" style="color:var(--warning);border-color:var(--warning);"><i class="fa-solid fa-broom"></i> Remove Stale Workers</button>' +
      '<button class="wd-btn wd-btn-ghost" id="admin-reset-portfolio" style="color:var(--danger);border-color:var(--danger);"><i class="fa-solid fa-rotate-left"></i> Reset Portfolio</button>' +
      '<button class="wd-btn wd-btn-ghost" id="admin-full-reset" style="color:var(--danger);border-color:var(--danger);font-weight:700;"><i class="fa-solid fa-skull-crossbones"></i> FULL SYSTEM RESET</button>' +
      '</div></div></div>';

    root.innerHTML = html;

    /* ── Events ────────────────────────────────────── */
    document.getElementById('settings-save').addEventListener('click', function () {
      var s = {};
      document.querySelectorAll('.settings-input').forEach(function (input) {
        s[input.getAttribute('data-key')] = input.value;
      });
      ApiClient.saveSettings(s).then(function () {
        ToastManager.show('Settings saved.', 'success');
        GlobalSettings.fetch();
      }).catch(function () { ToastManager.show('Save failed.', 'error'); });
    });

    document.getElementById('admin-clear-trades').addEventListener('click', function () {
      ModalManager.show({ title: 'Clear All Trades', type: 'danger', bodyHtml: '<p>Delete ALL trade records?</p>', confirmText: 'Clear',
        onConfirm: function () { ApiClient.adminClearTrades().then(function (d) { ToastManager.show('Trades cleared: ' + (d.trades_deleted || 0), 'success'); }); } });
    });
    document.getElementById('admin-clear-events').addEventListener('click', function () {
      ModalManager.show({ title: 'Clear Events', type: 'danger', bodyHtml: '<p>Delete ALL event logs?</p>', confirmText: 'Clear',
        onConfirm: function () { ApiClient.adminClearEvents().then(function () { ToastManager.show('Events cleared.', 'success'); }); } });
    });
    document.getElementById('admin-remove-stale').addEventListener('click', function () {
      ApiClient.adminRemoveStale().then(function (d) { ToastManager.show('Removed ' + (d.removed || 0) + ' stale workers.', 'info'); });
    });
    document.getElementById('admin-reset-portfolio').addEventListener('click', function () {
      ModalManager.show({ title: 'Reset Portfolio', type: 'danger', bodyHtml: '<p>Clear ALL trades + equity history?</p>', confirmText: 'Reset',
        onConfirm: function () { ApiClient.adminResetPortfolio().then(function () { ToastManager.show('Portfolio reset.', 'success'); }); } });
    });
    document.getElementById('admin-full-reset').addEventListener('click', function () {
      ModalManager.show({ title: 'FULL SYSTEM RESET', type: 'danger',
        bodyHtml: '<p>This will delete <strong>EVERYTHING</strong>: workers, strategies, deployments, trades, events.</p><div class="modal-warning"><i class="fa-solid fa-skull-crossbones"></i><span>This action is irreversible!</span></div>',
        confirmText: 'RESET EVERYTHING',
        onConfirm: function () { ApiClient.adminFullReset().then(function () { ToastManager.show('System reset complete.', 'success'); navigateTo('dashboard'); }); } });
    });
  }

  /* ══════════════════════════════════════════════════════════
     PLACEHOLDER
     ══════════════════════════════════════════════════════════ */

  function _renderPlaceholder(page) {
    document.getElementById('main-content').innerHTML =
      '<div class="placeholder-page"><i class="fa-solid fa-hammer"></i><h2>' + (page || 'Page') + '</h2><p>Coming soon.</p></div>';
  }

  return { navigateTo: navigateTo };
})();

/* ══════════════════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════════════════ */

(function () {
  /* ── Clock ────────────────────────────────────────────── */
  function _updateClock() {
    var el = document.getElementById('topbar-clock');
    if (el) {
      var d = new Date();
      el.textContent = String(d.getHours()).padStart(2, '0') + ':' +
        String(d.getMinutes()).padStart(2, '0') + ':' +
        String(d.getSeconds()).padStart(2, '0');
    }
  }
  setInterval(_updateClock, 1000);
  _updateClock();

  /* ── Theme Toggle ─────────────────────────────────────── */
  var themeBtn = document.getElementById('theme-toggle');
  var saved = localStorage.getItem('jinni-theme');
  if (saved) document.body.setAttribute('data-theme', saved);

  function _syncThemeBtn() {
    var dark = document.body.getAttribute('data-theme') !== 'light';
    if (themeBtn) {
      themeBtn.querySelector('i').className = dark ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
      var sp = themeBtn.querySelector('span');
      if (sp) sp.textContent = dark ? 'Light Mode' : 'Dark Mode';
    }
  }
  _syncThemeBtn();
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.body.setAttribute('data-theme', next);
      localStorage.setItem('jinni-theme', next);
      _syncThemeBtn();
      /* ★ NEW: Sync LW chart theme */
      if (typeof ChartRenderer !== 'undefined' && ChartRenderer.applyTheme) ChartRenderer.applyTheme();
    });
  }

  /* ★ NEW: Sidebar Collapse ─────────────────────────────── */
  var sidebar = document.getElementById('sidebar');
  var collapseBtn = document.getElementById('sidebar-collapse-btn');
  var sidebarState = localStorage.getItem('jinni-sidebar');
  if (sidebarState === 'collapsed' && sidebar) sidebar.classList.add('collapsed');

  if (collapseBtn) {
    collapseBtn.addEventListener('click', function () {
      sidebar.classList.toggle('collapsed');
      var isCollapsed = sidebar.classList.contains('collapsed');
      localStorage.setItem('jinni-sidebar', isCollapsed ? 'collapsed' : 'expanded');
    });
  }

  /* ── Nav Click ────────────────────────────────────────── */
  document.querySelectorAll('.nav-item').forEach(function (item) {
    item.addEventListener('click', function (e) {
      e.preventDefault();
      App.navigateTo(item.getAttribute('data-page'));
    });
  });

  /* ── Boot ─────────────────────────────────────────────── */
  GlobalSettings.fetch().then(function () {
    App.navigateTo('dashboard');
  });
})();