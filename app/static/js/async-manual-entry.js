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

  function renderMessages(container, payload) {
    if (!container) return;

    const messages = payload.messages || [];
    const errors = payload.errors || [];

    if (!messages.length && !errors.length) {
      container.innerHTML = '';
      return;
    }

    let html = '';
    messages.forEach((message) => {
      html += '<div class="alert alert-success alert-dismissible fade show py-2 mb-2" role="alert">';
      html += escapeHtml(message);
      html += '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
      html += '</div>';
    });

    errors.forEach((error) => {
      html += '<div class="alert alert-warning alert-dismissible fade show py-2 mb-2" role="alert">';
      html += escapeHtml(error);
      html += '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
      html += '</div>';
    });

    container.innerHTML = html;
  }

  function refreshBootstrapTable(tableContainer) {
    if (!tableContainer || !window.$) return;
    const table = tableContainer.querySelector('[data-toggle="table"]');
    if (table) {
      window.$(table).bootstrapTable();
    }
  }

  window.setupAsyncManualEntry = function setupAsyncManualEntry(config) {
    const form = document.getElementById(config.formId);
    const tableContainer = document.getElementById(config.tableContainerId);
    const messageContainer = document.getElementById(config.messageContainerId);

    if (!form || !tableContainer || !messageContainer) {
      return;
    }

    form.addEventListener('submit', async function (event) {
      event.preventDefault();

      const submitBtn = form.querySelector('[type="submit"]');
      const originalBtnText = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Salvando...';
      }

      try {
        const response = await fetch(config.endpoint, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          },
          body: new FormData(form),
        });

        const payload = await response.json();

        renderMessages(messageContainer, payload);

        (payload.messages || []).forEach(function (message) {
          if (window.asyncUI && window.asyncUI.showToast) {
            window.asyncUI.showToast(message, 'success');
          }
        });
        (payload.errors || []).forEach(function (errorMessage) {
          if (window.asyncUI && window.asyncUI.showToast) {
            window.asyncUI.showToast(errorMessage, 'warning');
          }
        });

        if (payload.success && payload.table_html) {
          tableContainer.innerHTML = payload.table_html;
          refreshBootstrapTable(tableContainer);
          form.reset();
        }
      } catch (error) {
        renderMessages(messageContainer, {
          errors: ['Falha ao salvar entrada. Tente novamente.'],
        });
        if (window.asyncUI && window.asyncUI.showToast) {
          window.asyncUI.showToast('Falha ao salvar entrada. Tente novamente.', 'danger');
        }
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;
        }
      }
    });
  };
})();
