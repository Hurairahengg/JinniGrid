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
          } catch (e) { if (text) msg = text; }
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
          } catch (e) { if (text) msg = text; }
          throw new Error(msg);
        });
      }
      return res.json();
    });
  }

  return {
    /* Fleet */
    getFleetWorkers:   function ()   { return _request('GET',  '/api/Grid/workers'); },
    getSystemSummary:  function ()   { return _request('GET',  '/api/system/summary'); },
    getHealth:         function ()   { return _request('GET',  '/api/health'); },

    /* Strategies */
    getStrategies:     function ()     { return _request('GET',  '/api/grid/strategies'); },
    getStrategy:       function (id)   { return _request('GET',  '/api/grid/strategies/' + encodeURIComponent(id)); },
    uploadStrategy:    function (file) { return _upload('/api/grid/strategies/upload', file); },
    validateStrategy:  function (id)   { return _request('POST', '/api/grid/strategies/' + encodeURIComponent(id) + '/validate'); },

    /* Deployments */
    createDeployment:  function (cfg)  { return _request('POST', '/api/grid/deployments', cfg); },
    getDeployments:    function ()     { return _request('GET',  '/api/grid/deployments'); },
    getDeployment:     function (id)   { return _request('GET',  '/api/grid/deployments/' + encodeURIComponent(id)); },
    stopDeployment:    function (id)   { return _request('POST', '/api/grid/deployments/' + encodeURIComponent(id) + '/stop'); },
  };
})();