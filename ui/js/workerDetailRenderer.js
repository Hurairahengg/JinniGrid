/* workerDetailRenderer.js */

var WorkerDetailRenderer = (function () {
  'use strict';

  var _currentWorker = null;
  var _refreshInterval = null;
  var _fileSelected = false;
  var _selectedFileName = null;
  var _strategyLoaded = false;
  var _runtimeConfig = {};
  var _parameterValues = {};
  var _parameterDefaults = {};
  var _activityLog = [];

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

  /* ── State Init ──────────────────────────────────────────── */

  function _initState() {
    _fileSelected = false;
    _selectedFileName = null;
    _strategyLoaded = false;
    _activityLog = [];

    var defaults = DeploymentMockData.runtimeConfigDefaults;
    _runtimeConfig = {};
    for (var k in defaults) _runtimeConfig[k] = defaults[k];

    _parameterValues = {};
    _parameterDefaults = {};
    DeploymentMockData.strategyParameters.forEach(function (p) {
      _parameterValues[p.key] = p.defaultValue;
      _parameterDefaults[p.key] = p.defaultValue;
    });
  }

  /* ── Activity Log ────────────────────────────────────────── */

  function _addActivity(text) {
    _activityLog.unshift({ time: _timeNow(), text: text });
    if (_activityLog.length > 20) _activityLog.length = 20;
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
    var pnl = _formatPnl(w.floating_pnl);
    var pnlStyle = '';
    if (w.floating_pnl !== null && w.floating_pnl !== undefined) {
      pnlStyle = w.floating_pnl >= 0 ? 'color:var(--success)' : 'color:var(--danger)';
    }

    var cards = [
      { label: 'Connection', value: '<div class="status-indicator"><span class="wd-status-dot-sm ' + _stateColor(state) + '"></span>' + _stateLabel(state) + '</div>' },
      { label: 'Runtime State', value: '<div class="status-indicator"><span class="wd-status-dot-sm blue"></span>Idle</div>' },
      { label: 'Active Strategy', value: strats },
      { label: 'Open Positions', value: String(w.open_positions_count || 0) },
      { label: 'Floating PnL', value: '<span style="' + pnlStyle + '">' + pnl + '</span>' },
      { label: 'CPU Load', value: _nullVal(null) },
      { label: 'RAM Load', value: _nullVal(null) },
      { label: 'Last Heartbeat', value: _formatAge(w.heartbeat_age_seconds) }
    ];

    var html = '';
    cards.forEach(function (c) {
      html += '<div class="wd-status-card"><span class="status-label">' + c.label + '</span><span class="status-value">' + c.value + '</span></div>';
    });
    return html;
  }

  /* ── Checklist ───────────────────────────────────────────── */

  function _renderChecklist() {
    var w = _currentWorker;
    var onlineStates = ['online', 'running', 'idle'];
    var isOnline = onlineStates.indexOf(w.state) !== -1;
    var tlOk = _runtimeConfig.tick_lookback_value > 0;
    var bsOk = _runtimeConfig.bar_size_points > 0;
    var mbOk = _runtimeConfig.max_bars_memory > 0;

    var items = [
      { pass: isOnline, text: 'Worker connected', type: isOnline ? 'pass' : 'fail' },
      { pass: _fileSelected, text: 'Strategy file selected', type: _fileSelected ? 'pass' : 'fail' },
      { pass: !!_runtimeConfig.symbol, text: 'Symbol selected', type: _runtimeConfig.symbol ? 'pass' : 'fail' },
      { pass: tlOk, text: 'Tick lookback configured', type: tlOk ? 'pass' : 'fail' },
      { pass: bsOk, text: 'Bar size points configured', type: bsOk ? 'pass' : 'fail' },
      { pass: mbOk, text: 'Max bars memory configured', type: mbOk ? 'pass' : 'fail' },
      { pass: true, text: 'Parameters configured', type: 'pass' },
      { pass: false, text: 'Backend deployment not connected in this UI phase', type: 'info', dimmed: true }
    ];

    var iconMap = { pass: 'fa-check', fail: 'fa-xmark', warn: 'fa-exclamation', info: 'fa-info' };

    var html = '';
    items.forEach(function (item) {
      var textClass = item.dimmed ? 'wd-check-text dimmed' : (item.type === 'pass' ? 'wd-check-text pass' : 'wd-check-text');
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

  /* ── Build Strategy Parameters ───────────────────────────── */

  function _renderParams() {
    var params = DeploymentMockData.strategyParameters;
    var html = '';
    params.forEach(function (p) {
      var val = _parameterValues[p.key];
      var isModified = val !== _parameterDefaults[p.key];
      var modClass = isModified ? ' modified' : '';
      var input = '';

      if (p.type === 'bool') {
        input = '<input type="checkbox" class="wd-toggle wd-param-input-ctrl" data-key="' + p.key + '"' +
          (val ? ' checked' : '') + ' />';
      } else {
        var attrs = 'type="number" class="wd-param-input wd-param-input-ctrl" data-key="' + p.key + '" value="' + val + '"';
        if (p.min !== null) attrs += ' min="' + p.min + '"';
        if (p.max !== null) attrs += ' max="' + p.max + '"';
        if (p.step !== null) attrs += ' step="' + p.step + '"';
        input = '<input ' + attrs + ' />';
      }

      html += '<div class="wd-param-row' + modClass + '" data-key="' + p.key + '">' +
        '<div class="wd-param-info">' +
          '<div class="wd-param-name">' + p.label +
            '<span class="wd-param-type-badge type-' + p.type + '">' + p.type + '</span></div>' +
          '<div class="wd-param-desc">' + p.description + '</div>' +
        '</div>' +
        '<div class="wd-param-controls">' +
          input +
          '<button class="wd-param-reset" data-key="' + p.key + '" title="Reset to default"><i class="fa-solid fa-rotate-left"></i></button>' +
        '</div></div>';
    });
    return html;
  }

  /* ── Build Runtime Config ────────────────────────────────── */

  function _renderRuntimeConfig() {
    var rc = _runtimeConfig;
    var symbols = DeploymentMockData.symbolOptions;
    var tlUnits = DeploymentMockData.tickLookbackUnits;
    var modes = DeploymentMockData.executionModes;

    var symOpts = symbols.map(function (s) {
      return '<option value="' + s + '"' + (rc.symbol === s ? ' selected' : '') + '>' + s + '</option>';
    }).join('');

    var tlUnitOpts = tlUnits.map(function (u) {
      var label = u.charAt(0).toUpperCase() + u.slice(1);
      return '<option value="' + u + '"' + (rc.tick_lookback_unit === u ? ' selected' : '') + '>' + label + '</option>';
    }).join('');

    var modeOpts = modes.map(function (m) {
      return '<option value="' + m.value + '"' + (rc.execution_mode === m.value ? ' selected' : '') +
        (m.disabled ? ' disabled' : '') + '>' + m.label + '</option>';
    }).join('');

    var html =
      '<div class="wd-form-grid">' +
        '<div class="wd-form-group"><label class="wd-form-label">Symbol</label>' +
          '<select class="wd-form-select rc-input" data-key="symbol">' + symOpts + '</select></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Lot Size</label>' +
          '<input type="number" class="wd-form-input rc-input" data-key="lot_size" value="' + rc.lot_size + '" step="0.01" min="0.01" /></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Tick Lookback</label>' +
          '<input type="number" class="wd-form-input rc-input" data-key="tick_lookback_value" value="' + rc.tick_lookback_value + '" step="1" min="1" /></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Lookback Unit</label>' +
          '<select class="wd-form-select rc-input" data-key="tick_lookback_unit">' + tlUnitOpts + '</select></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Bar Size Points</label>' +
          '<input type="number" class="wd-form-input rc-input" data-key="bar_size_points" value="' + rc.bar_size_points + '" step="1" min="1" /></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Max Bars in Memory</label>' +
          '<input type="number" class="wd-form-input rc-input" data-key="max_bars_memory" value="' + rc.max_bars_memory + '" step="10" min="10" /></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Max Spread</label>' +
          '<input type="number" class="wd-form-input rc-input" data-key="max_spread" value="' + rc.max_spread + '" step="0.1" min="0" /></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Magic Number</label>' +
          '<input type="number" class="wd-form-input rc-input" data-key="magic_number" value="' + rc.magic_number + '" step="1" /></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Slippage</label>' +
          '<input type="number" class="wd-form-input rc-input" data-key="slippage" value="' + rc.slippage + '" step="1" min="0" /></div>' +
        '<div class="wd-form-group"><label class="wd-form-label">Execution Mode</label>' +
          '<select class="wd-form-select rc-input" data-key="execution_mode">' + modeOpts + '</select></div>' +
      '</div>' +
      '<div style="margin-top:16px;">' +
        '<div class="wd-toggle-row">' +
          '<div class="wd-toggle-label"><span>Auto-start after deploy</span><span>Automatically start strategy execution after deployment</span></div>' +
          '<input type="checkbox" class="wd-toggle rc-toggle" data-key="auto_start"' + (rc.auto_start ? ' checked' : '') + ' />' +
        '</div>' +
        '<div class="wd-toggle-row">' +
          '<div class="wd-toggle-label"><span>Allow new entries</span><span>Allow strategy to open new positions</span></div>' +
          '<input type="checkbox" class="wd-toggle rc-toggle" data-key="allow_new_entries"' + (rc.allow_new_entries ? ' checked' : '') + ' />' +
        '</div>' +
        '<div class="wd-toggle-row">' +
          '<div class="wd-toggle-label"><span>Close existing positions</span><span>Close all open positions before deploying</span></div>' +
          '<input type="checkbox" class="wd-toggle rc-toggle" data-key="close_existing"' + (rc.close_existing ? ' checked' : '') + ' />' +
        '</div>' +
      '</div>';
    return html;
  }

  /* ── Build Metadata Preview ──────────────────────────────── */

  function _renderMetadata() {
    var m = DeploymentMockData.strategyMetadata;
    return '<div class="wd-metadata-grid">' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Name</span><span class="wd-metadata-value">' + m.name + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Version</span><span class="wd-metadata-value">' + m.version + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Type</span><span class="wd-metadata-value">' + m.type + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Parameters</span><span class="wd-metadata-value">' + m.parameterCount + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Required Symbols</span><span class="wd-metadata-value">' + m.requiredSymbols.join(', ') + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Last Modified</span><span class="wd-metadata-value">' + m.lastModified + '</span></div>' +
      '<div class="wd-metadata-item" style="grid-column:1/-1;"><span class="wd-metadata-label">Description</span><span class="wd-metadata-value" style="font-family:Inter,sans-serif;">' + m.description + '</span></div>' +
      '<div class="wd-metadata-item"><span class="wd-metadata-label">Validation</span><span class="wd-metadata-value" style="color:var(--success);">Mock Validated \u2713</span></div>' +
    '</div>';
  }

  /* ── Build Full Page ─────────────────────────────────────── */

  function _buildPage() {
    var w = _currentWorker;
    var state = w.state || 'unknown';
    var name = w.worker_name || w.worker_id;
    var ip = w.host || '\u2014';
    var paramCount = DeploymentMockData.strategyParameters.length;

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

    // Strategy File Panel
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Strategy File<span class="panel-badge mock">UI PREVIEW</span></div>' +
      '<div class="wd-panel-body">' +
        '<div class="wd-file-upload" id="wd-file-upload">' +
          '<input type="file" id="wd-file-input" accept=".py" style="display:none" />' +
          '<i class="fa-solid fa-file-code"></i>' +
          '<h4>Select Strategy File</h4>' +
          '<p>.py files only</p>' +
          '<div id="wd-file-status"></div>' +
        '</div>' +
        '<div id="wd-metadata" style="display:none;"></div>' +
      '</div></div>';

    // Runtime Config Panel
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Runtime Configuration<span class="panel-badge mock">UI PREVIEW</span></div>' +
      '<div class="wd-panel-body" id="wd-runtime-body">' + _renderRuntimeConfig() + '</div></div>';

    // Strategy Parameters Panel
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Strategy Parameters<span class="panel-badge">' + paramCount + ' PARAMS</span></div>' +
      '<div class="wd-panel-body"><div class="wd-params-list" id="wd-params-list">' + _renderParams() + '</div></div></div>';

    html += '</div>'; // main-col

    // Side Column
    html += '<div class="wd-side-col">';

    // Deployment Readiness
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Deployment Readiness</div>' +
      '<div class="wd-panel-body"><div class="wd-checklist" id="wd-checklist">' + _renderChecklist() + '</div></div></div>';

    // Activity Timeline
    html += '<div class="wd-panel">' +
      '<div class="wd-panel-header">Activity Timeline</div>' +
      '<div class="wd-panel-body"><div class="wd-timeline" id="wd-timeline"></div></div></div>';

    html += '</div>'; // side-col
    html += '</div>'; // wd-content

    // Action Bar
    html += '<div class="wd-panel">' +
      '<div class="wd-action-bar">' +
        '<div class="wd-action-bar-left">' +
          '<button class="wd-btn wd-btn-ghost" id="wd-save-draft"><i class="fa-solid fa-floppy-disk"></i> Save Draft</button>' +
          '<button class="wd-btn wd-btn-ghost" id="wd-reset-changes"><i class="fa-solid fa-rotate-left"></i> Reset Changes</button>' +
        '</div>' +
        '<div class="wd-action-bar-right">' +
          '<button class="wd-btn wd-btn-outline" id="wd-validate"><i class="fa-solid fa-shield-check"></i> Validate Strategy</button>' +
          '<button class="wd-btn wd-btn-primary deploy" id="wd-deploy"><i class="fa-solid fa-rocket"></i> Deploy to Worker</button>' +
        '</div>' +
      '</div></div>';

    html += '</div>'; // worker-detail
    return html;
  }

  /* ── Attach Events ───────────────────────────────────────── */

  function _attachEvents() {
    // Back
    document.getElementById('wd-back-btn').addEventListener('click', function () {
      App.navigateTo('fleet');
    });

    // Refresh
    document.getElementById('wd-refresh-btn').addEventListener('click', function () {
      _refreshStatus();
      _addActivity('Status refreshed');
    });

    // Emergency Stop
    document.getElementById('wd-emergency-btn').addEventListener('click', function () {
      ModalManager.show({
        title: 'Emergency Stop',
        type: 'danger',
        bodyHtml: '<p>This will immediately halt all strategy execution on this worker.</p>' +
          '<div class="modal-warning"><i class="fa-solid fa-triangle-exclamation"></i>' +
          '<span>All open positions will remain unmanaged. Use with extreme caution.</span></div>',
        confirmText: 'Stop Worker',
        onConfirm: function () {
          ToastManager.show('Emergency stop is not connected in this UI phase.', 'warning');
          _addActivity('Emergency stop requested (not connected)');
        }
      });
    });

    // File upload
    var uploadArea = document.getElementById('wd-file-upload');
    var fileInput = document.getElementById('wd-file-input');
    uploadArea.addEventListener('click', function () { fileInput.click(); });
    fileInput.addEventListener('change', function () {
      if (!fileInput.files || !fileInput.files[0]) return;
      var file = fileInput.files[0];
      if (!file.name.endsWith('.py')) {
        ToastManager.show('Only .py strategy files are accepted.', 'error');
        return;
      }
      _fileSelected = true;
      _selectedFileName = file.name;
      _strategyLoaded = true;

      uploadArea.classList.add('has-file');
      var statusEl = document.getElementById('wd-file-status');
      uploadArea.querySelector('h4').textContent = 'Strategy File Selected';
      statusEl.innerHTML =
        '<div class="file-name">' + file.name + '</div>' +
        '<div class="wd-file-status" style="color:var(--success);"><i class="fa-solid fa-circle-check"></i> Mock validated</div>';

      var metaEl = document.getElementById('wd-metadata');
      metaEl.style.display = 'block';
      metaEl.innerHTML = _renderMetadata();

      _updateChecklist();
      _addActivity('Strategy file selected: ' + file.name);
      _addActivity('Strategy mock validated');
    });

    // Runtime config inputs
    _attachRuntimeEvents();

    // Parameter inputs
    _attachParamEvents();

    // Deploy button
    document.getElementById('wd-deploy').addEventListener('click', _handleDeploy);

    // Validate button
    document.getElementById('wd-validate').addEventListener('click', function () {
      ToastManager.show('Mock validation passed. Backend validation not connected.', 'info');
      _addActivity('Strategy validation triggered (mock)');
    });

    // Save Draft
    document.getElementById('wd-save-draft').addEventListener('click', function () {
      ToastManager.show('Draft saved locally. Backend persistence not connected.', 'info');
      _addActivity('Draft saved (local only)');
    });

    // Reset Changes
    document.getElementById('wd-reset-changes').addEventListener('click', function () {
      _initState();
      document.getElementById('wd-runtime-body').innerHTML = _renderRuntimeConfig();
      document.getElementById('wd-params-list').innerHTML = _renderParams();
      _updateChecklist();
      _attachRuntimeEvents();
      _attachParamEvents();

      var uploadArea = document.getElementById('wd-file-upload');
      uploadArea.classList.remove('has-file');
      uploadArea.querySelector('h4').textContent = 'Select Strategy File';
      document.getElementById('wd-file-status').innerHTML = '';
      document.getElementById('wd-metadata').style.display = 'none';

      ToastManager.show('Changes reset to defaults.', 'info');
      _addActivity('All changes reset to defaults');
    });
  }

  function _attachRuntimeEvents() {
    document.querySelectorAll('.rc-input').forEach(function (input) {
      input.addEventListener('change', function () {
        var key = input.getAttribute('data-key');
        _runtimeConfig[key] = input.type === 'number' ? parseFloat(input.value) : input.value;
        _updateChecklist();
        _addActivity('Runtime config updated: ' + key);
      });
    });
    document.querySelectorAll('.rc-toggle').forEach(function (toggle) {
      toggle.addEventListener('change', function () {
        var key = toggle.getAttribute('data-key');
        _runtimeConfig[key] = toggle.checked;
        _addActivity('Toggle changed: ' + key + ' = ' + toggle.checked);
      });
    });
  }

  function _attachParamEvents() {
    document.querySelectorAll('.wd-param-input-ctrl').forEach(function (input) {
      var key = input.getAttribute('data-key');
      var handler = function () {
        var val = input.type === 'checkbox' ? input.checked : parseFloat(input.value);
        _parameterValues[key] = val;
        var row = document.querySelector('.wd-param-row[data-key="' + key + '"]');
        if (row) {
          if (val !== _parameterDefaults[key]) row.classList.add('modified');
          else row.classList.remove('modified');
        }
        _addActivity('Parameter updated: ' + key + ' = ' + val);
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
        _addActivity('Parameter reset: ' + key + ' \u2192 ' + defVal);
      });
    });
  }

  /* ── Deploy Handler ──────────────────────────────────────── */

  function _handleDeploy() {
    var w = _currentWorker;
    var name = w.worker_name || w.worker_id;
    var stratName = _strategyLoaded ? DeploymentMockData.strategyMetadata.name : (_selectedFileName || 'Not selected');
    var modCount = _getModifiedCount();
    var tlDisplay = _runtimeConfig.tick_lookback_value + ' ' + _runtimeConfig.tick_lookback_unit;

    var bodyHtml =
      '<p>You are about to prepare a mock deployment.</p>' +
      '<div class="modal-summary">' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Worker</span><span class="modal-summary-value">' + name + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Strategy</span><span class="modal-summary-value">' + stratName + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Symbol</span><span class="modal-summary-value">' + _runtimeConfig.symbol + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Tick Lookback</span><span class="modal-summary-value">' + tlDisplay + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Bar Size Points</span><span class="modal-summary-value">' + _runtimeConfig.bar_size_points + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Max Bars in Memory</span><span class="modal-summary-value">' + _runtimeConfig.max_bars_memory + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Lot Size</span><span class="modal-summary-value">' + _runtimeConfig.lot_size + '</span></div>' +
        '<div class="modal-summary-row"><span class="modal-summary-label">Modified Params</span><span class="modal-summary-value">' + modCount + '</span></div>' +
      '</div>' +
      '<div class="modal-warning"><i class="fa-solid fa-triangle-exclamation"></i>' +
      '<span>UI preview only. Backend deployment not implemented in this phase.</span></div>';

    ModalManager.show({
      title: 'Deployment Preview',
      bodyHtml: bodyHtml,
      confirmText: 'Confirm Deploy',
      onConfirm: function () {
        ToastManager.show('Mock deployment prepared. Backend deployment will be wired in a later phase.', 'success');
        _addActivity('Mock deployment prepared for ' + name);
      }
    });
  }

  /* ── Refresh Status ──────────────────────────────────────── */

  function _refreshStatus() {
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

    _addActivity('Worker detail opened');
    _addActivity('Worker connected: ' + (workerData.worker_name || workerData.worker_id));
    if (workerData.heartbeat_age_seconds !== null && workerData.heartbeat_age_seconds !== undefined) {
      _addActivity('Heartbeat received (' + _formatAge(workerData.heartbeat_age_seconds) + ')');
    }

    _refreshInterval = setInterval(_refreshStatus, 5000);
  }

  function destroy() {
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
    _currentWorker = null;
  }

  return { render: render, destroy: destroy };
})();