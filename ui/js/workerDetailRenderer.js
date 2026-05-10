/* workerDetailRenderer.js */

var WorkerDetailRenderer = (function () {
  'use strict';

  var _currentWorker = null;
  var _refreshInterval = null;
  var _runtimeConfig = {};
  var _parameterValues = {};
  var _parameterDefaults = {};
  var _activityLog = [];

  // Backend-loaded data
  var _strategies = [];
  var _selectedStrategyId = null;
  var _selectedStrategy = null;
  var _deployments = [];

  /* ── Helpers ──────────────────────────────────────────────── */

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
    return String(val);
  }

  function _stateColor(state) {
    var map = { online: 'green', running: 'green', idle: 'blue', warning: 'amber', stale: 'orange', error: 'red', offline: 'gray' };
    return map[state] || 'gray';
  }

  function _stateLabel(state) {
    if (!state) return 'Unknown';
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

  function _formatPnl(val) {
    if (val === null || val === undefined) return '<span class="value-null">\u2014</span>';
    var sign = val >= 0 ? '+' : '';
    return sign + '$' + val.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function _timeNow() {
    var d = new Date();
    return String(d.getHours()).padStart(2, '0') + ':' +
           String(d.getMinutes()).padStart(2, '0') + ':' +
           String(d.getSeconds()).padStart(2, '0');
  }

  function _getModifiedCount() {
    var count = 0;
    for (var k in _parameterValues) {
      if (_parameterValues[k] !== _parameterDefaults[k]) count++;
    }
    return count;
  }

  function _deployStateClass(state) {
    if (!state) return 'unknown';
    if (state === 'running') return 'online';
    if (state === 'failed') return 'error';
    if (state === 'stopped') return 'offline';
    if (state.indexOf('loading') !== -1 || state.indexOf('fetching') !== -1 ||
        state.indexOf('generating') !== -1 || state.indexOf('warming') !== -1) return 'warning';
    return 'stale';
  }

  /* ── State Init ──────────────────────────────────────────── */

  function _initState() {
    _activityLog = [];
    _strategies = [];
    _selectedStrategyId = null;
    _selectedStrategy = null;
    _deployments = [];

    var defaults = DeploymentConfig.runtimeDefaults;
    _runtimeConfig = {};
    for (var k in defaults) _runtimeConfig[k] = defaults[k];

    _parameterValues = {};
    _parameterDefaults = {};
  }

  /* ── Activity Log ────────────────────────────────────────── */

  function _addActivity(text) {
    _activityLog.unshift({ time: _timeNow(), text: text });
    if (_activityLog.length > 30) _activityLog.length = 30;
    _renderTimeline();
  }

  function _renderTimeline() {
    var el = document.getElementById('wd-timeline');
    if (!el) return;
    if (_activityLog.length === 0) {
      el.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">No activity yet.</div>';
      return;
    }
    var html = '';
    _activityLog.forEach(function (entry) {
      html += '<div class="wd-timeline-item">' +
        '<span class="wd-timeline-time">' + entry.time + '</span>' +
        '<span class="wd-timeline-dot"></span>' +
        '<span class="wd-timeline-text">' + entry.text + '</span></div>';
    });
    el.innerHTML = html;
  }

  /* ── Status Cards ────────────────────────────────────────── */

  function _renderStatusCards() {
    var w = _currentWorker;
    var state = w.state || 'unknown';
    var strats = (w.active_strategies && w.active_strategies.length > 0)
      ? w.active_strategies.join(', ') : 'None';

    /* ── MT5 info ────────────────────────────────────── */
    var mt5Val = _nullVal(w.mt5_state, 'Not Connected');
    var mt5Color = '';
    if (w.mt5_state === 'connected') {
      mt5Val = '<span style="color:var(--success);">Connected</span>';
    } else if (w.mt5_state === 'disconnected') {
      mt5Val = '<span style="color:var(--danger);">Disconnected</span>';
    }

    var brokerAcct = '';
    if (w.broker || w.account_id) {
      brokerAcct = (w.broker || '?') + ' / ' + (w.account_id || '?');
    } else {
      brokerAcct = '<span class="value-null">\u2014</span>';
    }

    /* ── Pipeline stats ──────────────────────────────── */
    var ticks = w.total_ticks || 0;
    var bars = w.total_bars || 0;
    var signals = w.signal_count || 0;
    var onBarCalls = w.on_bar_calls || 0;

    var barsInMem = w.current_bars_in_memory || 0;
    var barsText = _fmtNum(bars) + ' gen\u2019d' + (barsInMem > 0 ? ' (' + barsInMem + ' mem)' : '');
    var pipelineVal =
      '<span style="color:var(--accent);">' + _fmtNum(ticks) + '</span> ticks \u2192 ' +
      '<span style="color:var(--warning);">' + barsText + '</span> bars \u2192 ' +
      '<span style="color:var(--success);">' + signals + '</span> signals';

    /* ── Current price ───────────────────────────────── */
    var priceVal = (w.current_price !== null && w.current_price !== undefined)
      ? '<span class="mono">' + w.current_price.toFixed(2) + '</span>'
      : '<span class="value-null">\u2014</span>';

    /* ── PnL ─────────────────────────────────────────── */
    var pnl = _formatPnl(w.floating_pnl);
    var pnlStyle = '';
    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlStyle = w.floating_pnl >= 0 ? 'color:var(--success)' : 'color:var(--danger)';
    }

    var cards = [
      { label: 'Connection',       value: '<div class="status-indicator"><span class="wd-status-dot-sm ' + _stateColor(state) + '"></span>' + _stateLabel(state) + '</div>' },
      { label: 'MT5',              value: mt5Val },
      { label: 'Broker / Account', value: brokerAcct },
      { label: 'Active Strategy',  value: strats },
      { label: 'Pipeline',         value: pipelineVal },
      { label: 'Current Price',    value: priceVal },
      { label: 'Equity',           value: '<span style="' + pnlStyle + '">' + pnl + '</span>' },
      { label: 'Last Heartbeat',   value: _formatAge(w.heartbeat_age_seconds) },
    ];

    var html = '';
    cards.forEach(function (c) {
      html += '<div class="wd-status-card"><span class="status-label">' + c.label + '</span><span class="status-value">' + c.value + '</span></div>';
    });
    return html;
  }

  function _fmtNum(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  /* ── Checklist ───────────────────────────────────────────── */

  function _renderChecklist() {
    var w = _currentWorker;
    var onlineStates = ['online', 'running', 'idle'];
    var isOnline = onlineStates.indexOf(w.state) !== -1;
    var hasSid = !!_selectedStrategyId;
    var hasSym = !!_runtimeConfig.symbol && /^[A-Z0-9._]{1,30}$/.test((_runtimeConfig.symbol || '').trim().toUpperCase());
    var tlOk = _runtimeConfig.tick_lookback_value > 0;
    var bsOk = _runtimeConfig.bar_size_points > 0;
    var mbOk = _runtimeConfig.max_bars_memory > 0;

    var items = [
      { pass: isOnline, text: 'Worker connected', type: isOnline ? 'pass' : 'fail' },
      { pass: hasSid, text: 'Strategy selected' + (hasSid ? ' (' + _selectedStrategyId + ')' : ''), type: hasSid ? 'pass' : 'fail' },
      { pass: hasSym, text: 'Symbol selected', type: hasSym ? 'pass' : 'fail' },
      { pass: tlOk, text: 'Tick lookback configured', type: tlOk ? 'pass' : 'fail' },
      { pass: bsOk, text: 'Bar size points configured', type: bsOk ? 'pass' : 'fail' },
      { pass: mbOk, text: 'Max bars memory configured', type: mbOk ? 'pass' : 'fail' },
      { pass: true, text: 'Parameters configured', type: 'pass' },
    ];

    var iconMap = { pass: 'fa-check', fail: 'fa-xmark', warn: 'fa-exclamation', info: 'fa-info' };
    var html = '';
    items.forEach(function (item) {
      var textClass = item.type === 'pass' ? 'wd-check-text pass' : 'wd-check-text';
      html += '<div class="wd-check-item">' +
        '<span class="wd-check-icon ' + item.type + '"><i class="fa-solid ' + iconMap[item.type] + '"></i></span>' +
        '<span class="' + textClass + '">' + item.text + '</span></div>';
    });
    return html;
  }

  function _updateChecklist() {
    var el = document.getElementById('wd-checklist');
    if (el) el.innerHTML = _renderChecklist();
  }

  /* ── Build Strategy Selector ─────────────────────────────── */

  function _renderStrategySelector() {
    if (_strategies.length === 0) {
      return '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">' +
        '<i class="fa-solid fa-circle-info" style="margin-right:6px;opacity:0.5;"></i>' +
        'No strategies registered. Go to Strategies page to upload one.</div>';
    }

    var html = '<div class="wd-form-grid" style="grid-template-columns:1fr;">' +
      '<div class="wd-form-group"><label class="wd-form-label">Select Strategy</label>' +
      '<select class="wd-form-select" id="wd-strategy-select">';
    html += '<option value="">-- Choose a strategy --</option>';
    _strategies.forEach(function (s) {
      var disabled = s.validation_status !== 'validated' ? ' disabled' : '';
      var label = (s.strategy_name || s.strategy_id) + ' v' + (s.version || '?');
      if (s.validation_status !== 'validated') label += ' (invalid)';
      var selected = (_selectedStrategyId === s.strategy_id) ? ' selected' : '';
      html += '<option value="' + s.strategy_id + '"' + disabled + selected + '>' + label + '</option>';
    });
    html += '</select></div></div>';

    // Metadata preview
    html += '<div id="wd-strat-meta"></div>';
    return html;
  }

  function _renderStrategyMeta() {
    var el = document.getElementById('wd-strat-meta');
    if (!el) return;
    if (!_selectedStrategy) { el.innerHTML = ''; return; }

    var s = _selectedStrategy;
    el.innerHTML = '<div class="wd-metadata" style="margin-top:12px;"><div class="wd-metadata-grid">' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">ID</span><span class="wd-metadata-value">' + s.strategy_id + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Name</span><span class="wd-metadata-value">' + (s.strategy_name || s.strategy_id) + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Version</span><span class="wd-metadata-value">' + (s.version || '\u2014') + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Parameters</span><span class="wd-metadata-value">' + (s.parameter_count || 0) + '</span></div>' +
      (s.description ? '<div class="wd-metadata-item" style="grid-column:1/-1;"><span class="wd-metadata-label">Description</span><span class="wd-metadata-value" style="font-family:Inter,sans-serif;">' + s.description + '</span></div>' : '') +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Status</span><span class="wd-metadata-value" style="color:var(--success);">' + (s.validation_status || 'unknown') + '</span></div>' +
      '</div></div>';
  }

  /* ── Build Strategy Parameters ───────────────────────────── */

  function _renderParams() {
    if (!_selectedStrategy || !_selectedStrategy.parameters ||
        Object.keys(_selectedStrategy.parameters).length === 0) {
      return '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">' +
        'No editable parameters exposed by this strategy.</div>';
    }

    var schema = _selectedStrategy.parameters;
    var html = '';

    Object.keys(schema).forEach(function (key) {
      var spec = schema[key];
      if (typeof spec !== 'object') return;

      var ptype = spec.type || 'number';
      var label = spec.label || key;
      var desc = spec.help || '';
      var defVal = spec.default !== undefined ? spec.default : '';
      var val = _parameterValues.hasOwnProperty(key) ? _parameterValues[key] : defVal;
      var isModified = val !== defVal;
      var modClass = isModified ? ' modified' : '';
      var typeBadge = ptype === 'boolean' ? 'bool' : (ptype === 'number' ? (String(defVal).indexOf('.') !== -1 ? 'float' : 'int') : 'string');
      var input = '';

      if (ptype === 'boolean') {
        input = '<input type="checkbox" class="wd-toggle wd-param-input-ctrl" data-key="' + key + '"' +
          (val ? ' checked' : '') + ' />';
      } else if (ptype === 'select' && spec.options) {
        input = '<select class="wd-param-input wd-param-input-ctrl" data-key="' + key + '" style="width:120px;text-align:left;">';
        spec.options.forEach(function (opt) {
          var optVal = typeof opt === 'object' ? opt.value : opt;
          var optLabel = typeof opt === 'object' ? (opt.label || opt.value) : opt;
          input += '<option value="' + optVal + '"' + (String(optVal) === String(val) ? ' selected' : '') + '>' + optLabel + '</option>';
        });
        input += '</select>';
      } else if (ptype === 'string' || ptype === 'text') {
        input = '<input type="text" class="wd-param-input wd-param-input-ctrl" data-key="' + key + '" value="' + (val || '') + '" style="width:120px;text-align:left;" />';
      } else {
        var attrs = 'type="number" class="wd-param-input wd-param-input-ctrl" data-key="' + key + '" value="' + val + '"';
        if (spec.min !== undefined && spec.min !== null) attrs += ' min="' + spec.min + '"';
        if (spec.max !== undefined && spec.max !== null) attrs += ' max="' + spec.max + '"';
        if (spec.step !== undefined && spec.step !== null) attrs += ' step="' + spec.step + '"';
        input = '<input ' + attrs + ' />';
      }

      html += '<div class="wd-param-row' + modClass + '" data-key="' + key + '">' +
        '<div class="wd-param-info">' +
          '<div class="wd-param-name">' + label +
            '<span class="wd-param-type-badge type-' + typeBadge + '">' + typeBadge + '</span></div>' +
          '<div class="wd-param-desc">' + desc + '</div>' +
        '</div>' +
        '<div class="wd-param-controls">' +
          input +
          '<button class="wd-param-reset" data-key="' + key + '" title="Reset to default"><i class="fa-solid fa-rotate-left"></i></button>' +
        '</div></div>';
    });

    return html;
  }

  /* ── Build Runtime Config ────────────────────────────────── */

  function _renderRuntimeConfig() {
    var rc = _runtimeConfig;
    var tlUnits = DeploymentConfig.tickLookbackUnits;

    var tlUnitOpts = tlUnits.map(function (u) {
      var label = u.charAt(0).toUpperCase() + u.slice(1);
      return '<option value="' + u + '"' + (rc.tick_lookback_unit === u ? ' selected' : '') + '>' + label + '</option>';
    }).join('');

    return '<div class="wd-form-grid">' +

      /* ── Symbol (free-text input) ─────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Symbol</label>' +
        '<input type="text" class="wd-form-input rc-input" id="wd-symbol-input" data-key="symbol"' +
          ' value="' + (rc.symbol || '') + '" placeholder="e.g. EURUSD, XAUUSD, BTCUSD"' +
          ' autocomplete="off" spellcheck="false" />' +
        '<div class="wd-symbol-hint">Letters, numbers, dots, underscores only — auto-uppercased</div>' +
        '<div class="wd-field-error" id="wd-symbol-error"><i class="fa-solid fa-circle-xmark"></i><span></span></div>' +
      '</div>' +

      /* ── Lot Size ─────────────────────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Lot Size</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="lot_size" value="' + rc.lot_size + '" step="0.01" min="0.01" />' +
      '</div>' +

      /* ── History Lookback (merged value + unit) ───────── */
      '<div class="wd-form-group" style="grid-column:1/-1;">' +
        '<label class="wd-form-label">History Lookback</label>' +
        '<div class="wd-inline-row">' +
          '<input type="number" class="wd-form-input rc-input" data-key="tick_lookback_value" value="' + rc.tick_lookback_value + '" step="1" min="1" placeholder="Amount" />' +
          '<select class="wd-form-select rc-input" data-key="tick_lookback_unit">' + tlUnitOpts + '</select>' +
        '</div>' +
      '</div>' +

      /* ── Bar Size Points ──────────────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Bar Size Points</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="bar_size_points" value="' + rc.bar_size_points + '" step="1" min="1" />' +
      '</div>' +

      /* ── Max Bars in Memory ───────────────────────────── */
      '<div class="wd-form-group">' +
        '<label class="wd-form-label">Max Bars in Memory</label>' +
        '<input type="number" class="wd-form-input rc-input" data-key="max_bars_memory" value="' + rc.max_bars_memory + '" step="10" min="10" />' +
      '</div>' +

    '</div>';
  }

  /* ── Deployments Panel ───────────────────────────────────── */

  function _renderDeployments() {
    if (_deployments.length === 0) {
      return '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">' +
        'No deployments for this worker.</div>';
    }

    var html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    _deployments.forEach(function (d) {
      var stateClass = _deployStateClass(d.state);
      var updated = d.updated_at ? d.updated_at.replace('T', ' ').substring(0, 19) : '\u2014';
      html += '<div style="background:var(--bg-secondary);border-radius:6px;padding:10px 14px;">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
          '<span class="mono" style="font-size:12px;color:var(--accent);">' + d.deployment_id + '</span>' +
          '<span class="state-pill ' + stateClass + '">' + d.state.toUpperCase().replace(/_/g, ' ') + '</span>' +
        '</div>' +
        '<div style="display:flex;gap:16px;margin-top:6px;font-size:11px;color:var(--text-muted);">' +
          '<span>Strategy: <strong class="mono">' + (d.strategy_name || d.strategy_id) + '</strong></span>' +
          '<span>Symbol: <strong class="mono">' + d.symbol + '</strong></span>' +
          '<span>Bars: <strong class="mono">' + d.bar_size_points + 'pt / ' + d.max_bars_in_memory + '</strong></span>' +
        '</div>' +
        '<div style="display:flex;gap:16px;margin-top:4px;font-size:10.5px;color:var(--text-muted);">' +
          '<span>Updated: ' + updated + '</span>' +
          (d.last_error ? '<span style="color:var(--danger);">Error: ' + d.last_error + '</span>' : '') +
        '</div>';

      // Stop button for active deployments
      var activeStates = ['queued','sent_to_worker','acknowledged_by_worker','loading_strategy','fetching_ticks','generating_initial_bars','warming_up','running'];
      if (activeStates.indexOf(d.state) !== -1) {
        html += '<button class="wd-btn wd-btn-ghost dep-stop-btn" data-depid="' + d.deployment_id + '" style="margin-top:8px;font-size:10.5px;">' +
          '<i class="fa-solid fa-stop"></i> Stop</button>';
      }
      html += '</div>';
    });
    html += '</div>';
    return html;
  }

  /* ── Build Full Page ─────────────────────────────────────── */

  function _buildPage() {
    var w = _currentWorker;
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;
    var ip = w.host || '\u2014';

    var html = '<div class="worker-detail">';

    // Header
    html += '<div class="wd-header">' +
      '<div class="wd-header-left">' +
        '<button class="wd-back-btn" id="wd-back-btn"><i class="fa-solid fa-arrow-left"></i> Back to Fleet</button>' +
        '<div class="wd-header-info">' +
          '<h2>' + name + '</h2>' +
          '<div class="wd-header-meta">' +
            '<span>' + w.worker_id + '</span><span class="meta-sep">\u00B7</span>' +
            '<span>' + ip + '</span>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="wd-header-right">' +
        '<span class="state-pill ' + state + '" id="wd-state-pill">' + _stateLabel(state) + '</span>' +
        '<button class="wd-refresh-btn" id="wd-refresh-btn"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button>' +
        '<button class="wd-emergency-btn" id="wd-emergency-btn"><i class="fa-solid fa-circle-stop"></i> Emergency Stop</button>' +
      '</div></div>';

    // Status Cards
    html += '<div class="wd-status-grid" id="wd-status-grid">' + _renderStatusCards() + '</div>';

    // Content
    html += '<div class="wd-content">';

    // Main Column
    html += '<div class="wd-main-col">';

    // Strategy Selector
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Strategy Selection<span class="panel-badge">BACKEND</span></div>' +
      '<div class="wd-panel-body" id="wd-strat-selector-body">' +
        '<div class="loading-state" style="min-height:60px;"><div class="spinner"></div><p>Loading strategies\u2026</p></div>' +
      '</div></div>';

    // Runtime Config
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Runtime Configuration</div>' +
      '<div class="wd-panel-body" id="wd-runtime-body">' + _renderRuntimeConfig() + '</div></div>';

    // Strategy Parameters
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Strategy Parameters<span class="panel-badge" id="wd-param-count">0 PARAMS</span></div>' +
      '<div class="wd-panel-body"><div class="wd-params-list" id="wd-params-list">' +
        '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">Select a strategy to see parameters.</div>' +
      '</div></div></div>';

    html += '</div>'; // main-col

    // Side Column
    html += '<div class="wd-side-col">';

    // Deployment Readiness
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Deployment Readiness</div>' +
      '<div class="wd-panel-body"><div class="wd-checklist" id="wd-checklist">' + _renderChecklist() + '</div></div></div>';

    // Deployments
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Deployments<span class="panel-badge" id="wd-dep-count">0</span></div>' +
      '<div class="wd-panel-body" id="wd-deployments-body">' +
        '<div class="loading-state" style="min-height:60px;"><div class="spinner"></div><p>Loading\u2026</p></div>' +
      '</div></div>';

    // Activity Timeline
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Activity<span class="panel-badge mock">LOCAL UI</span></div>' +
      '<div class="wd-panel-body"><div class="wd-timeline" id="wd-timeline"></div></div></div>';

    html += '</div>'; // side-col
    html += '</div>'; // wd-content

    // Action Bar
    html += '<div class="wd-panel">' +
      '<div class="wd-action-bar">' +
        '<div class="wd-action-bar-left">' +
          '<button class="wd-btn wd-btn-ghost" id="wd-reset-changes"><i class="fa-solid fa-rotate-left"></i> Reset</button>' +
        '</div>' +
        '<div class="wd-action-bar-right">' +
          '<button class="wd-btn wd-btn-primary deploy" id="wd-deploy"><i class="fa-solid fa-rocket"></i> Deploy to Worker</button>' +
        '</div>' +
      '</div></div>';

    html += '</div>'; // worker-detail
    return html;
  }

  /* ── Attach Events ───────────────────────────────────────── */

  function _attachEvents() {
    document.getElementById('wd-back-btn').addEventListener('click', function () {
      App.navigateTo('fleet');
    });

    document.getElementById('wd-refresh-btn').addEventListener('click', function () {
      _refreshAll();
      _addActivity('Refreshed');
    });

    document.getElementById('wd-emergency-btn').addEventListener('click', function () {
      ModalManager.show({
        title: 'Emergency Stop',
        type: 'danger',
        bodyHtml: '<p>This will send stop commands for all active deployments on this worker.</p>' +
          '<div class="modal-warning"><i class="fa-solid fa-triangle-exclamation"></i>' +
          '<span>All open positions will remain unmanaged. Use with extreme caution.</span></div>',
        confirmText: 'Stop All',
        onConfirm: function () {
          _deployments.forEach(function (d) {
            var activeStates = ['queued','sent_to_worker','acknowledged_by_worker','loading_strategy','fetching_ticks','generating_initial_bars','warming_up','running'];
            if (activeStates.indexOf(d.state) !== -1) {
              ApiClient.stopDeployment(d.deployment_id).catch(function () {});
            }
          });
          ToastManager.show('Emergency stop sent.', 'warning');
          _addActivity('Emergency stop sent');
          setTimeout(_fetchDeployments, 2000);
        }
      });
    });

    _attachRuntimeEvents();

    document.getElementById('wd-deploy').addEventListener('click', _handleDeploy);

    document.getElementById('wd-reset-changes').addEventListener('click', function () {
      var defaults = DeploymentConfig.runtimeDefaults;
      _runtimeConfig = {};
      for (var k in defaults) _runtimeConfig[k] = defaults[k];
      document.getElementById('wd-runtime-body').innerHTML = _renderRuntimeConfig();
      _attachRuntimeEvents();
      _selectedStrategyId = null;
      _selectedStrategy = null;
      _parameterValues = {};
      _parameterDefaults = {};
      _loadStrategies();
      _updateChecklist();
      ToastManager.show('Reset to defaults.', 'info');
      _addActivity('Reset to defaults');
    });
  }

  function _attachRuntimeEvents() {
    document.querySelectorAll('.rc-input').forEach(function (input) {
      var key = input.getAttribute('data-key');

      /* ── Symbol gets special handling ──────────────── */
      if (key === 'symbol') {
        input.addEventListener('input', function () {
          input.value = input.value.toUpperCase().replace(/\s/g, '');
          _runtimeConfig.symbol = input.value;
          _validateSymbolInput();
          _updateChecklist();
        });
        input.addEventListener('blur', function () {
          input.value = input.value.trim().toUpperCase();
          _runtimeConfig.symbol = input.value;
          _validateSymbolInput();
          _updateChecklist();
        });
        return;
      }

      /* ── All other inputs ──────────────────────────── */
      input.addEventListener('change', function () {
        _runtimeConfig[key] = input.type === 'number' ? parseFloat(input.value) : input.value;
        _updateChecklist();
        _addActivity('Config: ' + key + ' updated');
      });
    });
  }

  function _validateSymbolInput() {
    var input = document.getElementById('wd-symbol-input');
    var errEl = document.getElementById('wd-symbol-error');
    if (!input || !errEl) return true;

    var val = (input.value || '').trim();
    var errSpan = errEl.querySelector('span');

    if (!val) {
      input.classList.remove('input-error');
      errEl.classList.remove('visible');
      return false;
    }

    if (!/^[A-Z0-9._]{1,30}$/.test(val)) {
      input.classList.add('input-error');
      errSpan.textContent = 'Only letters, numbers, dots, underscores allowed';
      errEl.classList.add('visible');
      return false;
    }

    input.classList.remove('input-error');
    errEl.classList.remove('visible');
    return true;
  }

  function _attachParamEvents() {
    document.querySelectorAll('.wd-param-input-ctrl').forEach(function (input) {
      var key = input.getAttribute('data-key');
      var handler = function () {
        var val;
        if (input.type === 'checkbox') val = input.checked;
        else if (input.tagName === 'SELECT' || input.type === 'text') val = input.value;
        else val = parseFloat(input.value);
        _parameterValues[key] = val;
        var row = document.querySelector('.wd-param-row[data-key="' + key + '"]');
        if (row) {
          if (val !== _parameterDefaults[key]) row.classList.add('modified');
          else row.classList.remove('modified');
        }
      };
      input.addEventListener(input.type === 'checkbox' ? 'change' : 'input', handler);
    });
    document.querySelectorAll('.wd-param-reset').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-key');
        var defVal = _parameterDefaults[key];
        _parameterValues[key] = defVal;
        var input = document.querySelector('.wd-param-input-ctrl[data-key="' + key + '"]');
        if (input) {
          if (input.type === 'checkbox') input.checked = defVal;
          else input.value = defVal;
        }
        var row = document.querySelector('.wd-param-row[data-key="' + key + '"]');
        if (row) row.classList.remove('modified');
      });
    });
  }

  function _attachDeploymentStopEvents() {
    document.querySelectorAll('.dep-stop-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var depId = btn.getAttribute('data-depid');
        ApiClient.stopDeployment(depId).then(function () {
          ToastManager.show('Stop sent for ' + depId, 'info');
          _addActivity('Stop sent: ' + depId);
          setTimeout(_fetchDeployments, 2000);
        }).catch(function (err) {
          ToastManager.show('Stop failed: ' + err.message, 'error');
        });
      });
    });
  }

  /* ── Strategy Loading ────────────────────────────────────── */

  function _loadStrategies() {
    var el = document.getElementById('wd-strat-selector-body');
    if (!el) return;

    ApiClient.getStrategies().then(function (data) {
      _strategies = data.strategies || [];
      el.innerHTML = _renderStrategySelector();

      var sel = document.getElementById('wd-strategy-select');
      if (sel) {
        sel.addEventListener('change', function () {
          var sid = sel.value;
          if (!sid) {
            _selectedStrategyId = null;
            _selectedStrategy = null;
            _parameterValues = {};
            _parameterDefaults = {};
            _renderStrategyMeta();
            document.getElementById('wd-params-list').innerHTML =
              '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">Select a strategy to see parameters.</div>';
            document.getElementById('wd-param-count').textContent = '0 PARAMS';
            _updateChecklist();
            return;
          }
          _selectedStrategyId = sid;
          // Find in loaded list
          for (var i = 0; i < _strategies.length; i++) {
            if (_strategies[i].strategy_id === sid) {
              _selectedStrategy = _strategies[i];
              break;
            }
          }
          // If list didn't include full parameters, fetch detail
          if (_selectedStrategy && (!_selectedStrategy.parameters || Object.keys(_selectedStrategy.parameters).length === 0)) {
            ApiClient.getStrategy(sid).then(function (data) {
              if (data.ok && data.strategy) {
                var detail = data.strategy;
                if (detail.parameters && typeof detail.parameters === 'object') {
                  _selectedStrategy.parameters = detail.parameters;
                  _selectedStrategy.parameter_count = Object.keys(detail.parameters).length;
                }
              }
              _renderStrategyMeta();
              _loadParamsFromSchema();
              _updateChecklist();
              _addActivity('Strategy selected: ' + sid);
            }).catch(function () {
              _renderStrategyMeta();
              _loadParamsFromSchema();
              _updateChecklist();
            });
          } else {
            _renderStrategyMeta();
            _loadParamsFromSchema();
            _updateChecklist();
            _addActivity('Strategy selected: ' + sid);
          }
        });
      }
    }).catch(function () {
      el.innerHTML = '<div style="font-size:12px;color:var(--danger);padding:8px 0;">' +
        'Failed to load strategies from backend.</div>';
    });
  }

  function _loadParamsFromSchema() {
    _parameterValues = {};
    _parameterDefaults = {};

    if (_selectedStrategy && _selectedStrategy.parameters) {
      var schema = _selectedStrategy.parameters;
      Object.keys(schema).forEach(function (key) {
        var spec = schema[key];
        if (typeof spec === 'object' && spec.default !== undefined) {
          _parameterValues[key] = spec.default;
          _parameterDefaults[key] = spec.default;
        }
      });
    }

    var el = document.getElementById('wd-params-list');
    if (el) {
      el.innerHTML = _renderParams();
      _attachParamEvents();
    }

    var countEl = document.getElementById('wd-param-count');
    if (countEl) countEl.textContent = Object.keys(_parameterValues).length + ' PARAMS';
  }

  /* ── Deployments Loading ─────────────────────────────────── */

  function _fetchDeployments() {
    var el = document.getElementById('wd-deployments-body');
    if (!el) return;

    ApiClient.getDeployments().then(function (data) {
      var all = data.deployments || [];
      var wid = _currentWorker.worker_id;
      _deployments = all.filter(function (d) { return d.worker_id === wid; });
      _deployments.sort(function (a, b) {
        return (b.updated_at || '').localeCompare(a.updated_at || '');
      });

      var countEl = document.getElementById('wd-dep-count');
      if (countEl) countEl.textContent = _deployments.length;

      el.innerHTML = _renderDeployments();
      _attachDeploymentStopEvents();
    }).catch(function () {
      el.innerHTML = '<div style="font-size:12px;color:var(--danger);padding:8px 0;">Failed to load deployments.</div>';
    });
  }

  /* ── Deploy Handler ──────────────────────────────────────── */

  function _handleDeploy() {
    if (!_selectedStrategyId) {
      ToastManager.show('Select a strategy first.', 'warning');
      return;
    }

    /* ── Symbol validation ───────────────────────────── */
    var symbolVal = (_runtimeConfig.symbol || '').trim().toUpperCase();
    _runtimeConfig.symbol = symbolVal;
    var symInput = document.getElementById('wd-symbol-input');
    if (symInput) symInput.value = symbolVal;

    if (!symbolVal) {
      ToastManager.show('Enter a symbol.', 'warning');
      if (symInput) symInput.focus();
      return;
    }
    if (!/^[A-Z0-9._]{1,30}$/.test(symbolVal)) {
      ToastManager.show('Invalid symbol — letters, numbers, dots, underscores only.', 'warning');
      _validateSymbolInput();
      if (symInput) symInput.focus();
      return;
    }

    if (!_runtimeConfig.bar_size_points || _runtimeConfig.bar_size_points <= 0) {
      ToastManager.show('Bar Size Points must be > 0.', 'warning');
      return;
    }

    var w = _currentWorker;
    var name = w.worker_name || w.worker_id;
    var modCount = _getModifiedCount();
    var tlDisplay = _runtimeConfig.tick_lookback_value + ' ' + _runtimeConfig.tick_lookback_unit;
    var stratName = _selectedStrategy ? (_selectedStrategy.strategy_name || _selectedStrategyId) : _selectedStrategyId;

    var bodyHtml =
      '<p>Deploy strategy to <strong>' + name + '</strong>?</p>' +
      '<div class="modal-summary">' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Worker</span><span class="modal-summary-value">' + name + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Strategy</span><span class="modal-summary-value">' + stratName + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Symbol</span><span class="modal-summary-value">' + _runtimeConfig.symbol + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Tick Lookback</span><span class="modal-summary-value">' + tlDisplay + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Bar Size Points</span><span class="modal-summary-value">' + _runtimeConfig.bar_size_points + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Max Bars in Memory</span><span class="modal-summary-value">' + _runtimeConfig.max_bars_memory + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Lot Size</span><span class="modal-summary-value">' + _runtimeConfig.lot_size + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Modified Params</span><span class="modal-summary-value">' + modCount + '</span></div>' +
      '</div>';

    ModalManager.show({
      title: 'Deploy Strategy',
      bodyHtml: bodyHtml,
      confirmText: 'Deploy',
      onConfirm: function () {
        var payload = {
          strategy_id: _selectedStrategyId,
          worker_id: w.worker_id,
          symbol: _runtimeConfig.symbol,
          tick_lookback_value: _runtimeConfig.tick_lookback_value,
          tick_lookback_unit: _runtimeConfig.tick_lookback_unit,
          bar_size_points: _runtimeConfig.bar_size_points,
          max_bars_in_memory: _runtimeConfig.max_bars_memory,
          lot_size: _runtimeConfig.lot_size,
          strategy_parameters: _parameterValues,
        };

        _addActivity('Deploying ' + stratName + ' to ' + name + '\u2026');

        ApiClient.createDeployment(payload).then(function (data) {
          ToastManager.show('Deployment created: ' + data.deployment_id, 'success');
          _addActivity('Deployment created: ' + data.deployment_id);
          setTimeout(_fetchDeployments, 2000);
        }).catch(function (err) {
          ToastManager.show('Deployment failed: ' + err.message, 'error');
          _addActivity('Deployment failed: ' + err.message);
        });
      }
    });
  }

  /* ── Refresh ─────────────────────────────────────────────── */

  function _refreshAll() {
    _refreshWorkerStatus();
    _fetchDeployments();
  }

  function _refreshWorkerStatus() {
    if (!_currentWorker) return;
    ApiClient.getFleetWorkers().then(function (data) {
      var workers = data.workers || [];
      var wid = _currentWorker.worker_id;
      for (var i = 0; i < workers.length; i++) {
        if (workers[i].worker_id === wid) {
          _currentWorker = workers[i];
          var grid = document.getElementById('wd-status-grid');
          if (grid) grid.innerHTML = _renderStatusCards();
          var pill = document.getElementById('wd-state-pill');
          if (pill) {
            var st = _currentWorker.state || 'unknown';
            pill.className = 'state-pill ' + st;
            pill.textContent = _stateLabel(st);
          }
          _updateChecklist();
          return;
        }
      }
    }).catch(function () {});
  }

  /* ── Public ──────────────────────────────────────────────── */

  function render(workerData) {
    _currentWorker = workerData;
    _initState();

    document.getElementById('main-content').innerHTML = _buildPage();
    _attachEvents();

    _addActivity('Worker detail opened: ' + (workerData.worker_name || workerData.worker_id));

    // Load backend data
    _loadStrategies();
    _fetchDeployments();

    _refreshInterval = setInterval(_refreshAll, 5000);
  }

  function destroy() {
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
    _currentWorker = null;
  }

  return { render: render, destroy: destroy };
})();