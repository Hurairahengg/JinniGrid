/* dashboardRenderer.js */

var DashboardRenderer = (function () {
  'use strict';

  var _fleetInterval = null;
  var _kpiInterval = null;
  var _lastFleetWorkers = [];

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">\u2014</span>';
    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '')
      return '<span class="value-null">' + (fallback || '\u2014') + '</span>';
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

  /* ── KPI fetch ────────────────────────────────────────────── */

  function _fetchKPIs() {
    var el = document.getElementById('dashboard-kpi-content');
    if (!el) return;

    // Fetch strategies, deployments, and system summary in parallel
    Promise.all([
      ApiClient.getStrategies().catch(function () { return { strategies: [] }; }),
      ApiClient.getDeployments().catch(function () { return { deployments: [] }; }),
      ApiClient.getSystemSummary().catch(function () { return {}; }),
    ]).then(function (results) {
      var strats = results[0].strategies || [];
      var deps = results[1].deployments || [];
      var sys = results[2];

      var registeredCount = strats.length;
      var activeDeployments = deps.filter(function (d) {
        return ['queued','sent_to_worker','acknowledged_by_worker','loading_strategy',
                'fetching_ticks','generating_initial_bars','warming_up','running'].indexOf(d.state) !== -1;
      }).length;
      var runningCount = deps.filter(function (d) { return d.state === 'running'; }).length;
      var failedCount = deps.filter(function (d) { return d.state === 'failed'; }).length;
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

  /* ── Fleet fetch ──────────────────────────────────────────── */

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
            var strats = (w.active_strategies && w.active_strategies.length > 0) ? w.active_strategies.join(', ') : '<span class="value-null">\u2014</span>';
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
            'No workers connected yet \u2014 start a worker agent to see fleet data.</div>';
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

  /* ── Deployments table ────────────────────────────────────── */

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

      // Show most recent first
      deps = deps.slice().reverse();

      var html = '<div class="compact-fleet-wrapper"><table class="compact-fleet-table">';
      html += '<thead><tr><th>Deployment</th><th>Strategy</th><th>Worker</th><th>Symbol</th><th>State</th><th>Updated</th></tr></thead><tbody>';

      deps.forEach(function (d) {
        var stateClass = _deployStateClass(d.state);
        var updated = d.updated_at ? d.updated_at.replace('T', ' ').substring(0, 19) : '\u2014';
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
    if (state.indexOf('loading') !== -1 || state.indexOf('fetching') !== -1 ||
        state.indexOf('generating') !== -1 || state.indexOf('warming') !== -1) return 'warning';
    if (state === 'queued' || state.indexOf('sent') !== -1 || state.indexOf('acknowledged') !== -1) return 'stale';
    return 'unknown';
  }

  /* ── Render ───────────────────────────────────────────────── */

  function render() {
    var html = '<div class="dashboard">';

    // KPIs
    html += '<section><div class="section-header"><i class="fa-solid fa-gauge-high"></i><h2>System KPIs</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-kpi-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading\u2026</p></div></div></section>';

    // Fleet
    html += '<section><div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Overview</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-fleet-content" class="dashboard-fleet-section">';
    html += '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading fleet data\u2026</p></div>';
    html += '</div></section>';

    // Deployments
    html += '<section><div class="section-header"><i class="fa-solid fa-rocket"></i><h2>Recent Deployments</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-deploy-content"><div class="loading-state" style="min-height:80px;"><div class="spinner"></div><p>Loading\u2026</p></div></div></section>';

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
    if (_fleetInterval) { clearInterval(_fleetInterval); _fleetInterval = null; }
    if (_kpiInterval) { clearInterval(_kpiInterval); _kpiInterval = null; }
  }

  return { render: render, destroy: destroy, _openWorker: _openWorker };
})();