var ModalManager = (function () {
  'use strict';

  var _overlay = null;

  function show(options) {
    hide();
    var title = options.title || 'Confirm';
    var bodyHtml = options.bodyHtml || '';
    var confirmText = options.confirmText || 'Confirm';
    var cancelText = options.cancelText || 'Cancel';
    var type = options.type || 'default';
    var onConfirm = options.onConfirm || function () {};

    var confirmClass = type === 'danger' ? 'wd-btn wd-btn-primary' : 'wd-btn wd-btn-primary';
    var confirmStyle = type === 'danger' ? ' style="background:var(--danger);"' : '';

    _overlay = document.createElement('div');
    _overlay.className = 'modal-overlay';
    _overlay.innerHTML =
      '<div class="modal-card">' +
        '<div class="modal-header">' +
          '<span class="modal-title">' + title + '</span>' +
          '<button class="modal-close" id="modal-close">&times;</button>' +
        '</div>' +
        '<div class="modal-body">' + bodyHtml + '</div>' +
        '<div class="modal-footer">' +
          '<button class="wd-btn wd-btn-ghost" id="modal-cancel">' + cancelText + '</button>' +
          '<button class="' + confirmClass + '" id="modal-confirm"' + confirmStyle + '>' + confirmText + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(_overlay);

    _overlay.querySelector('#modal-close').addEventListener('click', hide);
    _overlay.querySelector('#modal-cancel').addEventListener('click', hide);
    _overlay.querySelector('#modal-confirm').addEventListener('click', function () {
      onConfirm();
      hide();
    });
    _overlay.addEventListener('click', function (e) {
      if (e.target === _overlay) hide();
    });

    var escHandler = function (e) {
      if (e.key === 'Escape') { hide(); document.removeEventListener('keydown', escHandler); }
    };
    document.addEventListener('keydown', escHandler);
  }

  function hide() {
    if (_overlay && _overlay.parentNode) {
      _overlay.parentNode.removeChild(_overlay);
    }
    _overlay = null;
  }

  return { show: show, hide: hide };
})();
