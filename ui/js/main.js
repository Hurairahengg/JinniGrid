/* jinni-grid-combined.js
   Combined from:
   - apiClient.js
   - deploymentMockData.js
   - modalManager.js
   - toastManager.js
   - themeManager.js
   - dashboardRenderer.js
   - fleetRenderer.js
   - strategiesRenderer.js
   - app.js

   Note:
   - WorkerDetailRenderer is referenced by App but was not included in the files provided.
   - Keep WorkerDetailRenderer loaded separately or send it and I will merge it too.
*/

/* apiClient.js */

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
            var json = JSON.parse(text);
            if (json.detail) {
              msg = typeof json.detail === 'string' ? json.detail
                : (json.detail.error || JSON.stringify(json.detail));
            }
          } catch (e) {
            if (text) msg = text;
          }
          var err = new Error(msg);
          err.status = res.status;
          throw err;
        });
      }
      return res.json();
    });
  }

  function _upload(path, file) {
    var fd = new FormData();
    fd.append('file', file);
    return fetch(path, { method: 'POST', body: fd }).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          var msg = 'HTTP ' + res.status;
          try {
            var json = JSON.parse(text);
            if (json.detail) {
              msg = typeof json.detail === 'string' ? json.detail
                : (json.detail.error || JSON.stringify(json.detail));
            }
          } catch (e) {
            if (text) msg = text;
          }
          throw new Error(msg);
        });
      }
      return res.json();
    });
  }

  return {
    /* Fleet */
    getFleetWorkers: function () {
      return _request('GET', '/api/grid/workers');
    },
    getSystemSummary: function () {
      return _request('GET', '/api/system/summary');
    },
    getHealth: function () {
      return _request('GET', '/api/health');
    },

    /* Strategies */
    getStrategies: function () {
      return _request('GET', '/api/grid/strategies');
    },
    getStrategy: function (id) {
      return _request('GET', '/api/grid/strategies/' + encodeURIComponent(id));
    },
    uploadStrategy: function (file) {
      return _upload('/api/grid/strategies/upload', file);
    },
    validateStrategy: function (id) {
      return _request('POST', '/api/grid/strategies/' + encodeURIComponent(id) + '/validate');
    },

    /* Deployments */
    createDeployment: function (cfg) {
      return _request('POST', '/api/grid/deployments', cfg);
    },
    getDeployments: function () {
      return _request('GET', '/api/grid/deployments');
    },
    getDeployment: function (id) {
      return _request('GET', '/api/grid/deployments/' + encodeURIComponent(id));
    },
    stopDeployment: function (id) {
      return _request('POST', '/api/grid/deployments/' + encodeURIComponent(id) + '/stop');
    }
  };
})();

/* deploymentMockData.js — Runtime config defaults & dropdown options */

var DeploymentConfig = (function () {
  'use strict';

  var runtimeDefaults = {
    symbol: 'EURUSD',
    lot_size: 0.01,
    tick_lookback_value: 30,
    tick_lookback_unit: 'minutes',
    bar_size_points: 100,
    max_bars_memory: 500
  };

  var symbolOptions = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD',
    'USDCHF', 'NZDUSD', 'XAUUSD', 'BTCUSD', 'USTEC',
    'SPX500', 'DOW30', 'FTSE100'
  ];

  var tickLookbackUnits = ['minutes', 'hours', 'days'];

  return {
    runtimeDefaults: runtimeDefaults,
    symbolOptions: symbolOptions,
    tickLookbackUnits: tickLookbackUnits
  };
})();

/* modalManager.js */

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

    var confirmClass = type === 'danger' ? 'wd-btn wd-btn-primary' : 'wd-btn wd-btn-primary';
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
          '<button class="' + confirmClass + '" id="modal-confirm"' + confirmStyle + '>' + confirmText + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(_overlay);

    _overlay.querySelector('#modal-close').addEventListener('click', hide);
    _overlay.querySelector('#modal-cancel').addEventListener('click', hide);
    _overlay.querySelector('#modal-confirm').addEventListener('click', function () {
      onConfirm();
      hide();
    });

    _overlay.addEventListener('click', function (e) {
      if (e.target === _overlay) hide();
    });

    var escHandler = function (e) {
      if (e.key === 'Escape') {
        hide();
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  function hide() {
    if (_overlay && _overlay.parentNode) {
      _overlay.parentNode.removeChild(_overlay);
    }
    _overlay = null;
  }

  return {
    show: show,
    hide: hide
  };
})();

/* toastManager.js */

var ToastManager = (function () {
  'use strict';

  var iconMap = {
    success: 'fa-circle-check',
    info: 'fa-circle-info',
    warning: 'fa-triangle-exclamation',
    error: 'fa-circle-xmark'
  };

  function _getContainer() {
    var container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function show(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    var container = _getContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML =
      '<i class="fa-solid ' + (iconMap[type] || iconMap.info) + '"></i>' +
      '<span>' + message + '</span>' +
      '<button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';

    container.appendChild(toast);

    var dismiss = toast.querySelector('.toast-dismiss');
    dismiss.addEventListener('click', function () {
      _remove(toast);
    });

    setTimeout(function () {
      _remove(toast);
    }, duration);
  }

  function _remove(toast) {
    if (!toast || !toast.parentNode) return;

    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';

    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }

  return {
    show: show
  };
})();

/* themeManager.js */

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

    if (typeof DashboardRenderer !== 'undefined' && DashboardRenderer.onThemeChange) {
      DashboardRenderer.onThemeChange();
    }
  }

  function applyTheme() {
    document.body.setAttribute('data-theme', currentTheme);
  }

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

  function getTheme() {
    return currentTheme;
  }

  return {
    init: init,
    toggle: toggle,
    getTheme: getTheme
  };
})();

/* dashboardRenderer.js */

var DashboardRenderer = (function () {
  'use strict';

  var _fleetInterval = null;
  var _kpiInterval = null;
  var _lastFleetWorkers = [];

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">—</span>';

    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '') {
      return '<span class="value-null">' + (fallback || '—') + '</span>';
    }
    return val;
  }

  function kpiCard(icon, label, value, sentiment) {
    var valueClass = '';
    if (sentiment === 'positive') valueClass = ' positive';
    else if (sentiment === 'negative') valueClass = ' negative';

    return '<div class="portfolio-card">' +
      '<div class="card-icon ' + sentiment + '"><i class="fa-solid ' + icon + '"></i></div>' +
      '<div class="card-info"><div class="card-value' + valueClass + '">' + value + '</div>' +
      '<div class="card-label">' + label + '</div></div></div>';
  }

  function fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count +
      '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _fetchKPIs() {
    var el = document.getElementById('dashboard-kpi-content');
    if (!el) return;

    Promise.all([
      ApiClient.getStrategies().catch(function () {
        return { strategies: [] };
      }),
      ApiClient.getDeployments().catch(function () {
        return { deployments: [] };
      }),
      ApiClient.getSystemSummary().catch(function () {
        return {};
      })
    ]).then(function (results) {
      var strats = results[0].strategies || [];
      var deps = results[1].deployments || [];
      var sys = results[2];

      var registeredCount = strats.length;
      var activeDeployments = deps.filter(function (d) {
        return [
          'queued',
          'sent_to_worker',
          'acknowledged_by_worker',
          'loading_strategy',
          'fetching_ticks',
          'generating_initial_bars',
          'warming_up',
          'running'
        ].indexOf(d.state) !== -1;
      }).length;

      var runningCount = deps.filter(function (d) {
        return d.state === 'running';
      }).length;

      var failedCount = deps.filter(function (d) {
        return d.state === 'failed';
      }).length;

      var onlineWorkers = sys.online_nodes || 0;
      var totalWorkers = sys.total_nodes || 0;

      var html = '<div class="portfolio-grid">';
      html += kpiCard('fa-crosshairs', 'Registered Strategies', String(registeredCount), 'neutral');
      html += kpiCard('fa-rocket', 'Active Deployments', String(activeDeployments), activeDeployments > 0 ? 'positive' : 'neutral');
      html += kpiCard('fa-play', 'Running Runners', String(runningCount), runningCount > 0 ? 'positive' : 'neutral');
      html += kpiCard('fa-triangle-exclamation', 'Failed Deployments', String(failedCount), failedCount > 0 ? 'negative' : 'neutral');
      html += kpiCard('fa-server', 'Online Workers', onlineWorkers + ' / ' + totalWorkers, onlineWorkers > 0 ? 'positive' : 'warning');
      html += '</div>';

      el.innerHTML = html;
    });
  }

  function _fetchDashboardFleet() {
    var el = document.getElementById('dashboard-fleet-content');
    if (!el) return;

    ApiClient.getFleetWorkers()
      .then(function (data) {
        var s = data.summary || {};
        var workers = data.workers || [];

        _lastFleetWorkers = workers;

        var html = '<div class="fleet-summary">';
        html += fleetBadge(s.total_workers || 0, 'Total', 'total');
        html += fleetBadge(s.online_workers || 0, 'Online', 'online');
        html += fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
        html += fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
        html += fleetBadge(s.error_workers || 0, 'Error', 'error');
        html += '</div>';

        if (workers.length > 0) {
          html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">';
          html += '<thead><tr><th>Worker</th><th>State</th><th>Host</th><th>Strategy</th><th>Heartbeat</th></tr></thead><tbody>';

          workers.forEach(function (w) {
            var name = w.worker_name || w.worker_id;
            var state = w.state || 'unknown';
            var strats = w.active_strategies && w.active_strategies.length > 0
              ? w.active_strategies.join(', ')
              : '<span class="value-null">—</span>';

            html += '<tr class="clickable" onclick="DashboardRenderer._openWorker(\'' + w.worker_id + '\')">';
            html += '<td class="mono">' + name + '</td>';
            html += '<td><span class="state-pill ' + state + '">' + state.toUpperCase() + '</span></td>';
            html += '<td class="mono">' + _nullVal(w.host) + '</td>';
            html += '<td class="mono">' + strats + '</td>';
            html += '<td class="mono">' + _formatAge(w.heartbeat_age_seconds) + '</td>';
            html += '</tr>';
          });

          html += '</tbody></table></div>';
        } else {
          html += '<div style="padding:16px 0;color:var(--text-muted);font-size:12.5px;">' +
            '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
            'No workers connected yet — start a worker agent to see fleet data.</div>';
        }

        html += '<span class="view-fleet-link" onclick="App.navigateTo(\'fleet\')">' +
          'View Fleet <i class="fa-solid fa-arrow-right"></i></span>';

        el.innerHTML = html;
      })
      .catch(function () {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">' +
          '<i class="fa-solid fa-circle-exclamation" style="margin-right:6px;color:var(--danger);opacity:0.6;"></i>' +
          'Could not load fleet data from backend.</div>';
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

  function _fetchDeployments() {
    var el = document.getElementById('dashboard-deploy-content');
    if (!el) return;

    ApiClient.getDeployments().then(function (data) {
      var deps = data.deployments || [];

      if (deps.length === 0) {
        el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12.5px;">' +
          '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
          'No deployments yet. Deploy a strategy from the Worker Detail page.</div>';
        return;
      }

      deps = deps.slice().reverse();

      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">';
      html += '<thead><tr><th>Deployment</th><th>Strategy</th><th>Worker</th><th>Symbol</th><th>State</th><th>Updated</th></tr></thead><tbody>';

      deps.forEach(function (d) {
        var stateClass = _deployStateClass(d.state);
        var updated = d.updated_at ? d.updated_at.replace('T', ' ').substring(0, 19) : '—';

        html += '<tr>';
        html += '<td class="mono">' + d.deployment_id + '</td>';
        html += '<td class="mono">' + d.strategy_id + '</td>';
        html += '<td class="mono">' + d.worker_id + '</td>';
        html += '<td class="mono">' + d.symbol + '</td>';
        html += '<td><span class="state-pill ' + stateClass + '">' + d.state.toUpperCase().replace(/_/g, ' ') + '</span></td>';
        html += '<td class="mono">' + updated + '</td>';
        html += '</tr>';

        if (d.last_error) {
          html += '<tr><td colspan="6" style="color:var(--danger);font-size:11px;padding:4px 12px;">' +
            '<i class="fa-solid fa-circle-xmark" style="margin-right:4px;"></i>' + d.last_error + '</td></tr>';
        }
      });

      html += '</tbody></table></div>';
      el.innerHTML = html;
    }).catch(function () {
      el.innerHTML = '<div style="padding:16px 0;color:var(--text-muted);font-size:12px;">' +
        '<i class="fa-solid fa-circle-exclamation" style="margin-right:6px;color:var(--danger);opacity:0.6;"></i>' +
        'Could not load deployment data.</div>';
    });
  }

  function _deployStateClass(state) {
    if (!state) return 'unknown';
    if (state === 'running') return 'online';
    if (state === 'failed') return 'error';
    if (state === 'stopped') return 'offline';

    if (
      state.indexOf('loading') !== -1 ||
      state.indexOf('fetching') !== -1 ||
      state.indexOf('generating') !== -1 ||
      state.indexOf('warming') !== -1
    ) {
      return 'warning';
    }

    if (
      state === 'queued' ||
      state.indexOf('sent') !== -1 ||
      state.indexOf('acknowledged') !== -1
    ) {
      return 'stale';
    }

    return 'unknown';
  }

  function render() {
    var html = '<div class="dashboard">';

    html += '<section><div class="section-header"><i class="fa-solid fa-gauge-high"></i><h2>System KPIs</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-kpi-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading…</p></div></div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Overview</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-fleet-content" class="dashboard-fleet-section">';
    html += '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading fleet data…</p></div>';
    html += '</div></section>';

    html += '<section><div class="section-header"><i class="fa-solid fa-rocket"></i><h2>Recent Deployments</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-deploy-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading…</p></div></div></section>';

    html += '</div>';

    document.getElementById('main-content').innerHTML = html;

    _fetchKPIs();
    _fetchDashboardFleet();
    _fetchDeployments();

    _fleetInterval = setInterval(function () {
      _fetchDashboardFleet();
      _fetchDeployments();
    }, 10000);

    _kpiInterval = setInterval(_fetchKPIs, 15000);
  }

  function destroy() {
    if (_fleetInterval) {
      clearInterval(_fleetInterval);
      _fleetInterval = null;
    }

    if (_kpiInterval) {
      clearInterval(_kpiInterval);
      _kpiInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _openWorker: _openWorker
  };
})();

/* fleetRenderer.js */

var FleetRenderer = (function () {
  'use strict';

  var _refreshInterval = null;
  var _lastFetchTime = null;
  var _lastWorkers = [];
  var REFRESH_MS = 5000;

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">—</span>';

    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '') {
      return '<span class="value-null">' + (fallback || '—') + '</span>';
    }
    return String(val);
  }

  function _formatPnl(val) {
    if (val === null || val === undefined) return '<span class="value-null">—</span>';

    var sign = val >= 0 ? '+' : '';
    return sign + '$' + val.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function _stateLabel(state) {
    if (!state) return 'Unknown';
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  function fleetBadge(count, label, type) {
    return '<div class="fleet-badge"><span class="badge-count ' + type + '">' + count +
      '</span><span class="badge-label">' + label + '</span></div>';
  }

  function _infoRow(label, value) {
    return '<div class="node-info-row"><span class="node-info-label">' + label +
      '</span><span class="node-info-value">' + value + '</span></div>';
  }

  function renderNodeCard(w) {
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;

    var strategies = w.active_strategies && w.active_strategies.length > 0
      ? w.active_strategies.join(', ')
      : null;

    var errorsStr = w.errors && w.errors.length > 0
      ? w.errors.join(', ')
      : null;

    var pnlVal = _formatPnl(w.floating_pnl);
    var pnlClass = '';

    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlClass = w.floating_pnl >= 0
        ? ' style="color:var(--success)"'
        : ' style="color:var(--danger)"';
    }

    return (
      '<div class="node-card clickable" onclick="FleetRenderer._openWorker(\'' + w.worker_id + '\')">' +
        '<div class="node-card-top ' + state + '"></div>' +
        '<div class="node-card-header">' +
          '<div class="node-name-group">' +
            '<span class="node-status-dot ' + state + '"></span>' +
            '<span class="node-name">' + name + '</span>' +
          '</div>' +
          '<span class="node-status-badge ' + state + '">' + _stateLabel(state) + '</span>' +
        '</div>' +
        '<div class="node-card-body">' +
          _infoRow('Worker ID', '<span class="mono">' + w.worker_id + '</span>') +
          _infoRow('Host', _nullVal(w.host)) +
          _infoRow('MT5', _nullVal(w.mt5_state, 'Unknown')) +
          _infoRow('Broker', _nullVal(w.broker)) +
          _infoRow('Account', _nullVal(w.account_id)) +
          _infoRow('Strategies', _nullVal(strategies, 'No active strategy')) +
          _infoRow('Positions', String(w.open_positions_count || 0)) +
          _infoRow('Float PnL', '<span' + pnlClass + '>' + pnlVal + '</span>') +
          _infoRow('Heartbeat', _formatAge(w.heartbeat_age_seconds)) +
          _infoRow('Agent', _nullVal(w.agent_version)) +
          _infoRow('Errors', _nullVal(errorsStr, 'None')) +
          '<div class="node-card-action"><i class="fa-solid fa-arrow-right"></i> View / Deploy Strategy</div>' +
        '</div>' +
      '</div>'
    );
  }

  function _renderContent(data) {
    var headerEl = document.getElementById('fleet-page-header');
    var contentEl = document.getElementById('fleet-content');
    if (!contentEl) return;

    var workers = data.workers || [];
    var s = data.summary || {};

    _lastWorkers = workers;

    if (headerEl) {
      _lastFetchTime = new Date();

      var timeStr = _lastFetchTime.toLocaleTimeString('en-GB', {
        hour12: false
      });

      headerEl.style.display = 'flex';

      var metaEl = headerEl.querySelector('.last-synced');
      if (metaEl) metaEl.textContent = 'Synced: ' + timeStr;
    }

    if (workers.length === 0) {
      contentEl.innerHTML =
        '<div class="empty-state">' +
          '<i class="fa-solid fa-server"></i>' +
          '<h3>No Worker VMs Connected</h3>' +
          '<p>Start a worker agent and send heartbeat to this Mother Server to see workers here.</p>' +
          '<p>Endpoint: <code>POST /api/grid/workers/heartbeat</code></p>' +
        '</div>';
      return;
    }

    var html = '';
    html += '<div class="fleet-summary">';
    html += fleetBadge(s.total_workers || 0, 'Total', 'total');
    html += fleetBadge(s.online_workers || 0, 'Online', 'online');
    html += fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
    html += fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
    html += fleetBadge(s.error_workers || 0, 'Error', 'error');
    html += '</div>';

    html += '<div class="fleet-grid">';
    workers.forEach(function (w) {
      html += renderNodeCard(w);
    });
    html += '</div>';

    contentEl.innerHTML = html;
  }

  function _renderError() {
    var contentEl = document.getElementById('fleet-content');
    if (!contentEl) return;

    contentEl.innerHTML =
      '<div class="error-state">' +
        '<i class="fa-solid fa-triangle-exclamation"></i>' +
        '<h3>Failed to Load Fleet Data</h3>' +
        '<p>Could not connect to the Mother Server API. Check that the backend is running.</p>' +
        '<button class="retry-btn" onclick="FleetRenderer._retry()">Retry</button>' +
      '</div>';
  }

  function _fetchFleetData() {
    ApiClient.getFleetWorkers().then(_renderContent).catch(_renderError);
  }

  function _openWorker(workerId) {
    for (var i = 0; i < _lastWorkers.length; i++) {
      if (_lastWorkers[i].worker_id === workerId) {
        App.navigateToWorkerDetail(_lastWorkers[i]);
        return;
      }
    }
  }

  function render() {
    var html =
      '<div class="fleet-page">' +
        '<div class="fleet-page-header" id="fleet-page-header" style="display:none;">' +
          '<span class="fleet-page-title"><i class="fa-solid fa-server" style="color:var(--accent);margin-right:8px;"></i>Fleet Management</span>' +
          '<div class="fleet-page-meta">' +
            '<div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Auto-refresh</div>' +
            '<span class="last-synced">Synced: --:--:--</span>' +
          '</div>' +
        '</div>' +
        '<div id="fleet-content">' +
          '<div class="loading-state"><div class="spinner"></div><p>Loading fleet data…</p></div>' +
        '</div>' +
      '</div>';

    document.getElementById('main-content').innerHTML = html;

    _fetchFleetData();
    _refreshInterval = setInterval(_fetchFleetData, REFRESH_MS);
  }

  function destroy() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval);
      _refreshInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _retry: _fetchFleetData,
    _openWorker: _openWorker
  };
})();

/* strategiesRenderer.js */

var StrategiesRenderer = (function () {
  'use strict';

  var _refreshInterval = null;

  function render() {
    var html =
      '<div class="fleet-page">' +
        '<div class="fleet-page-header">' +
          '<span class="fleet-page-title"><i class="fa-solid fa-crosshairs" style="color:var(--accent);margin-right:8px;"></i>Strategy Registry</span>' +
          '<div class="fleet-page-meta">' +
            '<button class="wd-refresh-btn" id="strat-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button>' +
          '</div>' +
        '</div>' +

        '<div class="wd-panel">' +
          '<div class="wd-panel-header">Upload Strategy<span class="panel-badge">REGISTER</span></div>' +
          '<div class="wd-panel-body">' +
            '<div class="wd-file-upload" id="strat-upload-area">' +
              '<input type="file" id="strat-file-input" accept=".py" style="display:none" />' +
              '<i class="fa-solid fa-file-code"></i>' +
              '<h4>Upload Strategy File</h4>' +
              '<p>.py files extending BaseStrategy</p>' +
              '<div id="strat-upload-status"></div>' +
            '</div>' +
          '</div>' +
        '</div>' +

        '<div id="strat-list-content">' +
          '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading strategies…</p></div>' +
        '</div>' +
      '</div>';

    document.getElementById('main-content').innerHTML = html;

    _attachEvents();
    _fetch();

    _refreshInterval = setInterval(_fetch, 10000);
  }

  function _attachEvents() {
    document.getElementById('strat-refresh').addEventListener('click', _fetch);

    var area = document.getElementById('strat-upload-area');
    var input = document.getElementById('strat-file-input');

    area.addEventListener('click', function () {
      input.click();
    });

    input.addEventListener('change', function () {
      if (!input.files || !input.files[0]) return;

      var file = input.files[0];

      if (!file.name.endsWith('.py')) {
        ToastManager.show('Only .py files accepted.', 'error');
        return;
      }

      _upload(file);
    });
  }

  function _upload(file) {
    var el = document.getElementById('strat-upload-status');

    el.innerHTML =
      '<div class="wd-file-status" style="color:var(--accent);">' +
      '<i class="fa-solid fa-spinner fa-spin"></i> Uploading &amp; validating…</div>';

    ApiClient.uploadStrategy(file).then(function (data) {
      el.innerHTML =
        '<div class="wd-file-status" style="color:var(--success);">' +
        '<i class="fa-solid fa-circle-check"></i> Registered: ' +
        (data.strategy_name || data.strategy_id) +
        '</div>';

      ToastManager.show('Strategy registered: ' + (data.strategy_name || data.strategy_id), 'success');
      _fetch();
    }).catch(function (err) {
      el.innerHTML =
        '<div class="wd-file-status" style="color:var(--danger);">' +
        '<i class="fa-solid fa-circle-xmark"></i> ' +
        err.message +
        '</div>';

      ToastManager.show('Upload failed: ' + err.message, 'error');
    });
  }

  function _fetch() {
    var el = document.getElementById('strat-list-content');
    if (!el) return;

    ApiClient.getStrategies().then(function (data) {
      var list = data.strategies || [];

      if (list.length === 0) {
        el.innerHTML =
          '<div class="empty-state" style="min-height:200px;">' +
            '<i class="fa-solid fa-crosshairs"></i>' +
            '<h3>No Strategies Registered</h3>' +
            '<p>Upload a .py strategy file extending BaseStrategy to get started.</p>' +
          '</div>';
        return;
      }

      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">' +
        '<thead><tr><th>Strategy ID</th><th>Name</th><th>Version</th><th>Params</th><th>Status</th><th>Uploaded</th></tr></thead><tbody>';

      list.forEach(function (s) {
        var statusClass = s.validation_status === 'validated' ? 'online' : 'error';
        var statusLabel = s.validation_status === 'validated'
          ? 'Validated'
          : (s.validation_status || 'Unknown');

        var uploaded = s.uploaded_at
          ? s.uploaded_at.replace('T', ' ').substring(0, 19)
          : '—';

        html += '<tr>' +
          '<td class="mono">' + s.strategy_id + '</td>' +
          '<td>' + (s.strategy_name || s.strategy_id) + '</td>' +
          '<td class="mono">' + (s.version || '—') + '</td>' +
          '<td class="mono">' + (s.parameter_count || 0) + '</td>' +
          '<td><span class="state-pill ' + statusClass + '">' + statusLabel.toUpperCase() + '</span></td>' +
          '<td class="mono">' + uploaded + '</td>' +
          '</tr>';
      });

      html += '</tbody></table></div>';

      list.forEach(function (s) {
        if (s.description || s.error) {
          html += '<div style="margin-top:8px;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;font-size:11.5px;">';
          html += '<strong class="mono" style="color:var(--accent);">' + s.strategy_id + '</strong>';

          if (s.description) {
            html += '<span style="color:var(--text-secondary);margin-left:8px;">' + s.description + '</span>';
          }

          if (s.error) {
            html += '<span style="color:var(--danger);margin-left:8px;">Error: ' + s.error + '</span>';
          }

          html += '</div>';
        }
      });

      el.innerHTML = html;
    }).catch(function (err) {
      el.innerHTML =
        '<div class="error-state" style="min-height:200px;">' +
          '<i class="fa-solid fa-triangle-exclamation"></i>' +
          '<h3>Failed to Load Strategies</h3>' +
          '<p>' + err.message + '</p>' +
          '<button class="retry-btn" onclick="StrategiesRenderer._retry()">Retry</button>' +
        '</div>';
    });
  }

  function destroy() {
    if (_refreshInterval) {
      clearInterval(_refreshInterval);
      _refreshInterval = null;
    }
  }

  return {
    render: render,
    destroy: destroy,
    _retry: _fetch
  };
})();

/* app.js */

var App = (function () {
  'use strict';

  var currentPage = 'dashboard';
  var _selectedWorker = null;

  var pageIcons = {
    dashboard: 'fa-grip',
    fleet: 'fa-server',
    portfolio: 'fa-chart-line',
    strategies: 'fa-crosshairs',
    logs: 'fa-scroll',
    settings: 'fa-gear'
  };

  var pageDescriptions = {
    portfolio: 'Portfolio analytics will be available when trade execution is implemented.',
    logs: 'Centralized log aggregation, real-time streaming, and advanced search across all fleet nodes.',
    settings: 'System configuration, user preferences, notification settings, and connection management.'
  };

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
    if (currentPage === 'dashboard') DashboardRenderer.destroy();
    if (currentPage === 'fleet') FleetRenderer.destroy();
    if (currentPage === 'workerDetail') WorkerDetailRenderer.destroy();
    if (currentPage === 'strategies') StrategiesRenderer.destroy();

    currentPage = page;

    var navPage = page === 'workerDetail' ? 'fleet' : page;

    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.classList.toggle('active', item.getAttribute('data-page') === navPage);
    });

    var titleMap = {
      workerDetail: 'Worker Detail'
    };

    var title = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));
    document.getElementById('topbar-title').textContent = title;

    if (page === 'dashboard') {
      DashboardRenderer.render();
    } else if (page === 'fleet') {
      FleetRenderer.render();
    } else if (page === 'workerDetail' && _selectedWorker) {
      WorkerDetailRenderer.render(_selectedWorker);
    } else if (page === 'strategies') {
      StrategiesRenderer.render();
    } else {
      renderPlaceholder(page);
    }
  }

  function navigateToWorkerDetail(workerData) {
    _selectedWorker = workerData;
    navigateTo('workerDetail');
  }

  function renderPlaceholder(page) {
    var icon = pageIcons[page] || 'fa-circle-question';
    var title = page.charAt(0).toUpperCase() + page.slice(1);
    var desc = pageDescriptions[page] || 'This section is under development.';

    document.getElementById('main-content').innerHTML =
      '<div class="placeholder-page"><i class="fa-solid ' + icon + '"></i>' +
      '<h2>' + title + '</h2><p>' + desc + '</p></div>';
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