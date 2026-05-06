
/* apiClient.js */


var ApiClient = (function () {
  'use strict';

  function _request(method, path) {
    return fetch(path, { method: method })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      });
  }

  return {
    getFleetWorkers: function () { return _request('GET', '/api/Grid/workers'); },
    getSystemSummary: function () { return _request('GET', '/api/system/summary'); },
    getHealth: function () { return _request('GET', '/api/health'); }
  };
})();
