# Repo Snapshot — Part 5/5

- Root: `/home/hurairahengg/Documents/JinniGrid`
- Total files: `28` | This chunk: `7`
- you knwo my whole jinni grid systeM/ basically it is thereliek a kubernetes server setup what it does is basically a mother server with ui and bunch of lank state VMs. the vms run a speacial typa of renko style bars not normal timeframe u will get more context in the codes but yeha and we can uipload strategy codes though mother ui and it wiill run strategy mt5 report and ecetra ecetra.theres the whole ui with a professional protfolio and contorls such as settings and fleet management and so on yeah. currently im mostly dont and need bug fixes for many thigns so yeah. understand each code its role and keep in ur context i will give u big promtps to update code later duinerstood

## Files in Part 5

```text
ui/js/validationRenderer.js
app/services/mainServices.py
vm/trading/execution.py
vm/trading/sim_executor.py
ui/index.html
app/config.py
app/services/__init__.py
```

## Contents

---

## `ui/js/validationRenderer.js`

```javascript
/* ================================================================
   JINNI GRID — Validation Module
   ui/js/validationRenderer.js

   Sections:
   1. Job Creation Form (strategy + dynamic params, symbol, month, year, VM, config)
   2. Job History List (with status polling)
   3. Job Results View (equity chart, stats, trade table, download)
   ================================================================ */

var ValidationRenderer = (function () {
  'use strict';

  var _refreshInterval = null;
  var _charts = {};
  var _currentView = 'list';
  var _currentJobId = null;
  var _strategies = [];
  var _workers = [];
  var _selectedStrategy = null;
  var _parameterValues = {};
  var _parameterDefaults = {};

  function _destroyCharts() {
    for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } }
  }

  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  /* ── Main Render ──────────────────────────────────────────── */
  function render() {
    _currentView = 'list';
    _currentJobId = null;
    _selectedStrategy = null;
    _parameterValues = {};
    _parameterDefaults = {};
    _destroyCharts();

    var html = '<div class="fleet-page" id="validation-page">';

    /* Header */
    html += '<div class="fleet-page-header">';
    html += '<span class="fleet-page-title"><i class="fa-solid fa-flask-vial" style="color:var(--accent);margin-right:8px;"></i>Strategy Validation</span>';
    html += '<div class="fleet-page-meta">';
    html += '<button class="wd-refresh-btn" id="val-refresh"><i class="fa-solid fa-arrows-rotate"></i> Refresh</button>';
    html += '</div></div>';

    /* New Job Panel */
    html += '<div class="wd-panel" id="val-create-panel">';
    html += '<div class="wd-panel-header">New Validation Job<span class="panel-badge">BACKTEST</span></div>';
    html += '<div class="wd-panel-body" id="val-form-body">' + _spinner(80) + '</div>';
    html += '</div>';

    /* Strategy Parameters Panel (shown after strategy selection) */
    html += '<div class="wd-panel" id="val-params-panel" style="display:none;">';
    html += '<div class="wd-panel-header">Strategy Parameters<span class="panel-badge" id="val-param-count">0 PARAMS</span></div>';
    html += '<div class="wd-panel-body" id="val-params-body"></div>';
    html += '</div>';

    /* Jobs List */
    html += '<div id="val-jobs-content">' + _spinner() + '</div>';

    /* Results (hidden until clicked) */
    html += '<div id="val-results-content" style="display:none;"></div>';

    html += '</div>';
    document.getElementById('main-content').innerHTML = html;

    document.getElementById('val-refresh').addEventListener('click', function () {
      _fetchJobs();
    });

    _loadFormData();
    _fetchJobs();
    _refreshInterval = setInterval(_fetchJobs, 5000);
  }

  /* ── Load Form Data (strategies + workers) ────────────────── */
  function _loadFormData() {
    Promise.all([
      ApiClient.getStrategies().catch(function () { return { strategies: [] }; }),
      ApiClient.getFleetWorkers().catch(function () { return { workers: [] }; })
    ]).then(function (r) {
      _strategies = (r[0].strategies || []).filter(function (s) { return s.class_name; });
      _workers = r[1].workers || [];
      _renderForm();
    });
  }

  /* ── Render Form ──────────────────────────────────────────── */
  function _renderForm() {
    var el = document.getElementById('val-form-body');
    if (!el) return;

    var now = new Date();
    var curYear = now.getFullYear();
    var curMonth = now.getMonth();

    /* ★ Pull defaults from GlobalSettings */
    var vd = GlobalSettings.getValidationDefaults();
    var dd = GlobalSettings.getDeploymentDefaults();

    var html = '<div class="wd-form-grid" style="grid-template-columns:1fr 1fr 1fr;">';

    /* Strategy */
    html += '<div class="wd-form-group"><label class="wd-form-label">Strategy</label>';
    html += '<select class="wd-form-select" id="val-strategy">';
    html += '<option value="">-- Select Strategy --</option>';
    _strategies.forEach(function (s) {
      html += '<option value="' + s.strategy_id + '">' + (s.strategy_name || s.strategy_id) + ' v' + (s.version || '?') + '</option>';
    });
    html += '</select></div>';

    /* Symbol — from settings */
    html += '<div class="wd-form-group"><label class="wd-form-label">Symbol</label>';
    html += '<input type="text" class="wd-form-input" id="val-symbol" value="' + vd.symbol + '" placeholder="e.g. XAUUSD" autocomplete="off" spellcheck="false" /></div>';

    /* Worker VM */
    html += '<div class="wd-form-group"><label class="wd-form-label">Worker VM</label>';
    html += '<select class="wd-form-select" id="val-worker">';
    html += '<option value="">-- Select Worker --</option>';
    _workers.forEach(function (w) {
      var name = w.worker_name || w.worker_id;
      var st = w.state || 'unknown';
      html += '<option value="' + w.worker_id + '">' + name + ' (' + st + ')</option>';
    });
    html += '</select></div>';

    /* Month */
    html += '<div class="wd-form-group"><label class="wd-form-label">Month</label>';
    html += '<select class="wd-form-select" id="val-month">';
    MONTHS.forEach(function (m, i) {
      var sel = (i === curMonth) ? ' selected' : '';
      html += '<option value="' + (i + 1) + '"' + sel + '>' + m + '</option>';
    });
    html += '</select></div>';

    /* Year */
    html += '<div class="wd-form-group"><label class="wd-form-label">Year</label>';
    html += '<select class="wd-form-select" id="val-year">';
    for (var y = curYear; y >= 2020; y--) {
      html += '<option value="' + y + '"' + (y === curYear ? ' selected' : '') + '>' + y + '</option>';
    }
    html += '</select></div>';

    /* Lot Size — from settings */
    html += '<div class="wd-form-group"><label class="wd-form-label">Lot Size</label>';
    html += '<input type="number" class="wd-form-input" id="val-lot" value="' + vd.lot_size + '" step="0.01" min="0.01" /></div>';

    /* Bar Size Points — from settings */
    html += '<div class="wd-form-group"><label class="wd-form-label">Bar Size Points</label>';
    html += '<input type="number" class="wd-form-input" id="val-barsize" value="' + vd.bar_size_points + '" step="1" min="1" /></div>';

    /* Max Bars — from settings */
    html += '<div class="wd-form-group"><label class="wd-form-label">Max Bars Memory</label>';
    html += '<input type="number" class="wd-form-input" id="val-maxbars" value="' + vd.max_bars_memory + '" step="10" min="10" /></div>';

    /* Spread — from settings */
    html += '<div class="wd-form-group"><label class="wd-form-label">Spread (points)</label>';
    html += '<input type="number" class="wd-form-input" id="val-spread" value="' + vd.spread_points + '" step="0.1" min="0" /></div>';

    /* Commission — from settings */
    html += '<div class="wd-form-group"><label class="wd-form-label">Commission / Lot</label>';
    html += '<input type="number" class="wd-form-input" id="val-comm" value="' + vd.commission_per_lot + '" step="0.01" min="0" /></div>';

    html += '</div>';

    /* Run Button */
    html += '<div style="margin-top:16px;display:flex;gap:10px;justify-content:flex-end;">';
    html += '<button class="wd-btn wd-btn-primary deploy" id="val-run-btn"><i class="fa-solid fa-play"></i> Run Validation</button>';
    html += '</div>';

    el.innerHTML = html;

    /* Events */
    document.getElementById('val-run-btn').addEventListener('click', _handleRun);

    var symInput = document.getElementById('val-symbol');
    symInput.addEventListener('input', function () {
      symInput.value = symInput.value.toUpperCase().replace(/\s/g, '');
    });

    document.getElementById('val-strategy').addEventListener('change', _onStrategyChange);
  }

  /* ── Strategy Selection → Load Parameters ─────────────────── */
  function _onStrategyChange() {
    var sid = document.getElementById('val-strategy').value;
    var paramsPanel = document.getElementById('val-params-panel');
    var paramsBody = document.getElementById('val-params-body');
    var paramCount = document.getElementById('val-param-count');

    _selectedStrategy = null;
    _parameterValues = {};
    _parameterDefaults = {};

    if (!sid) {
      if (paramsPanel) paramsPanel.style.display = 'none';
      return;
    }

    /* Find in loaded list */
    var found = null;
    for (var i = 0; i < _strategies.length; i++) {
      if (_strategies[i].strategy_id === sid) {
        found = _strategies[i];
        break;
      }
    }

    if (!found) {
      if (paramsPanel) paramsPanel.style.display = 'none';
      return;
    }

    /* If parameters are empty/missing, fetch detail from backend */
    if (!found.parameters || Object.keys(found.parameters).length === 0) {
      if (paramsBody) paramsBody.innerHTML = '<div style="padding:8px;color:var(--text-muted);font-size:12px;"><i class="fa-solid fa-spinner fa-spin" style="margin-right:6px;"></i>Loading parameters\u2026</div>';
      if (paramsPanel) paramsPanel.style.display = '';

      ApiClient.getStrategy(sid).then(function (data) {
        if (data.ok && data.strategy) {
          var detail = data.strategy;
          if (detail.parameters && typeof detail.parameters === 'object') {
            found.parameters = detail.parameters;
            found.parameter_count = Object.keys(detail.parameters).length;
          }
        }
        _selectedStrategy = found;
        _initParamsFromSchema();
        _renderParams();
      }).catch(function () {
        _selectedStrategy = found;
        _initParamsFromSchema();
        _renderParams();
      });
    } else {
      _selectedStrategy = found;
      _initParamsFromSchema();
      _renderParams();
    }
  }

  /* ── Initialize Parameter Values from Schema ──────────────── */
  function _initParamsFromSchema() {
    _parameterValues = {};
    _parameterDefaults = {};

    if (!_selectedStrategy || !_selectedStrategy.parameters) return;

    var schema = _selectedStrategy.parameters;
    var keys = Object.keys(schema);
    keys.forEach(function (key) {
      var spec = schema[key];
      if (typeof spec === 'object' && spec.default !== undefined) {
        _parameterValues[key] = spec.default;
        _parameterDefaults[key] = spec.default;
      }
    });
  }

  /* ── Render Strategy Parameters ───────────────────────────── */
  function _renderParams() {
    var paramsPanel = document.getElementById('val-params-panel');
    var paramsBody = document.getElementById('val-params-body');
    var paramCount = document.getElementById('val-param-count');

    if (!paramsPanel || !paramsBody) return;

    if (!_selectedStrategy || !_selectedStrategy.parameters ||
        Object.keys(_selectedStrategy.parameters).length === 0) {
      paramsBody.innerHTML = '<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">' +
        'No editable parameters exposed by this strategy.</div>';
      if (paramCount) paramCount.textContent = '0 PARAMS';
      paramsPanel.style.display = '';
      return;
    }

    var schema = _selectedStrategy.parameters;
    var keys = Object.keys(schema);
    if (paramCount) paramCount.textContent = keys.length + ' PARAMS';

    var html = '<div class="wd-params-list">';

    keys.forEach(function (key) {
      var spec = schema[key];
      if (typeof spec !== 'object') return;

      var ptype = spec.type || 'number';
      var label = spec.label || key;
      var desc = spec.help || '';
      var defVal = spec.default !== undefined ? spec.default : '';
      var val = _parameterValues.hasOwnProperty(key) ? _parameterValues[key] : defVal;
      var isModified = val !== defVal;
      var modClass = isModified ? ' modified' : '';

      /* Type badge */
      var typeBadge = 'string';
      if (ptype === 'boolean') typeBadge = 'bool';
      else if (ptype === 'number') typeBadge = String(defVal).indexOf('.') !== -1 ? 'float' : 'int';

      /* Input element */
      var input = '';

      if (ptype === 'boolean') {
        input = '<input type="checkbox" class="wd-toggle val-param-ctrl" data-key="' + key + '"' +
          (val ? ' checked' : '') + ' />';
      } else if (ptype === 'select' && spec.options) {
        input = '<select class="wd-param-input val-param-ctrl" data-key="' + key + '" style="width:120px;text-align:left;">';
        spec.options.forEach(function (opt) {
          var optVal = typeof opt === 'object' ? opt.value : opt;
          var optLabel = typeof opt === 'object' ? (opt.label || opt.value) : opt;
          input += '<option value="' + optVal + '"' + (String(optVal) === String(val) ? ' selected' : '') + '>' + optLabel + '</option>';
        });
        input += '</select>';
      } else if (ptype === 'string' || ptype === 'text') {
        input = '<input type="text" class="wd-param-input val-param-ctrl" data-key="' + key + '" value="' + (val || '') + '" style="width:120px;text-align:left;" />';
      } else {
        var attrs = 'type="number" class="wd-param-input val-param-ctrl" data-key="' + key + '" value="' + val + '"';
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
          '<button class="wd-param-reset val-param-reset" data-key="' + key + '" title="Reset to default"><i class="fa-solid fa-rotate-left"></i></button>' +
        '</div></div>';
    });

    html += '</div>';
    paramsBody.innerHTML = html;
    paramsPanel.style.display = '';

    _attachParamEvents();
  }

  /* ── Attach Parameter Events ──────────────────────────────── */
  function _attachParamEvents() {
    document.querySelectorAll('.val-param-ctrl').forEach(function (input) {
      var key = input.getAttribute('data-key');
      var handler = function () {
        var val;
        if (input.type === 'checkbox') val = input.checked;
        else if (input.tagName === 'SELECT' || input.type === 'text') val = input.value;
        else val = parseFloat(input.value);
        _parameterValues[key] = val;

        /* Highlight modified */
        var row = document.querySelector('#val-params-body .wd-param-row[data-key="' + key + '"]');
        if (row) {
          if (val !== _parameterDefaults[key]) row.classList.add('modified');
          else row.classList.remove('modified');
        }
      };
      input.addEventListener(input.type === 'checkbox' ? 'change' : 'input', handler);
    });

    document.querySelectorAll('.val-param-reset').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-key');
        var defVal = _parameterDefaults[key];
        _parameterValues[key] = defVal;
        var input = document.querySelector('.val-param-ctrl[data-key="' + key + '"]');
        if (input) {
          if (input.type === 'checkbox') input.checked = defVal;
          else input.value = defVal;
        }
        var row = document.querySelector('#val-params-body .wd-param-row[data-key="' + key + '"]');
        if (row) row.classList.remove('modified');
      });
    });
  }

  /* ── Handle Run ───────────────────────────────────────────── */
  function _handleRun() {
    var stratId = document.getElementById('val-strategy').value;
    var symbol = (document.getElementById('val-symbol').value || '').trim().toUpperCase();
    var workerId = document.getElementById('val-worker').value;
    var month = parseInt(document.getElementById('val-month').value);
    var year = parseInt(document.getElementById('val-year').value);
    var lot = parseFloat(document.getElementById('val-lot').value);
    var barSize = parseFloat(document.getElementById('val-barsize').value);
    var maxBars = parseInt(document.getElementById('val-maxbars').value);
    var spread = parseFloat(document.getElementById('val-spread').value);
    var comm = parseFloat(document.getElementById('val-comm').value);

    if (!stratId) { ToastManager.show('Select a strategy.', 'warning'); return; }
    if (!symbol) { ToastManager.show('Enter a symbol.', 'warning'); return; }
    if (!workerId) { ToastManager.show('Select a worker VM.', 'warning'); return; }
    if (!barSize || barSize <= 0) { ToastManager.show('Bar Size Points must be > 0.', 'warning'); return; }

    /* Build strategy_parameters from edited values */
    var stratParams = {};
    for (var k in _parameterValues) {
      stratParams[k] = _parameterValues[k];
    }

    var payload = {
      strategy_id: stratId,
      worker_id: workerId,
      symbol: symbol,
      month: month,
      year: year,
      lot_size: lot,
      bar_size_points: barSize,
      max_bars_memory: maxBars,
      spread_points: spread,
      commission_per_lot: comm,
      strategy_parameters: stratParams,
    };

    var runBtn = document.getElementById('val-run-btn');
    runBtn.disabled = true;
    runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting\u2026';

    fetch('/api/validation/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (data.ok) {
        ToastManager.show('Validation job created: ' + data.job_id, 'success');
        _fetchJobs();
      } else {
        ToastManager.show('Failed: ' + (data.detail || JSON.stringify(data)), 'error');
      }
      runBtn.disabled = false;
      runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Validation';
    }).catch(function (e) {
      ToastManager.show('Error: ' + e.message, 'error');
      runBtn.disabled = false;
      runBtn.innerHTML = '<i class="fa-solid fa-play"></i> Run Validation';
    });
  }

  /* ── Fetch Jobs ───────────────────────────────────────────── */
  function _fetchJobs() {
    if (_currentView === 'results') return; /* don't overwrite results view */
    fetch('/api/validation/jobs?limit=50').then(function (r) { return r.json(); }).then(function (data) {
      var jobs = data.jobs || [];
      _renderJobsList(jobs);
    }).catch(function () {});
  }

  /* ── Render Jobs List ─────────────────────────────────────── */
  function _renderJobsList(jobs) {
    var el = document.getElementById('val-jobs-content');
    if (!el) return;

    if (jobs.length === 0) {
      el.innerHTML = _emptyState('fa-flask-vial', 'No Validation Jobs', 'Create your first backtest above.');
      return;
    }

    var html = '<div style="font-weight:600;font-size:13px;margin-bottom:12px;">Validation History (' + jobs.length + ')</div>';
    html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
    html += '<th>Job ID</th><th>Strategy</th><th>Symbol</th><th>Period</th><th>Worker</th><th>Status</th><th>Progress</th><th>Net P&L</th><th>Trades</th><th>Created</th><th></th>';
    html += '</tr></thead><tbody>';

    jobs.forEach(function (j) {
      var stateClass = j.state === 'completed' ? 'online' : j.state === 'failed' ? 'error' : j.state === 'running' ? 'warning' : 'stale';
      var netPnl = '\u2014';
      var tradeCount = '\u2014';
      if (j.summary) {
        netPnl = _fmtMoney(j.summary.net_pnl);
        tradeCount = String(j.summary.total_trades);
      }
      var created = j.created_at ? j.created_at.replace('T', ' ').substring(0, 16) : '\u2014';
      var period = MONTHS[(j.month || 1) - 1] + ' ' + j.year;

      var progressBar = '';
      if (j.state === 'running') {
        progressBar = '<div style="width:60px;height:4px;background:var(--border-primary);border-radius:2px;overflow:hidden;">' +
          '<div style="width:' + (j.progress || 0) + '%;height:100%;background:var(--accent);transition:width 0.3s;"></div></div>' +
          '<div style="font-size:9px;color:var(--text-muted);margin-top:2px;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (j.progress_message || '') + '</div>';
      } else {
        progressBar = '<span class="mono" style="font-size:10px;">' + (j.progress || 0) + '%</span>';
      }

      var pnlClass = j.summary ? ((j.summary.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger') : '';

      var actions = '';
      if (j.state === 'completed') {
        actions = '<button class="wd-btn wd-btn-ghost val-view-btn" data-jobid="' + j.job_id + '" style="font-size:10px;padding:3px 8px;" title="View Results"><i class="fa-solid fa-eye"></i></button>';
      } else if (j.state === 'running') {
        actions = '<button class="wd-btn wd-btn-ghost val-stop-btn" data-jobid="' + j.job_id + '" style="font-size:10px;padding:3px 8px;color:var(--danger);" title="Stop"><i class="fa-solid fa-stop"></i></button>';
      }
      actions += ' <button class="wd-btn wd-btn-ghost val-del-btn" data-jobid="' + j.job_id + '" style="font-size:10px;padding:3px 8px;color:var(--danger);" title="Delete"><i class="fa-solid fa-trash"></i></button>';

      html += '<tr>' +
        '<td class="mono" style="font-size:10px;color:var(--accent);cursor:pointer;" onclick="ValidationRenderer._viewJob(\'' + j.job_id + '\')">' + j.job_id + '</td>' +
        '<td class="mono" style="font-size:10.5px;">' + (j.strategy_name || j.strategy_id) + '</td>' +
        '<td class="mono">' + j.symbol + '</td>' +
        '<td class="mono" style="font-size:10.5px;">' + period + '</td>' +
        '<td class="mono" style="font-size:10px;">' + j.worker_id + '</td>' +
        '<td>' + _statPill(j.state.toUpperCase(), stateClass) + '</td>' +
        '<td>' + progressBar + '</td>' +
        '<td class="mono ' + pnlClass + '">' + netPnl + '</td>' +
        '<td class="mono">' + tradeCount + '</td>' +
        '<td class="mono" style="font-size:10px;">' + created + '</td>' +
        '<td style="white-space:nowrap;">' + actions + '</td></tr>';
    });

    html += '</tbody></table></div>';
    el.innerHTML = html;

    /* Attach button events */
    document.querySelectorAll('.val-view-btn').forEach(function (btn) {
      btn.addEventListener('click', function () { _viewJob(btn.getAttribute('data-jobid')); });
    });
    document.querySelectorAll('.val-stop-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        fetch('/api/validation/jobs/' + btn.getAttribute('data-jobid') + '/stop', { method: 'POST' })
          .then(function () { ToastManager.show('Stop sent.', 'info'); _fetchJobs(); });
      });
    });
    document.querySelectorAll('.val-del-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var jid = btn.getAttribute('data-jobid');
        ModalManager.show({
          title: 'Delete Validation Job', type: 'danger',
          bodyHtml: '<p>Delete job <strong>' + jid + '</strong> and all results?</p>',
          confirmText: 'Delete',
          onConfirm: function () {
            fetch('/api/validation/jobs/' + jid, { method: 'DELETE' })
              .then(function () { ToastManager.show('Deleted.', 'success'); _fetchJobs(); });
          }
        });
      });
    });
  }

  /* ── View Job Results ─────────────────────────────────────── */
  function _viewJob(jobId) {
    _currentJobId = jobId;
    _currentView = 'results';
    _destroyCharts();

    var resultsEl = document.getElementById('val-results-content');
    var listEl = document.getElementById('val-jobs-content');
    var createEl = document.getElementById('val-create-panel');
    var paramsEl = document.getElementById('val-params-panel');
    if (!resultsEl) return;

    resultsEl.style.display = '';
    resultsEl.innerHTML = _spinner();
    if (listEl) listEl.style.display = 'none';
    if (createEl) createEl.style.display = 'none';
    if (paramsEl) paramsEl.style.display = 'none';

    fetch('/api/validation/jobs/' + jobId).then(function (r) { return r.json(); }).then(function (data) {
      if (!data.ok || !data.job) {
        resultsEl.innerHTML = '<div style="color:var(--danger);padding:20px;">Job not found.</div>';
        return;
      }
      _renderResults(data.job);
    }).catch(function (e) {
      resultsEl.innerHTML = '<div style="color:var(--danger);padding:20px;">Error: ' + e.message + '</div>';
    });
  }

  function _backToList() {
    _currentJobId = null;
    _currentView = 'list';
    _destroyCharts();
    var resultsEl = document.getElementById('val-results-content');
    var listEl = document.getElementById('val-jobs-content');
    var createEl = document.getElementById('val-create-panel');
    var paramsEl = document.getElementById('val-params-panel');
    if (resultsEl) { resultsEl.style.display = 'none'; resultsEl.innerHTML = ''; }
    if (listEl) listEl.style.display = '';
    if (createEl) createEl.style.display = '';
    /* params panel visibility depends on strategy selection */
    if (paramsEl && _selectedStrategy) paramsEl.style.display = '';
    _fetchJobs();
  }

  /* ── Render Results ───────────────────────────────────────── */
  function _renderResults(job) {
    var el = document.getElementById('val-results-content');
    if (!el) return;

    var s = job.summary || {};
    var trades = job.trades || [];
    var eqCurve = job.equity_curve || [];
    var period = MONTHS[(job.month || 1) - 1] + ' ' + job.year;

    var html = '';

    /* Back button + header */
    html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;">';
    html += '<button class="wd-back-btn" id="val-back-btn"><i class="fa-solid fa-arrow-left"></i> Back</button>';
    html += '<div style="flex:1;min-width:200px;">';
    html += '<div style="font-size:15px;font-weight:600;">' + (job.strategy_name || job.strategy_id) + ' \u2014 ' + job.symbol + ' ' + period + '</div>';
    html += '<div style="font-size:11px;color:var(--text-muted);">Job: ' + job.job_id + ' | Worker: ' + job.worker_id + ' | Bar: ' + job.bar_size_points + 'pt | Lot: ' + job.lot_size;
    if (job.spread_points > 0) html += ' | Spread: ' + job.spread_points + 'pt';
    if (job.commission_per_lot > 0) html += ' | Comm: $' + job.commission_per_lot + '/lot';
    html += '</div>';
    html += '</div>';
    html += '<div style="display:flex;gap:8px;">';
    html += '<button class="wd-btn wd-btn-ghost" id="val-dl-json" style="font-size:11px;"><i class="fa-solid fa-download"></i> JSON</button>';
    html += '<button class="wd-btn wd-btn-ghost" id="val-dl-csv" style="font-size:11px;"><i class="fa-solid fa-download"></i> CSV</button>';
    html += '</div></div>';

    /* Error state */
    if (job.state === 'failed') {
      html += '<div style="padding:20px;background:var(--danger-dim);border-radius:8px;color:var(--danger);margin-bottom:16px;">' +
        '<i class="fa-solid fa-triangle-exclamation" style="margin-right:8px;"></i>' +
        '<strong>Failed:</strong> ' + (job.error || 'Unknown error') + '</div>';
    }

    /* Key metrics */
    html += '<div style="display:flex;flex-wrap:wrap;gap:20px;padding:16px 0;border-bottom:1px solid var(--border);margin-bottom:20px;">';
    html += _metricItem('Net P&L', _fmtMoney(s.net_pnl), (s.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger');
    html += _metricItem('Gross Profit', _fmtMoney(s.gross_profit), 'text-success');
    html += _metricItem('Gross Loss', _fmtMoney(s.gross_loss), 'text-danger');
    html += _metricItem('Profit Factor', String(s.profit_factor || 0), (s.profit_factor || 0) >= 1 ? 'text-success' : '');
    html += _metricItem('Win Rate', _fmtPct(s.win_rate));
    html += _metricItem('Expectancy', _fmtMoney(s.expectancy), (s.expectancy || 0) >= 0 ? 'text-success' : 'text-danger');
    html += _metricItem('Max DD ($)', _fmtMoney(-Math.abs(s.max_drawdown_usd || 0)), 'text-danger');
    html += _metricItem('Max DD (%)', _fmtPct(s.max_drawdown_pct), 'text-danger');
    html += _metricItem('Sharpe', String(s.sharpe_estimate || 0));
    html += _metricItem('Sortino', String(s.sortino_estimate || 0));
    html += _metricItem('Recovery', String(s.recovery_factor || 0));
    html += _metricItem('Trades', String(s.total_trades || 0));
    html += _metricItem('Wins / Losses', (s.wins || 0) + ' / ' + (s.losses || 0));
    html += _metricItem('Avg Trade', _fmtMoney(s.avg_trade), (s.avg_trade || 0) >= 0 ? 'text-success' : 'text-danger');
    html += _metricItem('Avg Winner', _fmtMoney(s.avg_winner), 'text-success');
    html += _metricItem('Avg Loser', _fmtMoney(s.avg_loser), 'text-danger');
    html += _metricItem('Best Trade', _fmtMoney(s.best_trade), 'text-success');
    html += _metricItem('Worst Trade', _fmtMoney(s.worst_trade), 'text-danger');
    html += _metricItem('Avg Bars', String(s.avg_bars_held || 0));
    html += _metricItem('Consec Wins', String(s.max_consec_wins || 0), 'text-success');
    html += _metricItem('Consec Losses', String(s.max_consec_losses || 0), 'text-danger');
    html += '</div>';

    /* Equity Chart */
    if (eqCurve.length > 1) {
      html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">Equity Curve</div>';
      html += '<div class="chart-container"><div class="chart-wrapper" id="val-eq-wrap"><canvas id="val-eq-chart"></canvas></div></div></div>';

      /* Drawdown Chart */
      html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">Drawdown</div>';
      html += '<div class="chart-container"><div class="chart-wrapper" id="val-dd-wrap"><canvas id="val-dd-chart"></canvas></div></div></div>';
    }

    /* Trade Table */
    if (trades.length > 0) {
      html += '<div style="margin-bottom:20px;"><div style="font-weight:600;font-size:13px;margin-bottom:8px;">' + trades.length + ' Trades</div>';
      html += '<div class="compact-fleet-wrapper"><table class="compact-fleet-table"><thead><tr>';
      html += '<th>#</th><th>Dir</th><th>Entry</th><th>Exit</th><th>SL</th><th>TP</th><th>P&L</th><th>Comm</th><th>Net</th><th>Bars</th><th>Reason</th><th>Bal</th>';
      html += '</tr></thead><tbody>';
      trades.forEach(function (t) {
        var pc = (t.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger';
        html += '<tr>' +
          '<td class="mono">' + t.trade_id + '</td>' +
          '<td>' + _statPill(t.direction.toUpperCase(), t.direction === 'long' ? 'online' : 'error') + '</td>' +
          '<td class="mono">' + t.entry_price + '</td>' +
          '<td class="mono">' + t.exit_price + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.sl !== null && t.sl !== undefined ? t.sl : '\u2014') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.tp !== null && t.tp !== undefined ? t.tp : '\u2014') + '</td>' +
          '<td class="mono ' + pc + '">' + _fmtMoney(t.profit) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + _fmtMoney(t.commission || 0) + '</td>' +
          '<td class="mono ' + pc + '">' + _fmtMoney(t.net_pnl) + '</td>' +
          '<td class="mono">' + (t.bars_held || 0) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.exit_reason || '\u2014') + '</td>' +
          '<td class="mono" style="font-size:10px;">' + _fmtMoney(t.balance_after) + '</td>' +
          '</tr>';
      });
      html += '</tbody></table></div></div>';
    } else if (job.state === 'completed') {
      html += _emptyState('fa-receipt', 'No Trades Generated', 'Strategy produced no signals during this period.');
    }

    el.innerHTML = html;

    /* Back button */
    document.getElementById('val-back-btn').addEventListener('click', _backToList);

    /* Download buttons */
    document.getElementById('val-dl-json').addEventListener('click', function () {
      _downloadJSON(job);
    });
    document.getElementById('val-dl-csv').addEventListener('click', function () {
      _downloadCSV(trades, job);
    });

    /* Render charts */
    if (eqCurve.length > 1) {
      _renderEquityChart(eqCurve);
      _renderDrawdownChart(eqCurve);
    }
  }

  /* ── Charts ───────────────────────────────────────────────── */
  function _renderEquityChart(eqCurve) {
    var canvas = document.getElementById('val-eq-chart');
    if (!canvas) return;
    var labels = eqCurve.map(function (p, i) { return i; });
    var values = eqCurve.map(function (p) { return p.equity; });
    var ctx = canvas.getContext('2d');
    var g = ctx.createLinearGradient(0, 0, 0, 280);
    g.addColorStop(0, 'rgba(6,182,212,0.2)');
    g.addColorStop(1, 'rgba(6,182,212,0)');
    _charts.valEq = new Chart(ctx, {
      type: 'line',
      data: { labels: labels, datasets: [{ data: values, borderColor: ChartHelper.accentColor(), backgroundColor: g, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0 }] },
      options: ChartHelper.baseLineOpts({ scales: { x: { display: false }, y: { ticks: { callback: function (v) { return '$' + v.toFixed(0); } } } } })
    });
  }

  function _renderDrawdownChart(eqCurve) {
    var canvas = document.getElementById('val-dd-chart');
    if (!canvas) return;
    var values = eqCurve.map(function (p) { return p.equity; });
    var labels = eqCurve.map(function (p, i) { return i; });
    var peak = 0, dd = [];
    values.forEach(function (v) { if (v > peak) peak = v; dd.push(peak > 0 ? -((peak - v) / peak * 100) : 0); });
    var ctx = canvas.getContext('2d');
    var g = ctx.createLinearGradient(0, 0, 0, 280);
    g.addColorStop(0, 'rgba(239,68,68,0)');
    g.addColorStop(1, 'rgba(239,68,68,0.25)');
    _charts.valDd = new Chart(ctx, {
      type: 'line',
      data: { labels: labels, datasets: [{ data: dd, borderColor: ChartHelper.dangerColor(), backgroundColor: g, borderWidth: 1.5, fill: true, tension: 0.3, pointRadius: 0 }] },
      options: ChartHelper.baseLineOpts({ scales: { x: { display: false }, y: { ticks: { callback: function (v) { return v.toFixed(1) + '%'; } } } } })
    });
  }

  /* ── Downloads ─────────────────────────────────────────────── */
  function _downloadJSON(job) {
    var data = {
      job_id: job.job_id,
      strategy: job.strategy_name || job.strategy_id,
      symbol: job.symbol,
      period: MONTHS[(job.month || 1) - 1] + ' ' + job.year,
      config: {
        lot_size: job.lot_size,
        bar_size_points: job.bar_size_points,
        max_bars_memory: job.max_bars_memory,
        spread_points: job.spread_points,
        commission_per_lot: job.commission_per_lot,
      },
      summary: job.summary,
      trades: job.trades,
      equity_curve: job.equity_curve,
    };
    var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'validation_' + job.job_id + '.json';
    a.click();
    ToastManager.show('JSON report downloaded.', 'success');
  }

  function _downloadCSV(trades, job) {
    if (!trades || trades.length === 0) { ToastManager.show('No trades to export.', 'info'); return; }
    var cols = ['trade_id','direction','entry_price','exit_price','sl','tp','profit','commission','net_pnl','bars_held','exit_reason','balance_after','entry_bar','exit_bar'];
    var csv = cols.join(',') + '\n';
    trades.forEach(function (t) {
      csv += cols.map(function (c) { return '"' + (t[c] !== undefined && t[c] !== null ? t[c] : '') + '"'; }).join(',') + '\n';
    });
    var blob = new Blob([csv], { type: 'text/csv' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'validation_trades_' + job.job_id + '.csv';
    a.click();
    ToastManager.show('CSV exported (' + trades.length + ' trades).', 'success');
  }

  /* ── Lifecycle ────────────────────────────────────────────── */
  function destroy() {
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
    _destroyCharts();
    _currentView = 'list';
    _currentJobId = null;
    _selectedStrategy = null;
    _parameterValues = {};
    _parameterDefaults = {};
  }

  return {
    render: render,
    destroy: destroy,
    _viewJob: _viewJob,
    _backToList: _backToList,
  };
})();
```

---

## `app/services/mainServices.py`

```python
"""
JINNI GRID — Combined Runtime Services
app/services/mainServices.py

Portfolio computations use ISO date strings from the DB (not raw Unix timestamps).
Equity snapshots throttled to max once per 10 seconds.
All monetary values rounded to 2 decimals.
"""

import logging
import math
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.config import Config
from app.persistence import (
    init_db,
    save_worker, get_all_workers_db, get_worker_db,
    save_deployment, get_all_deployments_db, get_deployment_db,
    update_deployment_state_db,
    log_event_db, get_events_db,
    save_trade_db, get_all_trades_db,
    save_equity_snapshot_db, get_equity_snapshots_db, clear_equity_snapshots_db,
    get_setting, get_all_settings, save_setting, save_settings_bulk,
    delete_all_trades_db, delete_trades_by_strategy_db,
    delete_trades_by_worker_db,
    delete_strategy_full_db, remove_worker_db, remove_stale_workers_db,
    clear_events_db, get_system_stats_db, full_system_reset_db,
)

log = logging.getLogger("jinni.services")


def _r2(v):
    if v is None:
        return 0.0
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return 0.0


# ── Timestamp helpers (for portfolio date grouping) ─────────

def _trade_exit_date(t: dict) -> str:
    """Extract YYYY-MM-DD from a trade record, handling all formats."""
    # 1. ISO exit_time string (set by persistence layer)
    et = t.get("exit_time")
    if et and isinstance(et, str) and len(et) >= 10 and et[4:5] == "-":
        return et[:10]
    # 2. Unix timestamp in exit_time_unix
    etu = t.get("exit_time_unix")
    if etu:
        try:
            v = int(etu)
            if v > 946684800:
                return datetime.fromtimestamp(
                    v, tz=timezone.utc
                ).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            pass
    # 3. created_at from DB
    ca = t.get("created_at")
    if ca and isinstance(ca, str) and len(ca) >= 10:
        return ca[:10]
    return ""


def _trade_exit_month(t: dict) -> str:
    d = _trade_exit_date(t)
    return d[:7] if len(d) >= 7 else ""


# =============================================================================
# Command Queue
# =============================================================================

_command_queues: dict = {}
_command_lock = threading.Lock()


def enqueue_command(worker_id: str, command_type: str, payload: dict) -> dict:
    cmd_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    cmd = {"command_id": cmd_id, "worker_id": worker_id,
           "command_type": command_type, "payload": payload,
           "state": "pending", "created_at": now.isoformat(), "acked_at": None}
    with _command_lock:
        _command_queues.setdefault(worker_id, []).append(cmd)
    log_event_db("command", "enqueued", f"{command_type} for {worker_id}",
                 worker_id=worker_id, data={"command_id": cmd_id})
    return cmd


def poll_commands(worker_id: str) -> list:
    now = datetime.now(timezone.utc)
    with _command_lock:
        queue = _command_queues.get(worker_id, [])
        pending = [c for c in queue if c["state"] == "pending"]
        _command_queues[worker_id] = [
            c for c in queue
            if c["state"] == "pending" or (
                c.get("acked_at") and
                (now - datetime.fromisoformat(c["acked_at"])
                 ).total_seconds() < 300
            )
        ]
    return pending


def ack_command(worker_id: str, command_id: str) -> dict:
    now = datetime.now(timezone.utc)
    with _command_lock:
        for cmd in _command_queues.get(worker_id, []):
            if cmd["command_id"] == command_id:
                cmd["state"] = "acknowledged"
                cmd["acked_at"] = now.isoformat()
                return {"ok": True, "command": cmd}
    return {"ok": False, "error": "Command not found."}


# =============================================================================
# Deployment Registry
# =============================================================================

VALID_STATES = {
    "queued", "sent_to_worker", "acknowledged_by_worker", "loading_strategy",
    "fetching_ticks", "generating_initial_bars", "warming_up", "running",
    "stopped", "failed",
}


def create_deployment(config: dict) -> dict:
    deployment_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)
    settings = get_all_settings()
    record = {
        "deployment_id": deployment_id,
        "strategy_id": config["strategy_id"],
        "worker_id": config["worker_id"],
        "symbol": config.get("symbol") or settings.get(
            "default_symbol", "XAUUSD"),
        "tick_lookback_value": config.get("tick_lookback_value", 30),
        "tick_lookback_unit": config.get("tick_lookback_unit", "minutes"),
        "bar_size_points": config.get("bar_size_points") or float(
            settings.get("default_bar_size", "100")),
        "max_bars_in_memory": config.get("max_bars_in_memory", 500),
        "lot_size": config.get("lot_size") or float(
            settings.get("default_lot_size", "0.01")),
        "strategy_parameters": config.get("strategy_parameters") or {},
        "state": "queued",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "last_error": None,
    }
    save_deployment(deployment_id, record)
    log_event_db("deployment", "created",
                 f"Deployment {deployment_id} created",
                 worker_id=config["worker_id"],
                 strategy_id=config["strategy_id"],
                 deployment_id=deployment_id, symbol=record["symbol"])
    return {"ok": True, "deployment_id": deployment_id,
            "deployment": record}


def get_all_deployments() -> list:
    return get_all_deployments_db()


def get_deployment(deployment_id: str):
    return get_deployment_db(deployment_id)


def update_deployment_state(deployment_id: str, state: str,
                             error: str = None) -> dict:
    if state not in VALID_STATES:
        return {"ok": False, "error": f"Invalid state: {state}"}
    update_deployment_state_db(deployment_id, state, error)
    log_event_db("deployment", "state_change",
                 f"{deployment_id} -> {state}",
                 deployment_id=deployment_id,
                 data={"state": state, "error": error},
                 level="ERROR" if state == "failed" else "INFO")
    return {"ok": True, "deployment": get_deployment_db(deployment_id)}


def stop_deployment(deployment_id: str) -> dict:
    return update_deployment_state(deployment_id, "stopped")


# =============================================================================
# Worker Registry
# =============================================================================

_workers_cache: dict = {}
_worker_lock = threading.Lock()
_last_snapshot_time: float = 0.0  # throttle equity snapshots
_SNAPSHOT_INTERVAL = 10.0         # seconds between snapshots


def _load_workers_from_db():
    global _workers_cache
    db_workers = get_all_workers_db()
    with _worker_lock:
        for w in db_workers:
            wid = w["worker_id"]
            hb_at = w.get("last_heartbeat_at")
            if hb_at:
                try:
                    dt = datetime.fromisoformat(hb_at)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            w["_last_heartbeat_dt"] = dt
            _workers_cache[wid] = w


def process_heartbeat(payload: dict) -> dict:
    global _last_snapshot_time
    worker_id = payload["worker_id"].strip()
    now = datetime.now(timezone.utc)
    is_new = False
    with _worker_lock:
        if worker_id not in _workers_cache:
            is_new = True
        _workers_cache[worker_id] = {
            **payload, "worker_id": worker_id,
            "last_heartbeat_at": now.isoformat(),
            "_last_heartbeat_dt": now,
        }
    save_worker(worker_id, {**payload, "last_heartbeat_at": now.isoformat()})
    if is_new:
        log_event_db("worker", "registered",
                     f"Worker {worker_id} first heartbeat",
                     worker_id=worker_id)

    # Throttled equity snapshot (max once per 10s, not every heartbeat)
    mono = time.monotonic()
    if mono - _last_snapshot_time >= _SNAPSHOT_INTERVAL:
        _last_snapshot_time = mono
        _compute_equity_snapshot()

    return {"ok": True, "worker_id": worker_id, "registered": is_new,
            "server_time": now.isoformat()}


def get_all_workers() -> list:
    fleet_config = Config.get_fleet_config()
    timeout_setting = get_setting("worker_timeout_seconds")
    if timeout_setting:
        offline_threshold = int(timeout_setting)
        stale_threshold = max(10, offline_threshold // 3)
    else:
        stale_threshold = fleet_config.get("stale_threshold_seconds", 30)
        offline_threshold = fleet_config.get("offline_threshold_seconds", 90)

    now = datetime.now(timezone.utc)
    result = []
    with _worker_lock:
        for wid, rec in _workers_cache.items():
            hb_dt = rec.get("_last_heartbeat_dt", now)
            age = round((now - hb_dt).total_seconds(), 1)
            reported = rec.get("reported_state",
                               rec.get("state", "online"))
            if age >= offline_threshold:
                effective = "offline"
            elif age >= stale_threshold:
                effective = "stale"
            else:
                effective = reported

            result.append({
                "worker_id": rec.get("worker_id", wid),
                "worker_name": rec.get("worker_name"),
                "host": rec.get("host"),
                "state": effective, "reported_state": reported,
                "last_heartbeat_at": rec.get("last_heartbeat_at"),
                "heartbeat_age_seconds": age,
                "agent_version": rec.get("agent_version"),
                "mt5_state": rec.get("mt5_state"),
                "account_id": rec.get("account_id"),
                "broker": rec.get("broker"),
                "active_strategies": rec.get("active_strategies") or [],
                "open_positions_count": rec.get("open_positions_count", 0),
                "floating_pnl": _r2(rec.get("floating_pnl")),
                "account_balance": _r2(rec.get("account_balance")),
                "account_equity": _r2(rec.get("account_equity")),
                "errors": rec.get("errors") or [],
                "total_ticks": rec.get("total_ticks", 0),
                "total_bars": rec.get("total_bars", 0),
                "current_bars_in_memory": rec.get("current_bars_in_memory", 0),
                "on_bar_calls": rec.get("on_bar_calls", 0),
                "signal_count": rec.get("signal_count", 0),
                "last_bar_time": rec.get("last_bar_time"),
                "current_price": rec.get("current_price"),
            })
    return result


def get_fleet_summary() -> dict:
    workers = get_all_workers()
    counts = {"online_workers": 0, "stale_workers": 0,
              "offline_workers": 0, "error_workers": 0,
              "warning_workers": 0}
    for w in workers:
        s = w["state"]
        if s in ("online", "running", "idle"):
            counts["online_workers"] += 1
        elif s == "stale":
            counts["stale_workers"] += 1
        elif s == "offline":
            counts["offline_workers"] += 1
        elif s == "error":
            counts["error_workers"] += 1
    counts["total_workers"] = len(workers)
    return counts


# =============================================================================
# Equity Snapshot Engine (throttled)
# =============================================================================

def _compute_equity_snapshot():
    total_balance = 0.0
    total_equity = 0.0
    total_floating = 0.0
    open_pos = 0
    has_account = False

    with _worker_lock:
        for w in _workers_cache.values():
            ab = w.get("account_balance")
            ae = w.get("account_equity")
            if ab is not None and float(ab or 0) > 0:
                total_balance += float(ab)
                has_account = True
            if ae is not None and float(ae or 0) > 0:
                total_equity += float(ae)
                has_account = True
            total_floating += float(w.get("floating_pnl") or 0)
            open_pos += int(w.get("open_positions_count") or 0)

    # Sum realized PnL from DB (use a fast count, not loading all rows)
    trades = get_all_trades_db(limit=50000)
    realized = sum(_r2(t.get("profit")) for t in trades)

    if not has_account:
        total_balance = realized
        total_equity = realized + total_floating

    # Only save if we have meaningful data (avoid 0-equity pollution)
    if _r2(total_equity) != 0 or _r2(total_balance) != 0 or open_pos > 0:
        try:
            save_equity_snapshot_db(
                balance=_r2(total_balance),
                equity=_r2(total_equity),
                floating_pnl=_r2(total_floating),
                open_positions=open_pos,
                cumulative_pnl=_r2(realized),
            )
        except Exception as e:
            print(f"[PORTFOLIO] Snapshot save failed: {e}")

# =============================================================================
# Portfolio Engine (correct date handling + extended stats)
# =============================================================================

def _compute_trade_stats(trades: list) -> dict:
    """Comprehensive stats from trade records."""
    empty = {
        "total_trades": 0, "wins": 0, "losses": 0,
        "gross_profit": 0, "gross_loss": 0, "net_pnl": 0,
        "win_rate": 0, "profit_factor": 0, "expectancy": 0,
        "avg_trade": 0, "avg_winner": 0, "avg_loser": 0,
        "best_trade": 0, "worst_trade": 0,
        "max_drawdown_pct": 0, "max_drawdown_usd": 0,
        "recovery_factor": 0, "sharpe_estimate": 0,
        "sortino_estimate": 0, "avg_bars_held": 0,
        "max_consec_wins": 0, "max_consec_losses": 0,
        "best_day": None, "worst_day": None, "trades_per_day": 0,
    }
    if not trades:
        return empty

    profits = [_r2(t.get("profit")) for t in trades]
    n = len(profits)
    win_p = [p for p in profits if p > 0]
    loss_p = [p for p in profits if p <= 0]
    bars = [int(t.get("bars_held", 0) or 0) for t in trades]

    gp = _r2(sum(win_p))
    gl = _r2(sum(loss_p))
    net = _r2(gp + gl)

    # Max drawdown (peak-to-trough, capped at 100%)
    cum, peak, dd_usd, dd_pct = 0.0, 0.0, 0.0, 0.0
    for p in profits:
        cum += p
        if cum > peak:
            peak = cum
        d = peak - cum  # always >= 0
        dd_usd = max(dd_usd, d)
        # Only compute % when peak is meaningfully positive
        if peak > 0.01:
            dp = min((d / peak) * 100, 100.0)  # cap at 100%
            dd_pct = max(dd_pct, dp)

    # Sharpe
    mean = net / n
    var = sum((p - mean) ** 2 for p in profits) / (n - 1) if n > 1 else 0
    std = math.sqrt(var) if var > 0 else 0
    sharpe = _r2(mean / std * math.sqrt(252)) if std > 0 else 0

    # Sortino
    down = [p for p in profits if p < 0]
    if down and len(down) > 1:
        dvar = sum(p ** 2 for p in down) / len(down)
        dstd = math.sqrt(dvar) if dvar > 0 else 0
        sortino = _r2(mean / dstd * math.sqrt(252)) if dstd > 0 else 0
    else:
        sortino = 0

    # Consecutive
    mcw, mcl, cw, cl = 0, 0, 0, 0
    for p in profits:
        if p > 0:
            cw += 1; cl = 0
        else:
            cl += 1; cw = 0
        mcw = max(mcw, cw)
        mcl = max(mcl, cl)

    # ★ FIX: Daily grouping uses _trade_exit_date (handles Unix timestamps)
    daily = {}
    for t in trades:
        d = _trade_exit_date(t)
        if not d:
            continue
        daily.setdefault(d, 0.0)
        daily[d] += float(t.get("profit", 0) or 0)

    best_day = worst_day = None
    if daily:
        bd = max(daily.items(), key=lambda x: x[1])
        wd = min(daily.items(), key=lambda x: x[1])
        best_day = {"date": bd[0], "pnl": _r2(bd[1])}
        worst_day = {"date": wd[0], "pnl": _r2(wd[1])}

    num_days = max(len(daily), 1)
    agl = abs(gl)
    pf = _r2(gp / agl) if agl > 0 else (999.99 if gp > 0 else 0)
    rf = _r2(net / dd_usd) if dd_usd > 0 else 0

    return {
        "total_trades": n,
        "wins": len(win_p), "losses": len(loss_p),
        "gross_profit": gp, "gross_loss": gl, "net_pnl": net,
        "win_rate": _r2(len(win_p) / n * 100) if n else 0,
        "profit_factor": pf,
        "expectancy": _r2(net / n) if n else 0,
        "avg_trade": _r2(net / n) if n else 0,
        "avg_winner": _r2(gp / len(win_p)) if win_p else 0,
        "avg_loser": _r2(gl / len(loss_p)) if loss_p else 0,
        "best_trade": _r2(max(profits)),
        "worst_trade": _r2(min(profits)),
        "max_drawdown_pct": _r2(dd_pct),
        "max_drawdown_usd": _r2(dd_usd),
        "recovery_factor": rf,
        "sharpe_estimate": sharpe,
        "sortino_estimate": sortino,
        "avg_bars_held": _r2(sum(bars) / n) if n else 0,
        "max_consec_wins": mcw,
        "max_consec_losses": mcl,
        "best_day": best_day, "worst_day": worst_day,
        "trades_per_day": _r2(n / num_days),
    }


def get_portfolio_summary(strategy_id=None, worker_id=None,
                           symbol=None) -> dict:
    trades = get_all_trades_db(limit=50000, strategy_id=strategy_id,
                                worker_id=worker_id, symbol=symbol)
    workers = get_all_workers()
    tb = te = tf = 0.0
    tp = 0
    has_acc = False

    for w in workers:
        if worker_id and w.get("worker_id") != worker_id:
            continue
        ab = w.get("account_balance", 0) or 0
        ae = w.get("account_equity", 0) or 0
        if ab > 0:
            tb += ab; has_acc = True
        if ae > 0:
            te += ae; has_acc = True
        tf += (w.get("floating_pnl") or 0)
        tp += (w.get("open_positions_count") or 0)

    stats = _compute_trade_stats(trades)

    if not has_acc:
        tb = stats["net_pnl"]
        te = stats["net_pnl"] + tf

    # Compute drawdown from equity snapshots if available (more accurate)
    snapshots = get_equity_snapshots_db(limit=5000)
    snap_dd_usd = 0.0
    snap_dd_pct = 0.0
    if snapshots:
        eq_vals = [s.get("equity", 0) for s in snapshots if (s.get("equity") or 0) > 0]
        if eq_vals:
            pk = 0.0
            for v in eq_vals:
                if v > pk:
                    pk = v
                d = pk - v
                if d > snap_dd_usd:
                    snap_dd_usd = d
                if pk > 0.01:
                    dp = min((d / pk) * 100, 100.0)
                    if dp > snap_dd_pct:
                        snap_dd_pct = dp

    # Use snapshot-based DD if available and meaningful, else trade-based
    final_dd_usd = snap_dd_usd if snap_dd_usd > 0 else stats["max_drawdown_usd"]
    final_dd_pct = snap_dd_pct if snap_dd_pct > 0 else stats["max_drawdown_pct"]

    # Current drawdown
    current_dd_pct = 0.0
    if snapshots:
        eq_vals = [s.get("equity", 0) for s in snapshots if (s.get("equity") or 0) > 0]
        if eq_vals:
            peak_eq = max(eq_vals)
            current_eq = eq_vals[-1]
            if peak_eq > 0.01:
                current_dd_pct = min(((peak_eq - current_eq) / peak_eq) * 100, 100.0)

    return {
        "total_balance": _r2(tb),
        "total_equity": _r2(te),
        "floating_pnl": _r2(tf),
        "open_positions": tp,
        "has_account_data": has_acc,
        "active_workers": len([w for w in workers
                               if w.get("state") in
                               ("online", "running")]),
        "max_drawdown_usd": _r2(final_dd_usd),
        "max_drawdown_pct": _r2(final_dd_pct),
        "current_drawdown_pct": _r2(current_dd_pct),
        "peak_equity": _r2(max(eq_vals) if snapshots and eq_vals else te),
        # All other stats from _compute_trade_stats (except DD which we override)
        "total_trades": stats["total_trades"],
        "wins": stats["wins"],
        "losses": stats["losses"],
        "gross_profit": stats["gross_profit"],
        "gross_loss": stats["gross_loss"],
        "net_pnl": stats["net_pnl"],
        "win_rate": stats["win_rate"],
        "profit_factor": stats["profit_factor"],
        "expectancy": stats["expectancy"],
        "avg_trade": stats["avg_trade"],
        "avg_winner": stats["avg_winner"],
        "avg_loser": stats["avg_loser"],
        "best_trade": stats["best_trade"],
        "worst_trade": stats["worst_trade"],
        "recovery_factor": _r2(stats["net_pnl"] / final_dd_usd) if final_dd_usd > 0 else 0,
        "sharpe_estimate": stats["sharpe_estimate"],
        "sortino_estimate": stats["sortino_estimate"],
        "avg_bars_held": stats["avg_bars_held"],
        "max_consec_wins": stats["max_consec_wins"],
        "max_consec_losses": stats["max_consec_losses"],
        "best_day": stats["best_day"],
        "worst_day": stats["worst_day"],
        "trades_per_day": stats["trades_per_day"],
    }


def get_equity_history() -> list:
    trades = get_all_trades_db(limit=50000)
    trade_curve = []
    if trades:
        sorted_t = sorted(trades, key=lambda t: t.get("id", 0))
        cum = 0.0
        for t in sorted_t:
            cum += _r2(t.get("profit"))
            ts = t.get("exit_time") or t.get("created_at") or ""
            label = str(ts)[-8:] if len(str(ts)) >= 8 else str(ts)
            trade_curve.append({
                "timestamp": str(ts),
                "equity": _r2(cum),
                "balance": _r2(cum),
                "floating_pnl": 0.0,
                "realized_pnl": _r2(cum),
                "label": label,
                "source": "trade",
            })

    # Periodic snapshots
    snapshots = get_equity_snapshots_db(limit=2000)
    snap_curve = []
    for s in snapshots:
        eq = _r2(s.get("equity", 0))
        bal = _r2(s.get("balance", 0))
        # Skip zero-equity snapshots (worker not initialized yet)
        if eq <= 0 and bal <= 0:
            continue
        ts = s.get("timestamp", "")
        label = ts[-8:] if len(ts) >= 8 else ts
        snap_curve.append({
            "timestamp": ts,
            "equity": eq,
            "balance": bal,
            "floating_pnl": _r2(s.get("floating_pnl", 0)),
            "realized_pnl": _r2(s.get("cumulative_pnl", 0)),
            "label": label,
            "source": "snapshot",
        })

    if snap_curve:
        # Downsample to one per minute
        result, last_min = [], ""
        for s in snap_curve:
            m = s["timestamp"][:16]
            if m != last_min:
                result.append(s)
                last_min = m
        return result if result else snap_curve

    if trade_curve:
        return trade_curve

    # No data at all — return empty (UI handles gracefully)
    return []

def get_portfolio_trades(strategy_id=None, worker_id=None,
                          symbol=None, limit=500) -> list:
    return get_all_trades_db(limit=limit, strategy_id=strategy_id,
                             worker_id=worker_id, symbol=symbol)


def get_portfolio_performance(strategy_id=None, worker_id=None,
                               symbol=None) -> dict:
    trades = get_all_trades_db(limit=50000, strategy_id=strategy_id,
                                worker_id=worker_id, symbol=symbol)
    if not trades:
        return {"daily": [], "monthly": [],
                "by_strategy": [], "by_worker": [], "by_symbol": []}

    # ★ FIX: Daily uses _trade_exit_date (converts Unix → YYYY-MM-DD)
    daily = {}
    for t in trades:
        d = _trade_exit_date(t)
        if not d:
            continue
        if d not in daily:
            daily[d] = {"date": d, "pnl": 0, "trades": 0, "wins": 0}
        daily[d]["pnl"] += float(t.get("profit", 0) or 0)
        daily[d]["trades"] += 1
        if float(t.get("profit", 0) or 0) > 0:
            daily[d]["wins"] += 1

    daily_list = sorted(daily.values(), key=lambda x: x["date"])
    cum = 0.0
    for d in daily_list:
        cum += d["pnl"]
        d["pnl"] = _r2(d["pnl"])
        d["cumulative"] = _r2(cum)

    # ★ FIX: Monthly uses _trade_exit_month
    monthly = {}
    for t in trades:
        m = _trade_exit_month(t)
        if not m:
            continue
        if m not in monthly:
            monthly[m] = {"month": m, "pnl": 0, "trades": 0, "wins": 0}
        monthly[m]["pnl"] += float(t.get("profit", 0) or 0)
        monthly[m]["trades"] += 1
        if float(t.get("profit", 0) or 0) > 0:
            monthly[m]["wins"] += 1

    monthly_list = sorted(monthly.values(), key=lambda x: x["month"])
    for m in monthly_list:
        m["pnl"] = _r2(m["pnl"])
        m["win_rate"] = _r2(
            m["wins"] / m["trades"] * 100
        ) if m["trades"] else 0

    # Breakdowns
    def _bk(key):
        bk = {}
        for t in trades:
            k = t.get(key, "")
            if not k:
                continue
            if k not in bk:
                bk[k] = {key: k, "trades": 0, "pnl": 0,
                         "wins": 0, "losses": 0, "total_bars": 0}
            bk[k]["trades"] += 1
            p = float(t.get("profit", 0) or 0)
            bk[k]["pnl"] += p
            bk[k]["total_bars"] += int(t.get("bars_held", 0) or 0)
            if p > 0:
                bk[k]["wins"] += 1
            else:
                bk[k]["losses"] += 1
        for v in bk.values():
            v["pnl"] = _r2(v["pnl"])
            v["win_rate"] = _r2(
                v["wins"] / v["trades"] * 100
            ) if v["trades"] else 0
            v["avg_bars"] = _r2(
                v["total_bars"] / v["trades"]
            ) if v["trades"] else 0
            ws = sum(float(t.get("profit", 0) or 0)
                     for t in trades
                     if t.get(key) == v[key]
                     and float(t.get("profit", 0) or 0) > 0)
            ls = sum(abs(float(t.get("profit", 0) or 0))
                     for t in trades
                     if t.get(key) == v[key]
                     and float(t.get("profit", 0) or 0) <= 0)
            v["profit_factor"] = _r2(
                ws / ls) if ls > 0 else (999.99 if ws > 0 else 0)
        return list(bk.values())

    return {
        "daily": daily_list,
        "monthly": monthly_list,
        "by_strategy": _bk("strategy_id"),
        "by_worker": _bk("worker_id"),
        "by_symbol": _bk("symbol"),
    }


# =============================================================================
# Events / Logs
# =============================================================================

def get_events_list(category=None, level=None, worker_id=None,
                     deployment_id=None, search=None, limit=200) -> list:
    min_level = get_setting("log_verbosity") or "DEBUG"
    level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    min_ord = level_order.get(min_level, 0)

    events = get_events_db(limit=max(limit, 500), category=category,
                           worker_id=worker_id,
                           deployment_id=deployment_id)
    if level:
        events = [e for e in events if e.get("level") == level]
    elif min_ord > 0:
        events = [e for e in events
                  if level_order.get(e.get("level", "INFO"), 1) >= min_ord]
    if search:
        sl = search.lower()
        events = [e for e in events
                  if sl in (e.get("message", "") or "").lower()
                  or sl in (e.get("event_type", "") or "").lower()]
    return events[:limit]


# =============================================================================
# Settings
# =============================================================================

def get_system_settings() -> dict:
    return get_all_settings()


def save_system_settings(settings: dict) -> dict:
    save_settings_bulk(settings)
    return get_all_settings()


# =============================================================================
# Emergency Stop
# =============================================================================

def emergency_stop_all() -> dict:
    workers = get_all_workers()
    deployments = get_all_deployments_db()
    stopped = 0
    for d in deployments:
        if d.get("state") in ("running", "queued", "warming_up",
                                "loading_strategy", "fetching_ticks",
                                "generating_initial_bars"):
            update_deployment_state_db(d["deployment_id"], "stopped")
            stopped += 1
    cmds = 0
    for w in workers:
        if w.get("state") in ("online", "running", "idle", "stale"):
            enqueue_command(w["worker_id"], "emergency_close", {
                "action": "close_all_positions",
                "reason": "emergency_stop_all",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            enqueue_command(w["worker_id"], "stop_all_strategies", {
                "reason": "emergency_stop_all",
            })
            cmds += 2
    log_event_db("system", "emergency_stop",
                 f"Emergency stop: {stopped} deps stopped, "
                 f"{cmds} commands sent",
                 level="WARNING")
    return {"ok": True, "deployments_stopped": stopped,
            "commands_sent": cmds,
            "workers_notified": len(workers)}


# =============================================================================
# Admin
# =============================================================================

def admin_get_stats() -> dict:
    stats = get_system_stats_db()
    stats["fleet_summary"] = get_fleet_summary()
    return stats


def admin_delete_strategy(strategy_id: str) -> dict:
    result = delete_strategy_full_db(strategy_id)
    log_event_db("strategy", "deleted",
                 f"Strategy {strategy_id} deleted",
                 strategy_id=strategy_id, level="WARNING")
    return result


def admin_reset_portfolio() -> dict:
    tc = delete_all_trades_db()
    clear_equity_snapshots_db()
    log_event_db("system", "portfolio_reset",
                 f"{tc} trades deleted", level="WARNING")
    return {"trades_deleted": tc, "equity_cleared": True}


def admin_clear_trades() -> dict:
    c = delete_all_trades_db()
    log_event_db("system", "trades_cleared",
                 f"{c} trades deleted", level="WARNING")
    return {"trades_deleted": c}


def admin_remove_worker(worker_id: str) -> dict:
    with _worker_lock:
        _workers_cache.pop(worker_id, None)
    with _command_lock:
        _command_queues.pop(worker_id, None)
    result = remove_worker_db(worker_id)
    log_event_db("worker", "removed",
                 f"Worker {worker_id} removed",
                 worker_id=worker_id, level="WARNING")
    return result


def admin_remove_stale_workers(threshold: int = 300) -> dict:
    count = remove_stale_workers_db(threshold)
    now = datetime.now(timezone.utc)
    with _worker_lock:
        stale = []
        for wid, w in _workers_cache.items():
            hb = w.get("last_heartbeat_at")
            if hb:
                try:
                    last = datetime.fromisoformat(hb)
                    if (now - last).total_seconds() > threshold:
                        stale.append(wid)
                except (TypeError, ValueError):
                    stale.append(wid)
        for wid in stale:
            _workers_cache.pop(wid, None)
    return {"removed": count}


def admin_clear_events() -> dict:
    c = clear_events_db()
    return {"events_cleared": c}


def admin_full_reset() -> dict:
    counts = full_system_reset_db()
    with _worker_lock:
        _workers_cache.clear()
    with _command_lock:
        _command_queues.clear()
    log_event_db("system", "full_reset",
                 "Full system reset", level="WARNING")
    return counts
```

---

## `vm/trading/execution.py`

```python
"""
JINNI GRID — Trade Execution Layer + Logger
worker/execution.py

Handles:
  - Real MT5 order execution (BUY/SELL/CLOSE)
  - Position querying (filtered by magic number)
  - SL/TP modification
  - R-multiple TP computation from fill price
  - MA-snapshot SL computation
  - MA-cross exit monitoring
  - Dedicated [EXEC] execution logger
  - Trade record building for ctx._trades
  - Signal validation (ported from JINNI ZERO engine_core.py)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Signal Constants
# =============================================================================

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_CLOSE = "CLOSE"
SIGNAL_CLOSE_LONG = "CLOSE_LONG"
SIGNAL_CLOSE_SHORT = "CLOSE_SHORT"
VALID_SIGNALS = {
    SIGNAL_BUY, SIGNAL_SELL, SIGNAL_HOLD, SIGNAL_CLOSE,
    SIGNAL_CLOSE_LONG, SIGNAL_CLOSE_SHORT, None,
}


# =============================================================================
# Signal Validation (ported from JINNI ZERO engine_core.py)
# =============================================================================

def validate_signal(raw, bar_index: int) -> dict:
    """
    Validate and normalize a raw signal dict from strategy.on_bar().
    Matches JINNI ZERO backtester validate_signal() exactly.
    """
    if raw is None:
        return {"signal": "HOLD"}
    if not isinstance(raw, dict):
        print(f"[EXEC] WARNING: Bar {bar_index}: strategy returned "
              f"{type(raw).__name__}, expected dict or None")
        return {"signal": "HOLD"}

    sig = raw.get("signal")
    if sig is not None:
        sig = str(sig).upper()
    if sig not in VALID_SIGNALS:
        print(f"[EXEC] WARNING: Bar {bar_index}: invalid signal '{sig}'")
        return {"signal": "HOLD"}

    out = {"signal": sig or "HOLD"}

    # Direct SL/TP
    if raw.get("sl") is not None:
        out["sl"] = float(raw["sl"])
    if raw.get("tp") is not None:
        out["tp"] = float(raw["tp"])

    # Engine-computed SL/TP fields
    for key in ("sl_mode", "sl_pts", "sl_ma_key", "sl_ma_val",
                "tp_mode", "tp_r"):
        if raw.get(key) is not None:
            if key in ("sl_mode", "sl_ma_key", "tp_mode"):
                out[key] = raw[key]
            else:
                out[key] = float(raw[key])

    # Engine-level MA cross exit keys
    if raw.get("engine_sl_ma_key") is not None:
        out["engine_sl_ma_key"] = str(raw["engine_sl_ma_key"])
    if raw.get("engine_tp_ma_key") is not None:
        out["engine_tp_ma_key"] = str(raw["engine_tp_ma_key"])

    # CLOSE signal
    if out["signal"] == "CLOSE":
        out["close"] = True
        out["close_reason"] = str(raw.get("close_reason", "strategy_close"))
    elif raw.get("close"):
        out["close"] = True
        out["close_reason"] = str(raw.get("close_reason", "strategy_close"))

    # Dynamic SL/TP updates
    if raw.get("update_sl") is not None:
        out["update_sl"] = float(raw["update_sl"])
    if raw.get("update_tp") is not None:
        out["update_tp"] = float(raw["update_tp"])

    # Comment
    if raw.get("comment"):
        out["comment"] = str(raw["comment"])

    return out


# =============================================================================
# SL/TP Computation Helpers
# =============================================================================

def compute_sl(signal: dict, entry_price: float, direction: str) -> Optional[float]:
    """
    Compute SL price from signal fields.
    Supports: direct sl, sl_mode=ma_snapshot, sl_mode=fixed.
    """
    sl_mode = signal.get("sl_mode")

    if sl_mode == "ma_snapshot":
        ma_val = signal.get("sl_ma_val")
        if ma_val is not None:
            ma_val = float(ma_val)
            if direction == "long" and ma_val < entry_price:
                return round(ma_val, 5)
            elif direction == "short" and ma_val > entry_price:
                return round(ma_val, 5)
        return None

    if sl_mode == "fixed":
        pts = float(signal.get("sl_pts", 0))
        if pts > 0:
            if direction == "long":
                return round(entry_price - pts, 5)
            else:
                return round(entry_price + pts, 5)
        return None

    # Direct SL
    if signal.get("sl") is not None:
        return float(signal["sl"])

    return None


def compute_tp(signal: dict, entry_price: float, sl_price: Optional[float],
               direction: str) -> Optional[float]:
    """
    Compute TP price from signal fields.
    Supports: direct tp, tp_mode=r_multiple.
    """
    tp_mode = signal.get("tp_mode")

    if tp_mode == "r_multiple":
        r = float(signal.get("tp_r", 1.0))
        if sl_price is not None:
            risk = abs(entry_price - sl_price)
            if risk > 0:
                if direction == "long":
                    return round(entry_price + risk * r, 5)
                else:
                    return round(entry_price - risk * r, 5)
        return None

    # Direct TP
    if signal.get("tp") is not None:
        return float(signal["tp"])

    return None


# =============================================================================
# Position State
# =============================================================================

@dataclass
class PositionState:
    has_position: bool = False
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    size: Optional[float] = None
    ticket: Optional[int] = None
    profit: Optional[float] = None
    entry_bar: Optional[int] = None
    # Backtester-compatible fields
    bars_held: int = 0
    unrealized_pts: float = 0.0
    unrealized_pnl: float = 0.0
    mae: float = 0.0
    mfe: float = 0.0

    @property
    def sl_level(self) -> Optional[float]:
        """Backtester-compatible alias for sl."""
        return self.sl

    @property
    def tp_level(self) -> Optional[float]:
        """Backtester-compatible alias for tp."""
        return self.tp


# =============================================================================
# Execution Logger
# =============================================================================

class ExecutionLogger:
    """Dedicated [EXEC] logger for all trade decisions."""

    def __init__(self, deployment_id: str, symbol: str):
        self.deployment_id = deployment_id
        self.symbol = symbol
        self.buys_attempted = 0
        self.buys_filled = 0
        self.sells_attempted = 0
        self.sells_filled = 0
        self.closes_attempted = 0
        self.closes_filled = 0
        self.holds = 0
        self.skips = 0
        self.rejections = 0
        self.modifications = 0
        self.ma_cross_exits = 0

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

    def _pos_str(self, pos: PositionState) -> str:
        if not pos or not pos.has_position:
            return "FLAT"
        d = (pos.direction or "?").upper()
        p = f"@{pos.entry_price:.5f}" if pos.entry_price else ""
        s = f"x{pos.size}" if pos.size else ""
        pnl = f" pnl={pos.profit:.2f}" if pos.profit is not None else ""
        return f"{d}{p}{s}{pnl}"

    def log_signal(self, action: str, bar_idx: int, bar_time, price,
                   pos: PositionState):
        print(
            f"[EXEC] {self._ts()} | {action} | {self.symbol} | "
            f"bar={bar_idx} t={bar_time} | price={price} | "
            f"pos={self._pos_str(pos)}"
        )

    def log_open(self, direction: str, result: dict, sl=None, tp=None):
        if direction == "BUY":
            self.buys_attempted += 1
        else:
            self.sells_attempted += 1

        if result.get("success"):
            if direction == "BUY":
                self.buys_filled += 1
            else:
                self.sells_filled += 1
            print(
                f"[EXEC]   -> OPENED {direction} | "
                f"ticket={result.get('ticket')} "
                f"price={result.get('price', 0):.5f} "
                f"vol={result.get('volume', 0)} "
                f"sl={sl} tp={tp}"
            )
        else:
            self.rejections += 1
            print(
                f"[EXEC]   -> REJECTED {direction} | "
                f"error={result.get('error', 'unknown')}"
            )

    def log_close(self, results: list, reason: str = "signal"):
        self.closes_attempted += 1
        for r in results:
            if r.get("success"):
                self.closes_filled += 1
                print(
                    f"[EXEC]   -> CLOSED ticket={r.get('ticket')} "
                    f"price={r.get('price', 0):.5f} "
                    f"profit={r.get('profit', 0):.2f} "
                    f"reason={reason}"
                )
            else:
                self.rejections += 1
                print(
                    f"[EXEC]   -> CLOSE FAILED ticket={r.get('ticket', '?')} "
                    f"error={r.get('error', 'unknown')}"
                )

    def log_skip(self, action: str, reason: str):
        self.skips += 1
        print(f"[EXEC]   -> SKIPPED {action} | reason={reason}")

    def log_hold(self):
        self.holds += 1

    def log_modify(self, result: dict, sl=None, tp=None):
        self.modifications += 1
        if result.get("success"):
            print(f"[EXEC]   -> MODIFIED sl={sl} tp={tp}")
        else:
            print(f"[EXEC]   -> MODIFY FAILED error={result.get('error')}")

    def log_ma_cross_exit(self, ma_key: str, direction: str, ma_val: float,
                          close_price: float):
        self.ma_cross_exits += 1
        print(
            f"[EXEC]   -> MA CROSS EXIT | {ma_key}={ma_val:.5f} "
            f"close={close_price:.5f} dir={direction}"
        )

    def get_stats(self) -> dict:
        return {
            "buys_attempted": self.buys_attempted,
            "buys_filled": self.buys_filled,
            "sells_attempted": self.sells_attempted,
            "sells_filled": self.sells_filled,
            "closes_attempted": self.closes_attempted,
            "closes_filled": self.closes_filled,
            "holds": self.holds,
            "skips": self.skips,
            "rejections": self.rejections,
            "modifications": self.modifications,
            "ma_cross_exits": self.ma_cross_exits,
        }


# =============================================================================
# MT5 Trade Executor
# =============================================================================

def _import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None


class MT5Executor:
    """Handles all real MT5 order execution."""

    def __init__(self, symbol: str, lot_size: float, deployment_id: str):
        self.symbol = symbol
        self.lot_size = lot_size
        self.magic = self._make_magic(deployment_id)
        self._mt5 = _import_mt5()
        self._filling_mode = None

        if self._mt5:
            self._filling_mode = self._detect_filling()
            print(
                f"[EXECUTOR] Ready: symbol={symbol} lot={lot_size} "
                f"magic={self.magic} filling={self._filling_mode}"
            )
        else:
            print("[EXECUTOR] WARNING: MT5 not available. Execution disabled.")

    @staticmethod
    def _make_magic(deployment_id: str) -> int:
        h = 0
        for c in deployment_id:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return (h % 900000) + 100000

    def _detect_filling(self) -> int:
        mt5 = self._mt5
        info = mt5.symbol_info(self.symbol)
        if info is None:
            return 1
        fm = info.filling_mode
        if fm & 2:
            return 1  # IOC
        elif fm & 1:
            return 0  # FOK
        else:
            return 2  # RETURN

    # ── Open Orders ─────────────────────────────────────────

    def open_buy(self, sl=None, tp=None, comment="") -> dict:
        return self._open_order("buy", sl, tp, comment)

    def open_sell(self, sl=None, tp=None, comment="") -> dict:
        return self._open_order("sell", sl, tp, comment)

    def _open_order(self, direction: str, sl=None, tp=None,
                    comment="") -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "error": "MT5 not available"}

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return {"success": False,
                    "error": f"No tick data for {self.symbol}"}

        is_buy = direction == "buy"
        price = tick.ask if is_buy else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot_size,
            "type": order_type,
            "price": price,
            "deviation": 30,
            "magic": self.magic,
            "comment": comment or f"JG_{direction}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode,
        }

        if sl is not None and sl > 0:
            request["sl"] = round(float(sl), 5)
        if tp is not None and tp > 0:
            request["tp"] = round(float(tp), 5)

        print(f"[EXECUTOR] Sending {direction.upper()}: {request}")
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            return {"success": False, "error": f"order_send returned None: {err}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "error": f"retcode={result.retcode} comment={result.comment}",
                "retcode": result.retcode,
            }

        return {
            "success": True,
            "ticket": result.order,
            "price": result.price,
            "volume": result.volume,
        }

    # ── Close Orders ────────────────────────────────────────

    def close_position(self, ticket: int, pos_type: int,
                       volume: float, profit: float) -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "ticket": ticket,
                    "error": "MT5 not available"}

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return {"success": False, "ticket": ticket,
                    "error": f"No tick for {self.symbol}"}

        is_long = (pos_type == 0)
        close_price = tick.bid if is_long else tick.ask
        close_type = mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": close_price,
            "deviation": 30,
            "magic": self.magic,
            "comment": "JG_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode,
        }

        print(f"[EXECUTOR] Closing ticket={ticket}: {request}")
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            return {"success": False, "ticket": ticket,
                    "error": f"order_send None: {err}"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False, "ticket": ticket,
                "error": f"retcode={result.retcode} comment={result.comment}",
            }

        return {
            "success": True, "ticket": ticket,
            "price": result.price, "volume": volume,
            "profit": profit,
        }

    def close_all_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions()]

    def close_long_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions() if p["type"] == 0]

    def close_short_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"], p["volume"], p["profit"])
                for p in self.get_positions() if p["type"] == 1]

    # ── Modify SL/TP ────────────────────────────────────────

    def modify_sl_tp(self, ticket: int, sl=None, tp=None) -> dict:
        mt5 = self._mt5
        if mt5 is None:
            return {"success": False, "error": "MT5 not available"}

        positions = mt5.positions_get(ticket=ticket)
        if positions is None or len(positions) == 0:
            return {"success": False, "error": f"Position {ticket} not found"}

        pos = positions[0]
        new_sl = round(float(sl), 5) if sl is not None else pos.sl
        new_tp = round(float(tp), 5) if tp is not None else pos.tp

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp,
        }

        result = mt5.order_send(request)
        if result is None:
            return {"success": False, "error": "order_send returned None"}
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False,
                    "error": f"retcode={result.retcode} comment={result.comment}"}
        return {"success": True, "sl": new_sl, "tp": new_tp}

    # ── Query ───────────────────────────────────────────────

    def get_positions(self) -> list:
        mt5 = self._mt5
        if mt5 is None:
            return []
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []
        result = []
        for p in positions:
            if p.magic != self.magic:
                continue
            result.append({
                "ticket": p.ticket, "type": p.type,
                "volume": p.volume, "price_open": p.price_open,
                "sl": p.sl, "tp": p.tp, "profit": p.profit,
                "symbol": p.symbol, "magic": p.magic,
            })
        return result

    def get_floating_pnl(self) -> float:
        return sum(p["profit"] for p in self.get_positions())

    def get_open_count(self) -> int:
        return len(self.get_positions())

    def get_position_state(self) -> PositionState:
        positions = self.get_positions()
        if not positions:
            return PositionState(has_position=False)
        p = positions[0]
        return PositionState(
            has_position=True,
            direction="long" if p["type"] == 0 else "short",
            entry_price=p["price_open"],
            sl=p["sl"] if p["sl"] != 0 else None,
            tp=p["tp"] if p["tp"] != 0 else None,
            size=p["volume"],
            ticket=p["ticket"],
            profit=p["profit"],
        )
    # ── Deal History (for broker-side closes) ───────────────

    def get_closed_deal_profit(self, ticket: int) -> dict:
        """
        Look up the profit of a position that was closed by the broker (SL/TP).
        Uses MT5 deal history. Returns {profit, close_price, close_time} or empty dict.
        """
        mt5 = self._mt5
        if mt5 is None:
            return {}
        try:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            # Search deals for this position in the last 2 hours
            deals = mt5.history_deals_get(
                now - timedelta(hours=2), now, position=ticket
            )
            if deals is None or len(deals) == 0:
                return {}
            # The closing deal is the one with DEAL_ENTRY_OUT (1)
            close_deal = None
            for d in deals:
                if d.entry == 1:  # DEAL_ENTRY_OUT
                    close_deal = d
                    break
            if close_deal is None:
                # Fallback: use last deal
                close_deal = deals[-1]
            return {
                "profit": close_deal.profit,
                "close_price": close_deal.price,
                "close_time": close_deal.time,
                "commission": close_deal.commission,
                "swap": close_deal.swap,
                "fee": getattr(close_deal, "fee", 0.0),
            }
        except Exception as exc:
            print(f"[EXECUTOR] Deal history lookup failed for ticket {ticket}: {exc}")
            return {}

    def get_account_info(self) -> dict:
        """Get MT5 account balance, equity, and margin info."""
        mt5 = self._mt5
        if mt5 is None:
            return {}
        try:
            info = mt5.account_info()
            if info is None:
                return {}
            return {
                "balance": info.balance,
                "equity": info.equity,
                "margin": info.margin,
                "free_margin": info.margin_free,
                "profit": info.profit,  # total floating
                "currency": info.currency,
            }
        except Exception as exc:
            print(f"[EXECUTOR] Account info failed: {exc}")
            return {}


# =============================================================================
# Trade Record Builder (for ctx._trades)
# =============================================================================

def build_trade_record(
    trade_id: int,
    direction: str,
    entry_price: float,
    entry_bar: int,
    entry_time: int,
    exit_price: float,
    exit_bar: int,
    exit_time: int,
    exit_reason: str,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    lot_size: float = 0.01,
    ticket: Optional[int] = None,
    profit: Optional[float] = None,
) -> dict:
    """
    Build a trade record compatible with JINNI ZERO backtester format.
    Strategies use ctx.trades for gating logic, no-reuse, etc.
    """
    points_pnl = (exit_price - entry_price) if direction == "long" \
                 else (entry_price - exit_price)

    return {
        "id": trade_id,
        "direction": direction,
        "entry_bar": entry_bar,
        "entry_time": entry_time,
        "entry_price": round(entry_price, 5),
        "exit_bar": exit_bar,
        "exit_time": exit_time,
        "exit_price": round(exit_price, 5),
        "exit_reason": exit_reason,
        "sl_level": sl,
        "tp_level": tp,
        "lot_size": lot_size,
        "ticket": ticket,
        "points_pnl": round(points_pnl, 5),
        "profit": profit,
        "bars_held": exit_bar - entry_bar,
    }
```

---

## `vm/trading/sim_executor.py`

```python
"""
JINNI GRID — Simulated Executor
vm/trading/sim_executor.py

Drop-in replacement for MT5Executor used during validation.
Same API — StrategyRunner._on_new_bar() runs IDENTICALLY.

★ set_current_price() simulates broker SL/TP monitoring.
★ set_next_fill_price() controls fill price for bar-open execution.
"""

from __future__ import annotations
from typing import Optional
from trading.execution import PositionState


class SimulatedExecutor:

    def __init__(self, symbol: str, lot_size: float, deployment_id: str,
                 point: float, tick_size: float, tick_value: float):
        self.symbol = symbol
        self.lot_size = lot_size
        self.magic = self._make_magic(deployment_id)
        self._point = point
        self._tick_size = tick_size if tick_size > 0 else point
        self._tick_value = tick_value if tick_value > 0 else 1.0
        self._current_price = 0.0
        self._positions: list = []
        self._next_ticket = 100000
        self._filling_mode = 1
        self._next_fill_price: Optional[float] = None
        self._broker_closes: list = []

        print(f"[SIM-EXEC] Ready: symbol={symbol} lot={lot_size} "
              f"point={point} tick_size={self._tick_size} "
              f"tick_value={self._tick_value}")

    @staticmethod
    def _make_magic(deployment_id: str) -> int:
        h = 0
        for c in deployment_id:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return (h % 900000) + 100000

    # ── PnL ─────────────────────────────────────────────────

    def _calc_pnl(self, pos: dict) -> float:
        return self._calc_pnl_at_price(pos, self._current_price)

    def _calc_pnl_at_price(self, pos: dict, price: float) -> float:
        entry = pos["price_open"]
        vol = pos["volume"]
        if pos["type"] == 0:
            pts = price - entry
        else:
            pts = entry - price
        if self._tick_size > 0:
            ticks_moved = pts / self._tick_size
            return round(ticks_moved * self._tick_value * vol, 2)
        return 0.0

    # ── Price Feed + Broker SL/TP ───────────────────────────

    def set_current_price(self, price: float):
        self._current_price = price

        to_close = []
        for p in list(self._positions):
            sl = p.get("sl", 0)
            tp = p.get("tp", 0)

            if p["type"] == 0:  # LONG
                if sl > 0 and price <= sl:
                    to_close.append((p, sl, "SL_HIT"))
                elif tp > 0 and price >= tp:
                    to_close.append((p, tp, "TP_HIT"))
            else:  # SHORT
                if sl > 0 and price >= sl:
                    to_close.append((p, sl, "SL_HIT"))
                elif tp > 0 and price <= tp:
                    to_close.append((p, tp, "TP_HIT"))

        for p, fill_price, reason in to_close:
            pnl = self._calc_pnl_at_price(p, fill_price)
            self._broker_closes.append({
                "ticket": p["ticket"],
                "type": p["type"],
                "price_open": p["price_open"],
                "price": fill_price,
                "volume": p["volume"],
                "profit": pnl,
                "reason": reason,
                "sl": p.get("sl", 0),
                "tp": p.get("tp", 0),
            })
            self._positions.remove(p)
            print(f"[SIM-EXEC] BROKER {reason}: ticket={p['ticket']} "
                  f"{'LONG' if p['type'] == 0 else 'SHORT'} "
                  f"entry={p['price_open']:.5f} exit={fill_price:.5f} "
                  f"sl={p.get('sl', 0)} tp={p.get('tp', 0)} "
                  f"pnl={pnl:.2f}")

        for p in self._positions:
            p["profit"] = self._calc_pnl(p)

    def set_next_fill_price(self, price: float):
        """Override fill price for the next order only (bar-open fill)."""
        self._next_fill_price = price

    def get_broker_close_info(self, ticket: int) -> Optional[dict]:
        for i, c in enumerate(self._broker_closes):
            if c["ticket"] == ticket:
                return self._broker_closes.pop(i)
        return None

    # ── Open Orders ─────────────────────────────────────────

    def open_buy(self, sl=None, tp=None, comment="") -> dict:
        return self._open("buy", sl, tp, comment)

    def open_sell(self, sl=None, tp=None, comment="") -> dict:
        return self._open("sell", sl, tp, comment)

    def _open(self, direction: str, sl=None, tp=None, comment="") -> dict:
        ticket = self._next_ticket
        self._next_ticket += 1

        # ★ Use override fill price if set (bar-open fill)
        if self._next_fill_price is not None:
            price = self._next_fill_price
            self._next_fill_price = None
        else:
            price = self._current_price

        pos = {
            "ticket": ticket,
            "type": 0 if direction == "buy" else 1,
            "volume": self.lot_size,
            "price_open": price,
            "sl": round(float(sl), 5) if sl and float(sl) > 0 else 0,
            "tp": round(float(tp), 5) if tp and float(tp) > 0 else 0,
            "profit": 0.0,
            "symbol": self.symbol,
            "magic": self.magic,
        }
        self._positions.append(pos)

        print(f"[SIM-EXEC] OPENED {direction.upper()} ticket={ticket} "
              f"price={price:.5f} sl={pos['sl']} tp={pos['tp']}")

        return {
            "success": True,
            "ticket": ticket,
            "price": price,
            "volume": self.lot_size,
        }

    # ── Close Orders ────────────────────────────────────────

    def close_position(self, ticket: int, pos_type: int,
                       volume: float, profit: float) -> dict:
        pos = None
        for p in self._positions:
            if p["ticket"] == ticket:
                pos = p
                break
        if pos is None:
            return {"success": False, "ticket": ticket,
                    "error": "Position not found"}

        close_price = self._current_price
        actual_pnl = self._calc_pnl(pos)
        self._positions.remove(pos)

        print(f"[SIM-EXEC] CLOSED ticket={ticket} "
              f"price={close_price:.5f} pnl={actual_pnl:.2f}")

        return {
            "success": True,
            "ticket": ticket,
            "price": close_price,
            "volume": volume,
            "profit": actual_pnl,
        }

    def close_all_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"],
                                    p["volume"], p["profit"])
                for p in list(self._positions)]

    def close_long_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"],
                                    p["volume"], p["profit"])
                for p in list(self._positions) if p["type"] == 0]

    def close_short_positions(self) -> list:
        return [self.close_position(p["ticket"], p["type"],
                                    p["volume"], p["profit"])
                for p in list(self._positions) if p["type"] == 1]

    # ── Modify SL/TP ───────────────────────────────────────

    def modify_sl_tp(self, ticket: int, sl=None, tp=None) -> dict:
        for p in self._positions:
            if p["ticket"] == ticket:
                if sl is not None:
                    p["sl"] = round(float(sl), 5)
                if tp is not None:
                    p["tp"] = round(float(tp), 5)
                print(f"[SIM-EXEC] MODIFIED ticket={ticket} "
                      f"sl={p['sl']} tp={p['tp']}")
                return {"success": True, "sl": p["sl"], "tp": p["tp"]}
        return {"success": False, "error": f"Position {ticket} not found"}

    # ── Query ───────────────────────────────────────────────

    def get_positions(self) -> list:
        return list(self._positions)

    def get_floating_pnl(self) -> float:
        return sum(p["profit"] for p in self._positions)

    def get_open_count(self) -> int:
        return len(self._positions)

    def get_position_state(self) -> PositionState:
        if not self._positions:
            return PositionState(has_position=False)
        p = self._positions[0]
        return PositionState(
            has_position=True,
            direction="long" if p["type"] == 0 else "short",
            entry_price=p["price_open"],
            sl=p["sl"] if p["sl"] != 0 else None,
            tp=p["tp"] if p["tp"] != 0 else None,
            size=p["volume"],
            ticket=p["ticket"],
            profit=p["profit"],
        )

    def get_account_info(self) -> dict:
        return {
            "balance": 0.0,
            "equity": self.get_floating_pnl(),
            "margin": 0.0,
            "free_margin": 0.0,
            "profit": self.get_floating_pnl(),
            "currency": "USD",
        }
```

---

## `ui/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>JINNI GRID — Mother Server Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />
  <link rel="stylesheet" href="/css/style.css" />
</head>
<body data-theme="dark">

  <aside class="sidebar" id="sidebar">
    <div class="sidebar-brand">
      <div class="brand-mark">JG</div>
      <div class="brand-text">
        <span class="brand-name">JINNI GRID</span>
        <span class="brand-sub">Mother Server</span>
      </div>
    </div>
    <nav class="sidebar-nav" id="sidebar-nav">
      <a href="#" class="nav-item active" data-page="dashboard">
        <i class="fa-solid fa-grip"></i><span>Dashboard</span>
      </a>
      <a href="#" class="nav-item" data-page="fleet">
        <i class="fa-solid fa-server"></i><span>Fleet</span>
      </a>
      <a href="#" class="nav-item" data-page="portfolio">
        <i class="fa-solid fa-chart-line"></i><span>Portfolio</span>
      </a>
      <a href="#" class="nav-item" data-page="validation">
        <i class="fa-solid fa-flask-vial"></i><span>Validation</span>
      </a>
      <a href="#" class="nav-item" data-page="strategies">
        <i class="fa-solid fa-crosshairs"></i><span>Strategies</span>
      </a>
      <a href="#" class="nav-item" data-page="logs">
        <i class="fa-solid fa-scroll"></i><span>Logs</span>
      </a>
      <a href="#" class="nav-item" data-page="settings">
        <i class="fa-solid fa-gear"></i><span>Settings</span>
      </a>
    </nav>
    <div class="sidebar-footer">
      <button class="theme-toggle" id="theme-toggle" title="Toggle Theme">
        <i class="fa-solid fa-sun"></i><span>Light Mode</span>
      </button>
    </div>
  </aside>

  <div class="main-wrapper">
    <header class="topbar" id="topbar">
      <div class="topbar-left">
        <h1 class="topbar-title" id="topbar-title">Dashboard</h1>
        <span class="topbar-subtitle">Mother Server Control Panel</span>
      </div>
      <div class="topbar-right">
        <div class="topbar-status">
          <span class="status-dot status-dot--online pulse"></span>
          <span class="status-label">System Online</span>
        </div>
        <div class="topbar-clock" id="topbar-clock">00:00:00</div>
      </div>
    </header>
    <main class="content" id="main-content"></main>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
  <script src="/js/main.js"></script>
  <script src="/js/workerDetailRenderer.js"></script>
  <script src="/js/validationRenderer.js"></script>
</body>
</html>
```

---

## `app/config.py`

```python
"""
JINNI Grid - Configuration Loader
Reads config.yaml from project root. Falls back to safe defaults.
app/config.py
"""
import os, yaml

_config_cache = None

_DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 5100, "debug": False, "cors_origins": ["*"]},
    "app": {"name": "JINNI Grid Mother Server", "version": "0.2.0"},
    "fleet": {"stale_threshold_seconds": 30, "offline_threshold_seconds": 90},
}


def _load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    config_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(config_dir)
    config_path = os.path.join(project_root, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
        print(f"[CONFIG] Loaded config from: {config_path}")
    else:
        print(f"[CONFIG] WARNING: config.yaml not found at {config_path}")
        print("[CONFIG] Using fallback defaults.")
        _config_cache = _DEFAULTS
    return _config_cache


class Config:
    @classmethod
    def get_server_config(cls) -> dict:
        return _load_config().get("server", _DEFAULTS["server"])

    @classmethod
    def get_app_config(cls) -> dict:
        return _load_config().get("app", _DEFAULTS["app"])

    @classmethod
    def get_cors_origins(cls) -> list:
        return cls.get_server_config().get("cors_origins", ["*"])

    @classmethod
    def get_fleet_config(cls) -> dict:
        return _load_config().get("fleet", _DEFAULTS["fleet"])
```

---

## `app/services/__init__.py`

```python
# JINNI Grid - Services package
```
