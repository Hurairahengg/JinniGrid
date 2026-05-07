/* app.js */

var App = (function () {
  'use strict';

  var currentPage = 'dashboard';
  var _selectedWorker = null;

  var pageIcons = {
    dashboard: 'fa-grip', fleet: 'fa-server', portfolio: 'fa-chart-line',
    strategies: 'fa-crosshairs', logs: 'fa-scroll', settings: 'fa-gear'
  };

  var pageDescriptions = {
    portfolio: 'Portfolio analytics will be available when trade execution is implemented.',
    logs: 'Centralized log aggregation, real-time streaming, and advanced search across all fleet nodes.',
    settings: 'System configuration, user preferences, notification settings, and connection management.'
  };

  function init() {
    ThemeManager.init();
    setupNavigation();
    startClock();
    navigateTo('dashboard');
  }

  function setupNavigation() {
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        navigateTo(item.getAttribute('data-page'));
      });
    });
  }

  function navigateTo(page) {
    if (currentPage === 'dashboard')    DashboardRenderer.destroy();
    if (currentPage === 'fleet')        FleetRenderer.destroy();
    if (currentPage === 'workerDetail') WorkerDetailRenderer.destroy();
    if (currentPage === 'strategies')   StrategiesRenderer.destroy();

    currentPage = page;

    var navPage = (page === 'workerDetail') ? 'fleet' : page;
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.classList.toggle('active', item.getAttribute('data-page') === navPage);
    });

    var titleMap = { workerDetail: 'Worker Detail' };
    var title = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));
    document.getElementById('topbar-title').textContent = title;

    if (page === 'dashboard') {
      DashboardRenderer.render();
    } else if (page === 'fleet') {
      FleetRenderer.render();
    } else if (page === 'workerDetail' && _selectedWorker) {
      WorkerDetailRenderer.render(_selectedWorker);
    } else if (page === 'strategies') {
      StrategiesRenderer.render();
    } else {
      renderPlaceholder(page);
    }
  }

  function navigateToWorkerDetail(workerData) {
    _selectedWorker = workerData;
    navigateTo('workerDetail');
  }

  function renderPlaceholder(page) {
    var icon = pageIcons[page] || 'fa-circle-question';
    var title = page.charAt(0).toUpperCase() + page.slice(1);
    var desc = pageDescriptions[page] || 'This section is under development.';
    document.getElementById('main-content').innerHTML =
      '<div class="placeholder-page"><i class="fa-solid ' + icon + '"></i>' +
      '<h2>' + title + '</h2><p>' + desc + '</p></div>';
  }

  function startClock() {
    function update() {
      var now = new Date();
      document.getElementById('topbar-clock').textContent =
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0') + ':' +
        String(now.getSeconds()).padStart(2, '0');
    }
    update();
    setInterval(update, 1000);
  }

  document.addEventListener('DOMContentLoaded', init);

  return { navigateTo: navigateTo, navigateToWorkerDetail: navigateToWorkerDetail };
})();