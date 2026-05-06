var App = (function () {
  'use strict';

  var currentPage = 'dashboard';
  var _selectedWorker = null;

  var pageIcons = {
    dashboard: 'fa-grip', fleet: 'fa-server', portfolio: 'fa-chart-line',
    strategies: 'fa-crosshairs', logs: 'fa-scroll', settings: 'fa-gear'
  };

  var pageDescriptions = {
    portfolio: 'Detailed portfolio analytics with position breakdown, trade history, and performance metrics.',
    strategies: 'Strategy deployment, configuration, and live performance tracking across all worker nodes.',
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
    var navItems = document.querySelectorAll('#sidebar-nav .nav-item');
    navItems.forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        navigateTo(item.getAttribute('data-page'));
      });
    });
  }

  function navigateTo(page) {
    // Cleanup previous page
    if (currentPage === 'dashboard') DashboardRenderer.destroy();
    if (currentPage === 'fleet') FleetRenderer.destroy();
    if (currentPage === 'workerDetail') WorkerDetailRenderer.destroy();

    currentPage = page;

    // Update active nav (workerDetail highlights fleet)
    var navPage = (page === 'workerDetail') ? 'fleet' : page;
    document.querySelectorAll('#sidebar-nav .nav-item').forEach(function (item) {
      item.classList.toggle('active', item.getAttribute('data-page') === navPage);
    });

    // Update topbar
    var titleMap = { workerDetail: 'Worker Detail' };
    var title = titleMap[page] || (page.charAt(0).toUpperCase() + page.slice(1));
    document.getElementById('topbar-title').textContent = title;

    // Render page
    if (page === 'dashboard') {
      DashboardRenderer.render();
    } else if (page === 'fleet') {
      FleetRenderer.render();
    } else if (page === 'workerDetail' && _selectedWorker) {
      WorkerDetailRenderer.render(_selectedWorker);
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
      '<div class="placeholder-page">' +
        '<i class="fa-solid ' + icon + '"></i>' +
        '<h2>' + title + '</h2>' +
        '<p>' + desc + '</p>' +
      '</div>';
  }

  function startClock() {
    function update() {
      var now = new Date();
      var h = String(now.getHours()).padStart(2, '0');
      var m = String(now.getMinutes()).padStart(2, '0');
      var s = String(now.getSeconds()).padStart(2, '0');
      document.getElementById('topbar-clock').textContent = h + ':' + m + ':' + s;
    }
    update();
    setInterval(update, 1000);
  }

  document.addEventListener('DOMContentLoaded', init);

  return { navigateTo: navigateTo, navigateToWorkerDetail: navigateToWorkerDetail };
})();
