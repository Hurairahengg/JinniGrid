/* dashboardRenderer.js */

var DashboardRenderer = (function () {
  'use strict';

  var chartInstance = null;
  var _fleetInterval = null;
  var _lastFleetWorkers = [];

  function formatCurrency(val) {
    return '$' + val.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function formatPnl(val) {
    var sign = val >= 0 ? '+' : '';
    return sign + formatCurrency(val);
  }

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

  function portfolioCard(icon, label, value, sentiment) {
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

  function getChartColors() {
    var isDark = ThemeManager.getTheme() === 'dark';
    return {
      lineColor: isDark ? '#06b6d4' : '#0891b2',
      gridColor: isDark ? 'rgba(30,41,59,0.5)' : 'rgba(226,232,240,0.8)',
      textColor: isDark ? '#64748b' : '#94a3b8',
      tooltipBg: isDark ? '#1e293b' : '#ffffff',
      tooltipText: isDark ? '#e2e8f0' : '#1e293b',
      tooltipBorder: isDark ? '#334155' : '#e2e8f0',
      gradientTop: isDark ? 'rgba(6,182,212,0.25)' : 'rgba(8,145,178,0.18)',
      gradientBottom: isDark ? 'rgba(6,182,212,0)' : 'rgba(8,145,178,0)'
    };
  }

  function renderEquityChart() {
    var canvas = document.getElementById('equityChart');
    if (!canvas) return;
    if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
    var ctx = canvas.getContext('2d');
    var colors = getChartColors();
    var data = MockData.equityCurve;
    var labels = data.map(function (p) { return p.date; });
    var values = data.map(function (p) { return p.value; });
    var gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, colors.gradientTop);
    gradient.addColorStop(1, colors.gradientBottom);
    chartInstance = new Chart(ctx, {
      type: 'line',
      data: { labels: labels, datasets: [{
        label: 'Equity', data: values,
        borderColor: colors.lineColor, backgroundColor: gradient,
        borderWidth: 2, fill: true, tension: 0.3,
        pointRadius: 0, pointHoverRadius: 4,
        pointHoverBackgroundColor: colors.lineColor,
        pointHoverBorderColor: '#ffffff', pointHoverBorderWidth: 2
      }]},
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: colors.tooltipBg, titleColor: colors.tooltipText,
            bodyColor: colors.tooltipText, borderColor: colors.tooltipBorder,
            borderWidth: 1, cornerRadius: 6, padding: 10,
            titleFont: { family: 'Inter', size: 11 },
            bodyFont: { family: 'JetBrains Mono', size: 12 },
            callbacks: { label: function (ctx) {
              return '$' + ctx.parsed.y.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            }}
          }
        },
        scales: {
          x: { grid: { color: colors.gridColor, drawBorder: false },
            ticks: { color: colors.textColor, font: { family: 'JetBrains Mono', size: 10 }, maxTicksLimit: 10, maxRotation: 0 }},
          y: { grid: { color: colors.gridColor, drawBorder: false },
            ticks: { color: colors.textColor, font: { family: 'JetBrains Mono', size: 10 },
              callback: function (v) { return '$' + (v / 1000).toFixed(0) + 'k'; }}}
        }
      }
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
          html += '<thead><tr><th>Worker</th><th>State</th><th>Host</th><th>Heartbeat</th><th>Agent</th></tr></thead><tbody>';
          workers.forEach(function (w) {
            var name = w.worker_name || w.worker_id;
            var state = w.state || 'unknown';
            html += '<tr class="clickable" onclick="DashboardRenderer._openWorker(\'' + w.worker_id + '\')">';
            html += '<td class="mono">' + name + '</td>';
            html += '<td><span class="state-pill ' + state + '">' + state.toUpperCase() + '</span></td>';
            html += '<td class="mono">' + _nullVal(w.host) + '</td>';
            html += '<td class="mono">' + _formatAge(w.heartbeat_age_seconds) + '</td>';
            html += '<td class="mono">' + _nullVal(w.agent_version) + '</td>';
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

  function render() {
    var stats = MockData.portfolioStats;
    var pnlSentiment = function (v) { return v >= 0 ? 'positive' : 'negative'; };
    var html = '<div class="dashboard">';
    html += '<section><div class="section-header"><i class="fa-solid fa-chart-line"></i><h2>Portfolio Overview</h2><span class="section-badge">MOCK</span></div>';
    html += '<div class="portfolio-grid">';
    html += portfolioCard('fa-wallet', 'Total Balance', formatCurrency(stats.totalBalance), 'neutral');
    html += portfolioCard('fa-scale-balanced', 'Total Equity', formatCurrency(stats.totalEquity), 'neutral');
    html += portfolioCard('fa-arrow-trend-up', 'Floating PnL', formatPnl(stats.floatingPnl), pnlSentiment(stats.floatingPnl));
    html += portfolioCard('fa-calendar-day', 'Daily PnL', formatPnl(stats.dailyPnl), pnlSentiment(stats.dailyPnl));
    html += portfolioCard('fa-layer-group', 'Open Positions', stats.openPositions.toString(), 'neutral');
    html += portfolioCard('fa-sack-dollar', 'Realized PnL', formatPnl(stats.realizedPnl), pnlSentiment(stats.realizedPnl));
    html += portfolioCard('fa-gauge-high', 'Margin Usage', stats.marginUsage + '%', 'warning');
    html += portfolioCard('fa-bullseye', 'Win Rate', stats.winRate + '%', 'positive');
    html += '</div></section>';
    html += '<div class="chart-container"><div class="chart-header"><span class="chart-title">Equity Curve</span><span class="chart-period">Last 90 Days</span></div>';
    html += '<div class="chart-wrapper"><canvas id="equityChart"></canvas></div></div>';
    html += '<section><div class="section-header"><i class="fa-solid fa-server"></i><h2>Fleet Overview</h2><span class="section-badge">LIVE</span></div>';
    html += '<div id="dashboard-fleet-content" class="dashboard-fleet-section">';
    html += '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading fleet data...</p></div>';
    html += '</div></section></div>';
    document.getElementById('main-content').innerHTML = html;
    renderEquityChart();
    _fetchDashboardFleet();
    _fleetInterval = setInterval(_fetchDashboardFleet, 10000);
  }

  function destroy() {
    if (_fleetInterval) { clearInterval(_fleetInterval); _fleetInterval = null; }
    if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
  }

  function onThemeChange() {
    var canvas = document.getElementById('equityChart');
    if (canvas && chartInstance) renderEquityChart();
  }

  return { render: render, onThemeChange: onThemeChange, destroy: destroy, _openWorker: _openWorker };
})();
