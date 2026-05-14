/* ================================================================
   JINNI GRID — Validation Module
   ui/js/validationRenderer.js

   Sections:
   1. Job Creation Form (strategy, symbol, month, year, VM, config)
   2. Job History List (with status polling)
   3. Job Results View (equity chart, stats, trade table, download)
   ================================================================ */

var ValidationRenderer = (function () {
  'use strict';

  var _refreshInterval = null;
  var _charts = {};
  var _currentView = 'list'; // 'list' | 'results'
  var _currentJobId = null;
  var _strategies = [];
  var _workers = [];

  function _destroyCharts() {
    for (var k in _charts) { if (_charts[k]) { _charts[k].destroy(); delete _charts[k]; } }
  }

  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  /* ── Main Render ──────────────────────────────────────────── */
  function render() {
    _currentView = 'list';
    _currentJobId = null;
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
    var curMonth = now.getMonth(); // 0-indexed

    var html = '<div class="wd-form-grid" style="grid-template-columns:1fr 1fr 1fr;">';

    /* Strategy */
    html += '<div class="wd-form-group"><label class="wd-form-label">Strategy</label>';
    html += '<select class="wd-form-select" id="val-strategy">';
    html += '<option value="">-- Select --</option>';
    _strategies.forEach(function (s) {
      html += '<option value="' + s.strategy_id + '">' + (s.strategy_name || s.strategy_id) + ' v' + (s.version || '?') + '</option>';
    });
    html += '</select></div>';

    /* Symbol */
    html += '<div class="wd-form-group"><label class="wd-form-label">Symbol</label>';
    html += '<input type="text" class="wd-form-input" id="val-symbol" value="XAUUSD" placeholder="e.g. XAUUSD" autocomplete="off" spellcheck="false" /></div>';

    /* Worker VM */
    html += '<div class="wd-form-group"><label class="wd-form-label">Worker VM</label>';
    html += '<select class="wd-form-select" id="val-worker">';
    html += '<option value="">-- Select --</option>';
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

    /* Lot Size */
    html += '<div class="wd-form-group"><label class="wd-form-label">Lot Size</label>';
    html += '<input type="number" class="wd-form-input" id="val-lot" value="0.01" step="0.01" min="0.01" /></div>';

    /* Bar Size Points */
    html += '<div class="wd-form-group"><label class="wd-form-label">Bar Size Points</label>';
    html += '<input type="number" class="wd-form-input" id="val-barsize" value="100" step="1" min="1" /></div>';

    /* Max Bars */
    html += '<div class="wd-form-group"><label class="wd-form-label">Max Bars Memory</label>';
    html += '<input type="number" class="wd-form-input" id="val-maxbars" value="500" step="10" min="10" /></div>';

    /* Spread */
    html += '<div class="wd-form-group"><label class="wd-form-label">Spread (points)</label>';
    html += '<input type="number" class="wd-form-input" id="val-spread" value="0" step="0.1" min="0" /></div>';

    /* Commission */
    html += '<div class="wd-form-group"><label class="wd-form-label">Commission / Lot</label>';
    html += '<input type="number" class="wd-form-input" id="val-comm" value="0" step="0.01" min="0" /></div>';

    html += '</div>';

    /* Run Button */
    html += '<div style="margin-top:16px;display:flex;gap:10px;justify-content:flex-end;">';
    html += '<button class="wd-btn wd-btn-primary deploy" id="val-run-btn"><i class="fa-solid fa-play"></i> Run Validation</button>';
    html += '</div>';

    el.innerHTML = html;

    document.getElementById('val-run-btn').addEventListener('click', _handleRun);

    /* Auto-uppercase symbol */
    var symInput = document.getElementById('val-symbol');
    symInput.addEventListener('input', function () {
      symInput.value = symInput.value.toUpperCase().replace(/\s/g, '');
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
      strategy_parameters: {},
    };

    document.getElementById('val-run-btn').disabled = true;
    document.getElementById('val-run-btn').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting…';

    fetch('/api/validation/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (data.ok) {
        ToastManager.show('Validation job created: ' + data.job_id, 'success');
        _fetchJobs();
      } else {
        ToastManager.show('Failed: ' + (data.detail || 'Unknown error'), 'error');
      }
      document.getElementById('val-run-btn').disabled = false;
      document.getElementById('val-run-btn').innerHTML = '<i class="fa-solid fa-play"></i> Run Validation';
    }).catch(function (e) {
      ToastManager.show('Error: ' + e.message, 'error');
      document.getElementById('val-run-btn').disabled = false;
      document.getElementById('val-run-btn').innerHTML = '<i class="fa-solid fa-play"></i> Run Validation';
    });
  }

  /* ── Fetch Jobs ───────────────────────────────────────────── */
  function _fetchJobs() {
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
      var netPnl = '—';
      var tradeCount = '—';
      if (j.summary) {
        netPnl = _fmtMoney(j.summary.net_pnl);
        tradeCount = j.summary.total_trades;
      }
      var created = j.created_at ? j.created_at.replace('T', ' ').substring(0, 16) : '—';
      var period = MONTHS[(j.month || 1) - 1] + ' ' + j.year;
      var progressBar = '';
      if (j.state === 'running') {
        progressBar = '<div style="width:60px;height:4px;background:var(--border-primary);border-radius:2px;overflow:hidden;">' +
          '<div style="width:' + (j.progress || 0) + '%;height:100%;background:var(--accent);transition:width 0.3s;"></div></div>' +
          '<div style="font-size:9px;color:var(--text-muted);margin-top:2px;">' + (j.progress_message || '') + '</div>';
      } else {
        progressBar = '<span class="mono" style="font-size:10px;">' + (j.progress || 0) + '%</span>';
      }

      var pnlClass = j.summary ? ((j.summary.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger') : '';

      var actions = '';
      if (j.state === 'completed') {
        actions = '<button class="wd-btn wd-btn-ghost val-view-btn" data-jobid="' + j.job_id + '" style="font-size:10px;padding:3px 8px;"><i class="fa-solid fa-eye"></i></button>';
      } else if (j.state === 'running') {
        actions = '<button class="wd-btn wd-btn-ghost val-stop-btn" data-jobid="' + j.job_id + '" style="font-size:10px;padding:3px 8px;color:var(--danger);"><i class="fa-solid fa-stop"></i></button>';
      }
      actions += ' <button class="wd-btn wd-btn-ghost val-del-btn" data-jobid="' + j.job_id + '" style="font-size:10px;padding:3px 8px;color:var(--danger);"><i class="fa-solid fa-trash"></i></button>';

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
        '<td>' + actions + '</td></tr>';
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
    _destroyCharts();

    var resultsEl = document.getElementById('val-results-content');
    var listEl = document.getElementById('val-jobs-content');
    var createEl = document.getElementById('val-create-panel');
    if (!resultsEl) return;

    resultsEl.style.display = '';
    resultsEl.innerHTML = _spinner();
    if (listEl) listEl.style.display = 'none';
    if (createEl) createEl.style.display = 'none';

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
    _destroyCharts();
    var resultsEl = document.getElementById('val-results-content');
    var listEl = document.getElementById('val-jobs-content');
    var createEl = document.getElementById('val-create-panel');
    if (resultsEl) { resultsEl.style.display = 'none'; resultsEl.innerHTML = ''; }
    if (listEl) listEl.style.display = '';
    if (createEl) createEl.style.display = '';
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
    html += '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">';
    html += '<button class="wd-back-btn" id="val-back-btn"><i class="fa-solid fa-arrow-left"></i> Back</button>';
    html += '<div>';
    html += '<div style="font-size:15px;font-weight:600;">' + (job.strategy_name || job.strategy_id) + ' — ' + job.symbol + ' ' + period + '</div>';
    html += '<div style="font-size:11px;color:var(--text-muted);">Job: ' + job.job_id + ' | Worker: ' + job.worker_id + ' | Bar: ' + job.bar_size_points + 'pt | Lot: ' + job.lot_size + '</div>';
    html += '</div>';
    html += '<div style="margin-left:auto;display:flex;gap:8px;">';
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
    html += _metricItem('Wins/Losses', (s.wins || 0) + '/' + (s.losses || 0));
    html += _metricItem('Avg Trade', _fmtMoney(s.avg_trade), (s.avg_trade || 0) >= 0 ? 'text-success' : 'text-danger');
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
      html += '<th>#</th><th>Dir</th><th>Entry</th><th>Exit</th><th>P&L</th><th>Comm</th><th>Net</th><th>Bars</th><th>Reason</th>';
      html += '</tr></thead><tbody>';
      trades.forEach(function (t) {
        var pc = (t.net_pnl || 0) >= 0 ? 'text-success' : 'text-danger';
        html += '<tr>' +
          '<td class="mono">' + t.trade_id + '</td>' +
          '<td>' + _statPill(t.direction.toUpperCase(), t.direction === 'long' ? 'online' : 'error') + '</td>' +
          '<td class="mono">' + t.entry_price + '</td>' +
          '<td class="mono">' + t.exit_price + '</td>' +
          '<td class="mono ' + pc + '">' + _fmtMoney(t.profit) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + _fmtMoney(t.commission || 0) + '</td>' +
          '<td class="mono ' + pc + '">' + _fmtMoney(t.net_pnl) + '</td>' +
          '<td class="mono">' + (t.bars_held || 0) + '</td>' +
          '<td class="mono" style="font-size:10px;">' + (t.exit_reason || '—') + '</td></tr>';
      });
      html += '</tbody></table></div></div>';
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
      config: { lot_size: job.lot_size, bar_size_points: job.bar_size_points, spread: job.spread_points, commission: job.commission_per_lot },
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
    var cols = ['trade_id','direction','entry_price','exit_price','profit','commission','net_pnl','bars_held','exit_reason','sl','tp'];
    var csv = cols.join(',') + '\n';
    trades.forEach(function (t) {
      csv += cols.map(function (c) { return '"' + (t[c] !== undefined && t[c] !== null ? t[c] : '') + '"'; }).join(',') + '\n';
    });
    var blob = new Blob([csv], { type: 'text/csv' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'validation_trades_' + job.job_id + '.csv';
    a.click();
    ToastManager.show('CSV exported.', 'success');
  }

  /* ── Lifecycle ────────────────────────────────────────────── */
  function destroy() {
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
    _destroyCharts();
    _currentView = 'list';
    _currentJobId = null;
  }

  return {
    render: render,
    destroy: destroy,
    _viewJob: _viewJob,
    _backToList: _backToList,
  };
})();