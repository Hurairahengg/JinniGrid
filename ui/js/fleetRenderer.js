var FleetRenderer = (function () {
  'use strict';

  var _refreshInterval = null;
  var _lastFetchTime = null;
  var REFRESH_MS = 5000;

  /* ── Helpers ──────────────────────────────────────────────── */

  function _formatAge(seconds) {
    if (seconds === null || seconds === undefined) return '<span class="value-null">\u2014</span>';
    var s = Math.round(seconds);
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm ago';
  }

  function _nullVal(val, fallback) {
    if (val === null || val === undefined || val === '') {
      return '<span class="value-null">' + (fallback || '\u2014') + '</span>';
    }
    return String(val);
  }

  function _formatPnl(val) {
    if (val === null || val === undefined) return '<span class="value-null">\u2014</span>';
    var sign = val >= 0 ? '+' : '';
    return sign + '$' + val.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function _stateLabel(state) {
    if (!state) return 'Unknown';
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  function fleetBadge(count, label, type) {
    return '<div class="fleet-badge">' +
      '<span class="badge-count ' + type + '">' + count + '</span>' +
      '<span class="badge-label">' + label + '</span></div>';
  }

  function _infoRow(label, value) {
    return '<div class="node-info-row">' +
      '<span class="node-info-label">' + label + '</span>' +
      '<span class="node-info-value">' + value + '</span></div>';
  }

  /* ── Node Card ───────────────────────────────────────────── */

  function renderNodeCard(w) {
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;
    var strategies = (w.active_strategies && w.active_strategies.length > 0)
      ? w.active_strategies.join(', ') : null;
    var errorsStr = (w.errors && w.errors.length > 0)
      ? w.errors.join(', ') : null;
    var pnlClass = '';
    var pnlVal = _formatPnl(w.floating_pnl);
    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlClass = w.floating_pnl >= 0 ? ' style="color:var(--success)"' : ' style="color:var(--danger)"';
    }

    return (
      '<div class="node-card">' +
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
          _infoRow('Strategies', _nullVal(strategies)) +
          _infoRow('Positions', String(w.open_positions_count || 0)) +
          _infoRow('Float PnL', '<span' + pnlClass + '>' + pnlVal + '</span>') +
          _infoRow('Heartbeat', _formatAge(w.heartbeat_age_seconds)) +
          _infoRow('Agent', _nullVal(w.agent_version)) +
          _infoRow('Errors', _nullVal(errorsStr, 'None')) +
        '</div>' +
      '</div>'
    );
  }

  /* ── Render States ───────────────────────────────────────── */

  function _renderContent(data) {
    var headerEl = document.getElementById('fleet-page-header');
    var contentEl = document.getElementById('fleet-content');
    if (!contentEl) return;

    var workers = data.workers || [];
    var s = data.summary || {};

    // Show header
    if (headerEl) {
      _lastFetchTime = new Date();
      var timeStr = _lastFetchTime.toLocaleTimeString('en-GB', { hour12: false });
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
          '<p>Endpoint: <code>POST /api/Grid/workers/heartbeat</code></p>' +
        '</div>';
      return;
    }

    var html = '';

    // Summary badges
    html += '<div class="fleet-summary">';
    html += fleetBadge(s.total_workers || 0, 'Total', 'total');
    html += fleetBadge(s.online_workers || 0, 'Online', 'online');
    html += fleetBadge(s.stale_workers || 0, 'Stale', 'stale');
    html += fleetBadge(s.offline_workers || 0, 'Offline', 'offline');
    html += fleetBadge(s.error_workers || 0, 'Error', 'error');
    html += '</div>';

    // Fleet Grid
    html += '<div class="fleet-Grid">';
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

  /* ── Fetch ───────────────────────────────────────────────── */

  function _fetchFleetData() {
    ApiClient.getFleetWorkers()
      .then(_renderContent)
      .catch(_renderError);
  }

  /* ── Public ──────────────────────────────────────────────── */

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
          '<div class="loading-state"><div class="spinner"></div><p>Loading fleet data...</p></div>' +
        '</div>' +
      '</div>';

    document.getElementById('main-content').innerHTML = html;
    _fetchFleetData();
    _refreshInterval = setInterval(_fetchFleetData, REFRESH_MS);
  }

  function destroy() {
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
  }

  return { render: render, destroy: destroy, _retry: _fetchFleetData };
})();
