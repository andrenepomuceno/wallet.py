(function () {
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function ensureToastContainer() {
    let container = document.getElementById('appToastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'appToastContainer';
      container.className = 'toast-container position-fixed top-0 end-0 p-3';
      container.style.zIndex = '1080';
      document.body.appendChild(container);
    }
    return container;
  }

  function showToast(message, level) {
    if (!window.bootstrap) return;

    const bgClassByLevel = {
      success: 'text-bg-success',
      warning: 'text-bg-warning',
      danger: 'text-bg-danger',
      info: 'text-bg-info',
    };

    const toastClass = bgClassByLevel[level] || bgClassByLevel.info;
    const container = ensureToastContainer();
    const wrapper = document.createElement('div');

    wrapper.innerHTML =
      '<div class="toast align-items-center ' + toastClass + ' border-0" role="alert" aria-live="assertive" aria-atomic="true">' +
      '<div class="d-flex">' +
      '<div class="toast-body">' + escapeHtml(message) + '</div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
      '</div>' +
      '</div>';

    const toastEl = wrapper.firstChild;
    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 3500 });
    toast.show();

    toastEl.addEventListener('hidden.bs.toast', function () {
      toastEl.remove();
    });
  }

  window.asyncUI = {
    escapeHtml: escapeHtml,
    showToast: showToast,
  };
})();
