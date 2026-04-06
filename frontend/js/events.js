/**
 * VigIA Events / Bitácora page
 */

const EventsPage = (() => {

  async function render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h4 class="mb-0 fw-bold"><i class="bi bi-journal-text me-2 text-warning"></i>Bitácora de Accesos</h4>
        <div class="d-flex gap-2">
          <button class="btn btn-sm btn-outline-secondary" id="btnExportCsv">
            <i class="bi bi-filetype-csv me-1"></i>Exportar CSV
          </button>
          <button class="btn btn-sm btn-outline-primary" id="btnManualEntry">
            <i class="bi bi-plus-lg me-1"></i>Entrada manual
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="card bg-dark border-secondary mb-3">
        <div class="card-body py-2">
          <div class="row g-2 align-items-end">
            <div class="col-md-3">
              <label class="form-label form-label-sm text-muted mb-1">Buscar persona</label>
              <div class="input-group input-group-sm">
                <span class="input-group-text bg-dark border-secondary"><i class="bi bi-search"></i></span>
                <input type="text" id="evSearch" class="form-control bg-dark border-secondary text-white"
                       placeholder="Nombre..." />
              </div>
            </div>
            <div class="col-md-2">
              <label class="form-label form-label-sm text-muted mb-1">Tipo</label>
              <select id="evTipo" class="form-select form-select-sm bg-dark border-secondary text-white">
                <option value="">Todos</option>
                <option value="entrada">Entrada</option>
                <option value="salida">Salida</option>
              </select>
            </div>
            <div class="col-md-2">
              <label class="form-label form-label-sm text-muted mb-1">Desde</label>
              <input type="date" id="evDesde" class="form-control form-control-sm bg-dark border-secondary text-white" />
            </div>
            <div class="col-md-2">
              <label class="form-label form-label-sm text-muted mb-1">Hasta</label>
              <input type="date" id="evHasta" class="form-control form-control-sm bg-dark border-secondary text-white" />
            </div>
            <div class="col-md-2">
              <button class="btn btn-sm btn-primary w-100" id="btnFilterEvents">
                <i class="bi bi-funnel me-1"></i>Filtrar
              </button>
            </div>
            <div class="col-md-1">
              <button class="btn btn-sm btn-outline-secondary w-100" id="btnClearFilter" title="Limpiar">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Events table -->
      <div class="card bg-dark border-secondary">
        <div class="card-body p-0">
          <div class="table-responsive">
            <table class="table table-dark table-hover table-sm mb-0">
              <thead>
                <tr>
                  <th>#</th><th>Fecha/Hora</th><th>Persona</th><th>Tipo</th>
                  <th>Confianza</th><th>Objetos</th><th>Notif.</th><th>Notas</th>
                </tr>
              </thead>
              <tbody id="eventsBody">
                <tr><td colspan="8" class="text-center py-5">
                  <div class="spinner-border text-primary spinner-border-sm me-2"></div>Cargando...
                </td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card-footer border-secondary d-flex justify-content-between align-items-center">
          <small class="text-muted" id="evCount">—</small>
          <div class="btn-group btn-group-sm" id="evPagination"></div>
        </div>
      </div>

      <!-- Manual entry modal -->
      <div class="modal fade" id="manualEntryModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title">Entrada Manual en Bitácora</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="mb-3">
                <label class="form-label">Tipo de acceso</label>
                <select class="form-select" id="meType">
                  <option value="entrada">Entrada</option>
                  <option value="salida">Salida</option>
                </select>
              </div>
              <div class="mb-3">
                <label class="form-label">Tipo de persona</label>
                <select class="form-select" id="mePersonType" onchange="EventsPage.togglePersonFields()">
                  <option value="">Desconocido</option>
                  <option value="visitor">Visitante</option>
                  <option value="resident">Residente</option>
                </select>
              </div>
              <div id="meVisitorRow" class="mb-3 d-none">
                <label class="form-label">ID del Visitante</label>
                <input type="number" class="form-control" id="meVisitorId" placeholder="ID del visitante" min="1" />
              </div>
              <div id="meResidentRow" class="mb-3 d-none">
                <label class="form-label">ID del Residente</label>
                <input type="number" class="form-control" id="meResidentId" placeholder="ID del residente" min="1" />
              </div>
              <div class="mb-3">
                <label class="form-label">Notas</label>
                <textarea class="form-control" id="meNotes" rows="3" placeholder="Observaciones del guardia..."></textarea>
              </div>
            </div>
            <div class="modal-footer border-secondary">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-primary" id="btnSaveManualEntry">
                <i class="bi bi-check-lg me-1"></i>Guardar
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    setupListeners();
    loadEvents();
  }

  let currentSkip = 0;
  const PAGE_SIZE = 30;

  async function loadEvents(skip = 0) {
    currentSkip = skip;
    const params = { skip, limit: PAGE_SIZE };

    const search = document.getElementById('evSearch')?.value?.trim();
    const tipo   = document.getElementById('evTipo')?.value;
    const desde  = document.getElementById('evDesde')?.value;
    const hasta  = document.getElementById('evHasta')?.value;

    if (search) params.search = search;
    if (tipo)   params.tipo = tipo;
    if (desde)  params.fecha_inicio = desde;
    if (hasta)  params.fecha_fin = hasta;

    try {
      const logs = await Api.getEvents(params);
      renderTable(logs);
      renderPagination(logs.length);
    } catch (e) {
      document.getElementById('eventsBody').innerHTML =
        `<tr><td colspan="8" class="text-center text-danger py-4">${e.message}</td></tr>`;
    }
  }

  function renderTable(logs) {
    const tbody = document.getElementById('eventsBody');
    document.getElementById('evCount').textContent = `${logs.length} registro(s)`;

    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-5 text-muted">Sin registros encontrados</td></tr>';
      return;
    }

    tbody.innerHTML = logs.map(log => {
      const nombre = log.visitor?.nombre || log.resident?.nombre || 'Desconocido';
      const icon   = log.resident_id ? '🏠' : log.visitor_id ? '👤' : '❓';
      const ts     = fmtDateTime(log.timestamp);
      const badge  = log.tipo === 'entrada' ? 'bg-success' : 'bg-secondary';
      const conf   = log.confianza_facial !== null && log.confianza_facial !== undefined
                       ? log.confianza_facial
                       : null;
      const confPct = conf !== null ? Math.round(conf * 100) : null;
      const confClass = confPct === null ? '' : confPct >= 70 ? 'conf-high' : confPct >= 50 ? 'conf-med' : 'conf-low';

      let objetos = '—';
      if (log.objetos_detectados) {
        try { objetos = JSON.parse(log.objetos_detectados).join(', ') || '—'; }
        catch {}
      }

      return `
        <tr>
          <td class="text-muted small">${log.id}</td>
          <td class="text-muted small">${ts}</td>
          <td>
            <span class="me-1">${icon}</span>
            <strong>${nombre}</strong>
          </td>
          <td><span class="badge ${badge}">${log.tipo}</span></td>
          <td class="${confClass} small fw-semibold">
            ${confPct !== null ? confPct + '%' : '—'}
          </td>
          <td class="text-muted small">${objetos}</td>
          <td>
            ${log.notificacion_enviada
              ? '<i class="bi bi-bell-fill text-success" title="Enviada"></i>'
              : '<i class="bi bi-bell-slash text-muted" title="No enviada"></i>'
            }
          </td>
          <td class="text-muted small">${log.notas || '—'}</td>
        </tr>
      `;
    }).join('');
  }

  function renderPagination(count) {
    const pag = document.getElementById('evPagination');
    pag.innerHTML = `
      <button class="btn btn-outline-secondary" ${currentSkip === 0 ? 'disabled' : ''}
              onclick="EventsPage.loadMore(${Math.max(0, currentSkip - PAGE_SIZE)})">
        <i class="bi bi-chevron-left"></i>
      </button>
      <button class="btn btn-outline-secondary" disabled>
        ${Math.floor(currentSkip / PAGE_SIZE) + 1}
      </button>
      <button class="btn btn-outline-secondary" ${count < PAGE_SIZE ? 'disabled' : ''}
              onclick="EventsPage.loadMore(${currentSkip + PAGE_SIZE})">
        <i class="bi bi-chevron-right"></i>
      </button>
    `;
  }

  function setupListeners() {
    document.getElementById('btnFilterEvents').addEventListener('click', () => loadEvents(0));

    document.getElementById('btnClearFilter').addEventListener('click', () => {
      document.getElementById('evSearch').value = '';
      document.getElementById('evTipo').value = '';
      document.getElementById('evDesde').value = '';
      document.getElementById('evHasta').value = '';
      loadEvents(0);
    });

    document.getElementById('btnExportCsv').addEventListener('click', () => {
      const params = {};
      const desde = document.getElementById('evDesde').value;
      const hasta = document.getElementById('evHasta').value;
      if (desde) params.fecha_inicio = desde;
      if (hasta) params.fecha_fin = hasta;
      Api.exportCsv(params);
    });

    document.getElementById('btnManualEntry').addEventListener('click', () => {
      document.getElementById('meNotes').value = '';
      document.getElementById('mePersonType').value = '';
      document.getElementById('meVisitorRow').classList.add('d-none');
      document.getElementById('meResidentRow').classList.add('d-none');
      new bootstrap.Modal(document.getElementById('manualEntryModal')).show();
    });

    document.getElementById('btnSaveManualEntry').addEventListener('click', saveManualEntry);

    document.getElementById('evSearch').addEventListener('keypress', (e) => {
      if (e.key === 'Enter') loadEvents(0);
    });
  }

  function togglePersonFields() {
    const val = document.getElementById('mePersonType').value;
    document.getElementById('meVisitorRow').classList.toggle('d-none', val !== 'visitor');
    document.getElementById('meResidentRow').classList.toggle('d-none', val !== 'resident');
  }

  async function saveManualEntry() {
    const tipo       = document.getElementById('meType').value;
    const personType = document.getElementById('mePersonType').value;
    const visitorId  = document.getElementById('meVisitorId').value;
    const residentId = document.getElementById('meResidentId').value;
    const notas      = document.getElementById('meNotes').value.trim();

    const body = { tipo, notas: notas || null };
    if (personType === 'visitor' && visitorId) body.visitor_id = parseInt(visitorId);
    if (personType === 'resident' && residentId) body.resident_id = parseInt(residentId);

    const btn = document.getElementById('btnSaveManualEntry');
    btn.disabled = true;
    try {
      await Api.createManualLog(body);
      App.showToast('Registro guardado en bitácora', 'success');
      bootstrap.Modal.getInstance(document.getElementById('manualEntryModal')).hide();
      loadEvents(0);
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  return { render, loadMore: loadEvents, togglePersonFields };
})();
