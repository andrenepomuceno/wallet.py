(function () {
  window.setupAsyncFilterForm = function setupAsyncFilterForm(config) {
    const form = document.getElementById(config.formId);
    const tableContainer = document.getElementById(config.tableContainerId);
    const messageContainer = document.getElementById(config.messageContainerId);

    if (!form || !tableContainer || !messageContainer) {
      return;
    }

    function renderError(message) {
      messageContainer.innerHTML =
        '<div class="alert alert-warning alert-dismissible fade show py-2 mb-2" role="alert">' +
        message +
        '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>' +
        '</div>';
    }

    function clearMessages() {
      messageContainer.innerHTML = '';
    }

    function refreshBootstrapTable() {
      if (!window.$) return;
      const table = tableContainer.querySelector('[data-toggle="table"]');
      if (table) {
        window.$(table).bootstrapTable();
      }
    }

    form.addEventListener('submit', async function (event) {
      event.preventDefault();

      const submitBtn = form.querySelector('[type="submit"]');
      const originalBtnText = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Filtrando...';
      }

      clearMessages();
      try {
        const response = await fetch(config.endpoint, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          },
          body: new FormData(form),
        });

        if (!response.ok) {
          throw new Error('HTTP ' + response.status);
        }

        const payload = await response.json();
        if (payload.table_html) {
          tableContainer.innerHTML = payload.table_html;
          refreshBootstrapTable();
        }
      } catch (error) {
        renderError('Falha ao aplicar filtro. Tente novamente.');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;
        }
      }
    });

    if (config.resetButtonId) {
      const resetButton = document.getElementById(config.resetButtonId);
      if (resetButton) {
        resetButton.addEventListener('click', async function () {
          form.reset();

          const submitBtn = form.querySelector('[type="submit"]');
          const originalBtnText = submitBtn ? submitBtn.innerHTML : '';
          if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Atualizando...';
          }

          clearMessages();
          try {
            const formResponse = await fetch(config.endpoint, {
              method: 'POST',
              headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json',
              },
              body: new FormData(form),
            });
            if (!formResponse.ok) {
              throw new Error('HTTP ' + formResponse.status);
            }
            const payload = await formResponse.json();
            if (payload.table_html) {
              tableContainer.innerHTML = payload.table_html;
              refreshBootstrapTable();
            }
          } catch (error) {
            renderError('Falha ao limpar filtro.');
          } finally {
            if (submitBtn) {
              submitBtn.disabled = false;
              submitBtn.innerHTML = originalBtnText;
            }
          }
        });
      }
    }
  };
})();
