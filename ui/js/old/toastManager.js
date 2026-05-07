/* toastManager.js */

var ToastManager = (function () {
  'use strict';

  var iconMap = {
    success: 'fa-circle-check',
    info: 'fa-circle-info',
    warning: 'fa-triangle-exclamation',
    error: 'fa-circle-xmark'
  };

  function _getContainer() {
    var container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  function show(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    var container = _getContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML =
      '<i class="fa-solid ' + (iconMap[type] || iconMap.info) + '"></i>' +
      '<span>' + message + '</span>' +
      '<button class="toast-dismiss"><i class="fa-solid fa-xmark"></i></button>';

    container.appendChild(toast);

    var dismiss = toast.querySelector('.toast-dismiss');
    dismiss.addEventListener('click', function () { _remove(toast); });

    setTimeout(function () { _remove(toast); }, duration);
  }

  function _remove(toast) {
    if (!toast || !toast.parentNode) return;
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }

  return { show: show };
})();
