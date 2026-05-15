/* ================================================================
   JINNI GRID — Live Strategy Chart Module
   ui/js/chartRenderer.js
   TradingView Lightweight Charts v4
   ================================================================ */

var ChartRenderer = (function () {
  'use strict';

  var _chart = null;
  var _candleSeries = null;
  var _volumeSeries = null;
  var _pollInterval = null;
  var _resizeObserver = null;

  var _workers = [];
  var _deployments = [];
  var _selectedWorkerId = null;
  var _selectedDeploymentId = null;
  var _selectedSymbol = '';

  var _lastBarIndex = -1;
  var _lastMarkerId = 0;
  var _lwMarkers = [];
  var _slLine = null;
  var _tpLine = null;
  var _barCount = 0;

  /* ── Helpers ──────────────────────────────────────────── */

  function _isDark() { return document.body.getAttribute('data-theme') !== 'light'; }

  function _colors() {
    var d = _isDark();
    return {
      bg:        d ? '#0b0f19' : '#ffffff',
      text:      d ? '#94a3b8' : '#475569',
      grid:      d ? '#1a2236' : '#f1f5f9',
      border:    d ? '#1e293b' : '#e2e8f0',
      crosshair: d ? '#64748b' : '#94a3b8',
      upBody:    '#10b981', downBody: '#ef4444',
      upWick:    '#10b981', downWick: '#ef4444',
    };
  }

  function _fmtPrice(v) {
    if (v === null || v === undefined) return '\u2014';
    return Number(v).toFixed(v < 10 ? 5 : 2);
  }

  /* ── Reset ───────────────────────────────────────────── */

  function _reset() {
    if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
    if (_resizeObserver) { _resizeObserver.disconnect(); _resizeObserver = null; }
    if (_chart) { _chart.remove(); _chart = null; }
    _candleSeries = null; _volumeSeries = null;
    _workers = []; _deployments = [];
    _selectedWorkerId = null; _selectedDeploymentId = null; _selectedSymbol = '';
    _lastBarIndex = -1; _lastMarkerId = 0; _lwMarkers = []; _barCount = 0;
    _slLine = null; _tpLine = null;
  }

  /* ── Render Page ─────────────────────────────────────── */

  function render() {
    _reset();
    var html = '<div class="fleet-page" id="charts-page">';

    /* header */
    html += '<div class="fleet-page-header">' +
      '<span class="fleet-page-title"><i class="fa-solid fa-chart-column" style="color:var(--accent);margin-right:8px;"></i>Live Strategy Charts</span>' +
      '<div class="fleet-page-meta"><div class="auto-refresh-badge"><span class="auto-refresh-dot"></span>Live</div></div></div>';

    /* controls */
    html += '<div class="chart-controls"><div class="chart-ctrl-row">' +
      '<div class="wd-form-group"><label class="wd-form-label">Worker VM</label>' +
        '<select class="wd-form-select" id="chart-worker-sel"><option value="">Loading\u2026</option></select></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Deployment</label>' +
        '<select class="wd-form-select" id="chart-deploy-sel"><option value="">Select worker first</option></select></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Symbol</label>' +
        '<div class="chart-symbol-val mono" id="chart-symbol">\u2014</div></div>' +
      '<div class="wd-form-group"><label class="wd-form-label">Bars</label>' +
        '<div class="chart-symbol-val mono" id="chart-bar-ct">0</div></div>' +
      '<div class="wd-form-group" style="align-self:flex-end;">' +
        '<button class="wd-btn wd-btn-ghost" id="chart-fit-btn" title="Fit all data"><i class="fa-solid fa-expand"></i> Fit</button></div>' +
    '</div></div>';

    /* chart */
    html += '<div class="chart-main-panel"><div id="chart-area" class="chart-area"></div></div>';

    /* legend / info strip */
    html += '<div class="chart-legend-strip" id="chart-legend"></div>';

    html += '</div>';
    document.getElementById('main-content').innerHTML = html;

    _attachControls();
    _loadWorkers();
    _pollInterval = setInterval(_poll, 2500);
  }

  /* ── Attach Controls ─────────────────────────────────── */

  function _attachControls() {
    document.getElementById('chart-worker-sel').addEventListener('change', function () {
      _selectedWorkerId = this.value;
      _selectedDeploymentId = null;
      _loadDeployments();
    });
    document.getElementById('chart-deploy-sel').addEventListener('change', function () {
      _selectedDeploymentId = this.value;
      _onDeploymentSelected();
    });
    document.getElementById('chart-fit-btn').addEventListener('click', function () {
      if (_chart) _chart.timeScale().fitContent();
    });
  }

  /* ── Load Workers ────────────────────────────────────── */

  function _loadWorkers() {
    ApiClient.getFleetWorkers().then(function (d) {
      _workers = d.workers || [];
      var sel = document.getElementById('chart-worker-sel');
      if (!sel) return;
      var html = '<option value="">-- Select Worker --</option>';
      _workers.forEach(function (w) {
        var n = w.worker_name || w.worker_id;
        html += '<option value="' + w.worker_id + '">' + n + ' (' + (w.state || '?') + ')</option>';
      });
      sel.innerHTML = html;
    }).catch(function () {});
  }

  /* ── Load Deployments ────────────────────────────────── */

  function _loadDeployments() {
    var depSel = document.getElementById('chart-deploy-sel');
    if (!depSel) return;
    if (!_selectedWorkerId) {
      depSel.innerHTML = '<option value="">Select worker first</option>';
      return;
    }
    ApiClient.getDeployments().then(function (d) {
      _deployments = (d.deployments || []).filter(function (dep) {
        return dep.worker_id === _selectedWorkerId;
      });
      var html = '<option value="">-- Select Deployment --</option>';
      _deployments.forEach(function (dep) {
        var label = (dep.strategy_name || dep.strategy_id) + ' / ' + dep.symbol + ' [' + dep.state + ']';
        html += '<option value="' + dep.deployment_id + '">' + label + '</option>';
      });
      depSel.innerHTML = html;
    }).catch(function () {
      depSel.innerHTML = '<option value="">Failed to load</option>';
    });
  }

  /* ── Deployment Selected ─────────────────────────────── */

  function _onDeploymentSelected() {
    _lastBarIndex = -1;
    _lastMarkerId = 0;
    _lwMarkers = [];
    _barCount = 0;
    _removePriceLines();

    if (!_selectedDeploymentId) {
      _destroyChart();
      document.getElementById('chart-symbol').textContent = '\u2014';
      document.getElementById('chart-bar-ct').textContent = '0';
      document.getElementById('chart-legend').innerHTML = '';
      return;
    }

    /* find symbol */
    var dep = null;
    for (var i = 0; i < _deployments.length; i++) {
      if (_deployments[i].deployment_id === _selectedDeploymentId) { dep = _deployments[i]; break; }
    }
    _selectedSymbol = dep ? dep.symbol : '';
    document.getElementById('chart-symbol').textContent = _selectedSymbol || '\u2014';

    _initChart();
    _fetchAll();
  }

  /* ── Init Lightweight Chart ──────────────────────────── */

  function _destroyChart() {
    if (_chart) { _chart.remove(); _chart = null; }
    _candleSeries = null; _volumeSeries = null;
  }

  function _initChart() {
    _destroyChart();
    var container = document.getElementById('chart-area');
    if (!container) return;
    var c = _colors();

    _chart = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 500,
      layout: { background: { type: 'solid', color: c.bg }, textColor: c.text, fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal, vertLine: { color: c.crosshair, width: 1, style: 3 }, horzLine: { color: c.crosshair, width: 1, style: 3 } },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: c.border },
      rightPriceScale: { borderColor: c.border },
    });

    _candleSeries = _chart.addCandlestickSeries({
      upColor: c.upBody, downColor: c.downBody,
      borderUpColor: c.upBody, borderDownColor: c.downBody,
      wickUpColor: c.upWick, wickDownColor: c.downWick,
    });

    _volumeSeries = _chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    });
    _chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

    /* resize */
    if (_resizeObserver) _resizeObserver.disconnect();
    _resizeObserver = new ResizeObserver(function () {
      if (_chart && container) _chart.applyOptions({ width: container.clientWidth, height: container.clientHeight || 500 });
    });
    _resizeObserver.observe(container);
  }

  /* ── Fetch All Data ──────────────────────────────────── */

  function _fetchAll() {
    if (!_selectedDeploymentId || !_chart) return;
    _fetchBars(true);
    _fetchMarkers(true);
  }

  function _fetchBars(full) {
    var since = full ? 0 : (_lastBarIndex + 1);
    fetch('/api/charts/bars?deployment_id=' + encodeURIComponent(_selectedDeploymentId) + '&since_index=' + since)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var bars = d.bars || [];
        if (bars.length === 0) return;
        if (full) {
          var candles = [], vols = [];
          bars.forEach(function (b) {
            candles.push({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close });
            vols.push({ time: b.time, value: b.volume || 0, color: b.close >= b.open ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)' });
          });
          _candleSeries.setData(candles);
          _volumeSeries.setData(vols);
          _chart.timeScale().fitContent();
        } else {
          bars.forEach(function (b) {
            _candleSeries.update({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close });
            _volumeSeries.update({ time: b.time, value: b.volume || 0, color: b.close >= b.open ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)' });
          });
        }
        _lastBarIndex = bars[bars.length - 1].bar_index;
        _barCount = full ? bars.length : (_barCount + bars.length);
        var el = document.getElementById('chart-bar-ct');
        if (el) el.textContent = _barCount;
      }).catch(function () {});
  }

  function _fetchMarkers(full) {
    var since = full ? 0 : _lastMarkerId;
    fetch('/api/charts/markers?deployment_id=' + encodeURIComponent(_selectedDeploymentId) + '&since_id=' + since)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var raw = d.markers || [];
        if (raw.length === 0) return;
        raw.forEach(function (m) {
          _lwMarkers.push(_toLwMarker(m));
          if (m.id > _lastMarkerId) _lastMarkerId = m.id;
        });
        _lwMarkers.sort(function (a, b) { return a.time - b.time; });
        if (_candleSeries) _candleSeries.setMarkers(_lwMarkers);
        _updatePriceLines(raw);
        _renderLegend(raw);
      }).catch(function () {});
  }

  /* ── Convert DB marker → Lightweight Charts marker ──── */

  function _toLwMarker(m) {
    var mk = { time: m.time };
    switch (m.marker_type) {
      case 'entry_long':
        mk.position = 'belowBar'; mk.color = '#10b981'; mk.shape = 'arrowUp';
        mk.text = 'BUY ' + _fmtPrice(m.price); break;
      case 'entry_short':
        mk.position = 'aboveBar'; mk.color = '#ef4444'; mk.shape = 'arrowDown';
        mk.text = 'SELL ' + _fmtPrice(m.price); break;
      case 'exit_tp':
        mk.position = (m.side === 'long') ? 'aboveBar' : 'belowBar';
        mk.color = '#06b6d4'; mk.shape = 'circle'; mk.text = 'TP'; break;
      case 'exit_sl':
        mk.position = (m.side === 'long') ? 'belowBar' : 'aboveBar';
        mk.color = '#f59e0b'; mk.shape = 'circle'; mk.text = 'SL'; break;
      case 'exit_manual': case 'exit_strategy':
        mk.position = 'aboveBar'; mk.color = '#94a3b8'; mk.shape = 'square';
        mk.text = m.label || 'EXIT'; break;
      case 'exit_ma':
        mk.position = 'aboveBar'; mk.color = '#fb923c'; mk.shape = 'square';
        mk.text = 'MA EXIT'; break;
      case 'signal_buy':
        mk.position = 'belowBar'; mk.color = 'rgba(16,185,129,0.6)'; mk.shape = 'arrowUp';
        mk.text = '\u2192BUY'; break;
      case 'signal_sell':
        mk.position = 'aboveBar'; mk.color = 'rgba(239,68,68,0.6)'; mk.shape = 'arrowDown';
        mk.text = '\u2192SELL'; break;
      default:
        mk.position = 'inBar'; mk.color = '#64748b'; mk.shape = 'circle';
        mk.text = m.marker_type || '?'; break;
    }
    return mk;
  }

  /* ── Price Lines for active SL/TP ────────────────────── */

  function _removePriceLines() {
    if (_slLine && _candleSeries) { try { _candleSeries.removePriceLine(_slLine); } catch(e){} _slLine = null; }
    if (_tpLine && _candleSeries) { try { _candleSeries.removePriceLine(_tpLine); } catch(e){} _tpLine = null; }
  }

  function _updatePriceLines(markers) {
    _removePriceLines();
    if (!_candleSeries || !markers || markers.length === 0) return;
    /* find latest entry that has no matching exit */
    var entries = markers.filter(function (m) { return m.marker_type === 'entry_long' || m.marker_type === 'entry_short'; });
    var exits = markers.filter(function (m) { return m.marker_type && m.marker_type.indexOf('exit') === 0; });
    if (entries.length === 0 || entries.length <= exits.length) return;
    var last = entries[entries.length - 1];
    var meta = {};
    try { meta = JSON.parse(last.metadata_json || '{}'); } catch(e){}
    if (meta.sl) {
      _slLine = _candleSeries.createPriceLine({ price: parseFloat(meta.sl), color: '#ef4444', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'SL' });
    }
    if (meta.tp) {
      _tpLine = _candleSeries.createPriceLine({ price: parseFloat(meta.tp), color: '#06b6d4', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'TP' });
    }
  }

  /* ── Legend Strip ─────────────────────────────────────── */

  function _renderLegend(allMarkers) {
    var el = document.getElementById('chart-legend');
    if (!el) return;
    var entryCount = 0, exitCount = 0, signalCount = 0;
    allMarkers.forEach(function (m) {
      if (m.marker_type && m.marker_type.indexOf('entry') === 0) entryCount++;
      else if (m.marker_type && m.marker_type.indexOf('exit') === 0) exitCount++;
      else if (m.marker_type && m.marker_type.indexOf('signal') === 0) signalCount++;
    });
    el.innerHTML =
      '<span class="chart-legend-item"><span style="color:#10b981;">\u25B2</span> Entries: <strong>' + entryCount + '</strong></span>' +
      '<span class="chart-legend-item"><span style="color:#ef4444;">\u25CF</span> Exits: <strong>' + exitCount + '</strong></span>' +
      '<span class="chart-legend-item"><span style="color:#64748b;">\u25B6</span> Signals: <strong>' + signalCount + '</strong></span>' +
      '<span class="chart-legend-item">Bars: <strong class="mono">' + _barCount + '</strong></span>';
  }

  /* ── Poll ─────────────────────────────────────────────── */

  function _poll() {
    if (!_selectedDeploymentId || !_chart) return;
    _fetchBars(false);
    _fetchMarkers(false);
  }

  /* ── Theme Sync ──────────────────────────────────────── */

  function applyTheme() {
    if (!_chart) return;
    var c = _colors();
    _chart.applyOptions({
      layout: { background: { type: 'solid', color: c.bg }, textColor: c.text },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      timeScale: { borderColor: c.border },
      rightPriceScale: { borderColor: c.border },
    });
  }

  /* ── Lifecycle ───────────────────────────────────────── */

  function destroy() {
    _reset();
  }

  return { render: render, destroy: destroy, applyTheme: applyTheme };
})();