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
          '<div class="loading-state" style="min-height:120px;"><div class="spinner"></div><p>Loading strategies\u2026</p></div>' +
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
    area.addEventListener('click', function () { input.click(); });
    input.addEventListener('change', function () {
      if (!input.files || !input.files[0]) return;
      var file = input.files[0];
      if (!file.name.endsWith('.py')) { ToastManager.show('Only .py files accepted.', 'error'); return; }
      _upload(file);
    });
  }

  function _upload(file) {
    var el = document.getElementById('strat-upload-status');
    el.innerHTML = '<div class="wd-file-status" style="color:var(--accent);"><i class="fa-solid fa-spinner fa-spin"></i> Uploading &amp; validating\u2026</div>';

    ApiClient.uploadStrategy(file).then(function (data) {
      el.innerHTML = '<div class="wd-file-status" style="color:var(--success);"><i class="fa-solid fa-circle-check"></i> Registered: ' + (data.strategy_name || data.strategy_id) + '</div>';
      ToastManager.show('Strategy registered: ' + (data.strategy_name || data.strategy_id), 'success');
      _fetch();
    }).catch(function (err) {
      el.innerHTML = '<div class="wd-file-status" style="color:var(--danger);"><i class="fa-solid fa-circle-xmark"></i> ' + err.message + '</div>';
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
        var statusLabel = s.validation_status === 'validated' ? 'Validated' : (s.validation_status || 'Unknown');
        var uploaded = s.uploaded_at ? s.uploaded_at.replace('T', ' ').substring(0, 19) : '\u2014';
        html += '<tr>' +
          '<td class="mono">' + s.strategy_id + '</td>' +
          '<td>' + (s.strategy_name || s.strategy_id) + '</td>' +
          '<td class="mono">' + (s.version || '\u2014') + '</td>' +
          '<td class="mono">' + (s.parameter_count || 0) + '</td>' +
          '<td><span class="state-pill ' + statusClass + '">' + statusLabel.toUpperCase() + '</span></td>' +
          '<td class="mono">' + uploaded + '</td>' +
          '</tr>';
      });

      html += '</tbody></table></div>';

      // Description/error details below table
      list.forEach(function (s) {
        if (s.description || s.error) {
          html += '<div style="margin-top:8px;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;font-size:11.5px;">';
          html += '<strong class="mono" style="color:var(--accent);">' + s.strategy_id + '</strong>';
          if (s.description) html += '<span style="color:var(--text-secondary);margin-left:8px;">' + s.description + '</span>';
          if (s.error) html += '<span style="color:var(--danger);margin-left:8px;">Error: ' + s.error + '</span>';
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
    if (_refreshInterval) { clearInterval(_refreshInterval); _refreshInterval = null; }
  }

  return { render: render, destroy: destroy, _retry: _fetch };
})();