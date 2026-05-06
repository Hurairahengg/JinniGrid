var ThemeManager = (function () {
  'use strict';

  var STORAGE_KEY = 'jinni-Grid-theme';
  var currentTheme = 'dark';

  function init() {
    var saved = localStorage.getItem(STORAGE_KEY);
    currentTheme = (saved === 'light') ? 'light' : 'dark';
    applyTheme();
    updateToggleButton();
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggle);
  }

  function toggle() {
    currentTheme = (currentTheme === 'dark') ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, currentTheme);
    applyTheme();
    updateToggleButton();
    if (typeof DashboardRenderer !== 'undefined' && DashboardRenderer.onThemeChange) {
      DashboardRenderer.onThemeChange();
    }
  }

  function applyTheme() {
    document.body.setAttribute('data-theme', currentTheme);
  }

  function updateToggleButton() {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var icon = btn.querySelector('i');
    var label = btn.querySelector('span');
    if (currentTheme === 'dark') {
      icon.className = 'fa-solid fa-sun';
      label.textContent = 'Light Mode';
    } else {
      icon.className = 'fa-solid fa-moon';
      label.textContent = 'Dark Mode';
    }
  }

  function getTheme() { return currentTheme; }

  return { init: init, toggle: toggle, getTheme: getTheme };
})();
