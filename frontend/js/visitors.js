/**
 * VigIA Visitors page
 */

const VisitorsPage = (() => {
  let editingId = null;
  let uploadingFaceForId = null;

  async function render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h4 class="mb-0 fw-bold"><i class="bi bi-person-badge me-2 text-info"></i>Visitantes</h4>
        <button class="btn btn-primary btn-sm" id="btnNewVisitor">
          <i class="bi bi-plus-lg me-1"></i>Nuevo visitante
        </button>
      </div>

      <!-- Search -->
      <div class="card bg-dark border-secondary mb-3">
        <div class="card-body py-2">
          <div class="input-group input-group-sm">
            <span class="input-group-text bg-dark border-secondary"><i class="bi bi-search"></i></span>
            <input type="text" id="visitorSearch" class="form-control bg-dark border-secondary text-white"
                   placeholder="Buscar por nombre o documento..." />
          </div>
        </div>
      </div>

      <!-- Table -->
      <div class="card bg-dark border-secondary">
        <div class="card-body p-0">
          <div class="table-responsive">
            <table class="table table-dark table-hover table-sm mb-0">
              <thead>
                <tr>
                  <th>Foto</th><th>Nombre</th><th>Documento</th>
                  <th>Apto. destino</th><th>Teléfono</th><th>Última visita</th>
                  <th>Visitas</th><th>Facial</th><th>Acciones</th>
                </tr>
              </thead>
              <tbody id="visitorsBody">
                <tr><td colspan="9" class="text-center py-5">
                  <div class="spinner-border text-primary spinner-border-sm me-2"></div>Cargando...
                </td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card-footer border-secondary">
          <small class="text-muted" id="visitorCount">—</small>
        </div>
      </div>

      <!-- Add/Edit Modal -->
      <div class="modal fade" id="visitorModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title" id="visitorModalTitle">Nuevo Visitante</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <form id="visitorForm">
                <div class="row g-3">
                  <div class="col-12">
                    <label class="form-label">Nombre completo <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="vNombre" required />
                  </div>
                  <div class="col-6">
                    <label class="form-label">Documento</label>
                    <input type="text" class="form-control" id="vDocumento" placeholder="CC/CE/PA..." />
                  </div>
                  <div class="col-6">
                    <label class="form-label">Teléfono</label>
                    <input type="tel" class="form-control" id="vTelefono" placeholder="+57 300..." />
                  </div>
                  <div class="col-12">
                    <label class="form-label"><i class="bi bi-house-door me-1 text-warning"></i>Visita al apartamento <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="vApartamento" placeholder="Ej: 514, 302-B..." required />
                  </div>
                </div>
              </form>
            </div>
            <div class="modal-footer border-secondary">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-primary" id="btnSaveVisitor">
                <i class="bi bi-check-lg me-1"></i>Guardar
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Face enrollment modal -->
      <div class="modal fade" id="visitorFaceModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title"><i class="bi bi-person-bounding-box me-2"></i>Registrar Rostro del Visitante</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <ul class="nav nav-tabs nav-tabs-dark mb-3" id="vFaceTabs">
                <li class="nav-item">
                  <button class="nav-link active" id="vTabFile" data-tab="file">
                    <i class="bi bi-folder2-open me-1"></i>Subir archivo
                  </button>
                </li>
                <li class="nav-item">
                  <button class="nav-link" id="vTabCamera" data-tab="camera">
                    <i class="bi bi-camera me-1"></i>Capturar de cámara
                  </button>
                </li>
              </ul>
              <div id="vFaceTabFile">
                <input type="file" class="form-control" id="vFaceFileInput" accept="image/*" />
                <div class="form-text">Foto clara de frente, buena iluminación.</div>
              </div>
              <div id="vFaceTabCamera" class="d-none text-center">
                <img id="vFaceCamPreview" src="" class="img-fluid rounded mb-2"
                     style="max-height:200px;width:100%;object-fit:cover;background:#111" />
                <div class="d-flex gap-2 justify-content-center">
                  <button class="btn btn-sm btn-outline-primary" id="btnVLoadCamStream">
                    <i class="bi bi-play me-1"></i>Ver cámara
                  </button>
                  <button class="btn btn-sm btn-warning" id="btnVSnapFace">
                    <i class="bi bi-camera me-1"></i>Capturar foto
                  </button>
                </div>
              </div>
              <div id="vFacePreviewWrap" class="text-center d-none mt-2">
                <img id="vFacePreviewImg" src="" alt="Preview" class="img-thumbnail mb-2" style="max-height:180px" />
                <div class="small text-success"><i class="bi bi-check-circle me-1"></i>Listo para registrar</div>
              </div>
              <div id="vFaceAlertArea"></div>
            </div>
            <div class="modal-footer border-secondary">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-success" id="btnUploadVisitorFace" disabled>
                <i class="bi bi-person-check me-1"></i>Registrar rostro
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Visitor detail modal -->
      <div class="modal fade" id="visitorDetailModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title"><i class="bi bi-person-badge me-2"></i>Historial de Visitas</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body" id="visitorDetailBody">
              <div class="text-center py-4"><div class="spinner-border text-primary"></div></div>
            </div>
          </div>
        </div>
      </div>
    `;

    setupListeners();
    loadVisitors();
  }

  async function loadVisitors() {
    const search = document.getElementById('visitorSearch')?.value || '';
    const params = { limit: 100 };
    if (search) params.search = search;

    try {
      const visitors = await Api.getVisitors(params);
      renderTable(visitors);
    } catch (e) {
      document.getElementById('visitorsBody').innerHTML =
        `<tr><td colspan="9" class="text-center text-danger py-4">${e.message}</td></tr>`;
    }
  }

  function renderTable(visitors) {
    const tbody = document.getElementById('visitorsBody');
    document.getElementById('visitorCount').textContent = `${visitors.length} visitante(s)`;

    if (visitors.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-center py-5 text-muted">Sin visitantes registrados</td></tr>';
      return;
    }

    tbody.innerHTML = visitors.map(v => {
      const primera = fmtDate(v.primera_visita);
      const ultima  = fmtDate(v.ultima_visita);
      return `
        <tr>
          <td>
            ${v.foto_path
              ? `<img src="/data/faces/${v.foto_path.split('/').pop()}" class="face-thumb" onerror="this.src=''" />`
              : `<div class="face-thumb d-flex align-items-center justify-content-center bg-secondary">
                   <i class="bi bi-person text-muted"></i>
                 </div>`
            }
          </td>
          <td class="fw-semibold">${v.nombre}</td>
          <td class="text-muted small">${v.documento || '—'}</td>
          <td>${v.apartamento_destino ? `<span class="badge bg-warning text-dark"><i class="bi bi-house-door me-1"></i>${v.apartamento_destino}</span>` : '<span class="text-muted">—</span>'}</td>
          <td class="text-muted small">${v.telefono || '—'}</td>
          <td class="text-muted small">${ultima}</td>
          <td><span class="badge bg-info text-dark">${v.total_visitas}</span></td>
          <td>
            ${v.foto_path
              ? '<span class="badge bg-success"><i class="bi bi-check-lg"></i></span>'
              : '<span class="badge bg-secondary">—</span>'
            }
          </td>
          <td>
            <div class="btn-group btn-group-sm">
              <button class="btn btn-outline-primary" onclick="VisitorsPage.openEdit(${v.id})" title="Editar">
                <i class="bi bi-pencil"></i>
              </button>
              <button class="btn btn-outline-success" onclick="VisitorsPage.openFace(${v.id})" title="Foto">
                <i class="bi bi-person-bounding-box"></i>
              </button>
              <button class="btn btn-outline-info" onclick="VisitorsPage.showDetail(${v.id})" title="Historial">
                <i class="bi bi-clock-history"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  function setupListeners() {
    document.getElementById('btnNewVisitor').addEventListener('click', () => {
      editingId = null;
      document.getElementById('visitorModalTitle').textContent = 'Nuevo Visitante';
      document.getElementById('visitorForm').reset();
      new bootstrap.Modal(document.getElementById('visitorModal')).show();
    });

    document.getElementById('btnSaveVisitor').addEventListener('click', saveVisitor);

    const searchInput = document.getElementById('visitorSearch');
    let searchTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(loadVisitors, 400);
    });

    // Tab switching
    document.querySelectorAll('#vFaceTabs .nav-link').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#vFaceTabs .nav-link').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.getElementById('vFaceTabFile').classList.toggle('d-none', tab !== 'file');
        document.getElementById('vFaceTabCamera').classList.toggle('d-none', tab !== 'camera');
        document.getElementById('vFacePreviewWrap').classList.add('d-none');
        document.getElementById('btnUploadVisitorFace').disabled = true;
      });
    });

    document.getElementById('vFaceFileInput').addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        document.getElementById('vFacePreviewImg').src = ev.target.result;
        document.getElementById('vFacePreviewWrap').classList.remove('d-none');
        document.getElementById('btnUploadVisitorFace').disabled = false;
      };
      reader.readAsDataURL(file);
    });

    document.getElementById('btnVLoadCamStream').addEventListener('click', async () => {
      try {
        const cameras = await Api.getCameras();
        const first = cameras.find(c => c.activo);
        if (!first) { App.showToast('No hay cámaras activas', 'warning'); return; }
        document.getElementById('vFaceCamPreview').src = Api.getStreamUrl(first.id) + '?t=' + Date.now();
      } catch (e) { App.showToast('Error: ' + e.message, 'danger'); }
    });

    document.getElementById('btnVSnapFace').addEventListener('click', async () => {
      try {
        const cameras = await Api.getCameras();
        const first = cameras.find(c => c.activo);
        if (!first) { App.showToast('No hay cámaras activas', 'warning'); return; }
        const token = localStorage.getItem('vigia_token');
        const resp = await fetch(`${API_BASE}/cameras/${first.id}/snapshot`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (!resp.ok) throw new Error('Error al capturar');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        document.getElementById('vFacePreviewImg').src = url;
        document.getElementById('vFacePreviewWrap').classList.remove('d-none');
        const btn = document.getElementById('btnUploadVisitorFace');
        btn.disabled = false;
        btn.dataset.snapBlob = url;
        App.showToast('Foto capturada', 'success');
      } catch (e) { App.showToast('Error: ' + e.message, 'danger'); }
    });

    document.getElementById('btnUploadVisitorFace').addEventListener('click', uploadVisitorFace);
  }

  async function saveVisitor() {
    const btn = document.getElementById('btnSaveVisitor');
    const data = {
      nombre:               document.getElementById('vNombre').value.trim(),
      documento:            document.getElementById('vDocumento').value.trim() || null,
      telefono:             document.getElementById('vTelefono').value.trim() || null,
      apartamento_destino:  document.getElementById('vApartamento').value.trim() || null,
    };

    if (!data.nombre) {
      App.showToast('El nombre es requerido', 'warning');
      return;
    }

    btn.disabled = true;
    try {
      if (editingId) {
        await Api.updateVisitor(editingId, data);
        App.showToast('Visitante actualizado', 'success');
      } else {
        await Api.createVisitor(data);
        App.showToast('Visitante creado', 'success');
      }
      bootstrap.Modal.getInstance(document.getElementById('visitorModal')).hide();
      loadVisitors();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  async function openEdit(id) {
    editingId = id;
    try {
      const visitors = await Api.getVisitors({ limit: 200 });
      const v = visitors.find(x => x.id === id);
      if (!v) return;
      document.getElementById('visitorModalTitle').textContent = 'Editar Visitante';
      document.getElementById('vNombre').value = v.nombre;
      document.getElementById('vDocumento').value = v.documento || '';
      document.getElementById('vTelefono').value = v.telefono || '';
      document.getElementById('vApartamento').value = v.apartamento_destino || '';
      new bootstrap.Modal(document.getElementById('visitorModal')).show();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    }
  }

  function openFace(visitorId) {
    uploadingFaceForId = visitorId;
    document.getElementById('vFaceFileInput').value = '';
    document.getElementById('vFacePreviewWrap').classList.add('d-none');
    const btn = document.getElementById('btnUploadVisitorFace');
    btn.disabled = true;
    btn.dataset.snapBlob = '';
    document.getElementById('vFaceAlertArea').innerHTML = '';
    // Reset tabs
    document.querySelectorAll('#vFaceTabs .nav-link').forEach(b => b.classList.remove('active'));
    document.getElementById('vTabFile').classList.add('active');
    document.getElementById('vFaceTabFile').classList.remove('d-none');
    document.getElementById('vFaceTabCamera').classList.add('d-none');
    document.getElementById('vFaceCamPreview').src = '';
    new bootstrap.Modal(document.getElementById('visitorFaceModal')).show();
  }

  async function uploadVisitorFace() {
    if (!uploadingFaceForId) return;

    const btn = document.getElementById('btnUploadVisitorFace');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Procesando...';

    try {
      const fd = new FormData();
      const snapBlobUrl = btn.dataset.snapBlob;
      const fileInput = document.getElementById('vFaceFileInput');

      if (snapBlobUrl && snapBlobUrl.startsWith('blob:')) {
        const resp = await fetch(snapBlobUrl);
        const blob = await resp.blob();
        fd.append('file', blob, 'captura.jpg');
      } else if (fileInput.files[0]) {
        fd.append('file', fileInput.files[0]);
      } else {
        App.showToast('Selecciona o captura una foto primero', 'warning');
        return;
      }

      await Api.uploadVisitorFace(uploadingFaceForId, fd);
      document.getElementById('vFaceAlertArea').innerHTML =
        '<div class="alert alert-success py-2"><i class="bi bi-check-circle me-2"></i>Rostro registrado correctamente</div>';
      App.showToast('Rostro registrado', 'success');
      btn.dataset.snapBlob = '';
      setTimeout(() => {
        bootstrap.Modal.getInstance(document.getElementById('visitorFaceModal')).hide();
        loadVisitors();
      }, 1500);
    } catch (e) {
      document.getElementById('vFaceAlertArea').innerHTML =
        `<div class="alert alert-danger py-2"><i class="bi bi-exclamation-triangle me-2"></i>${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-person-check me-1"></i>Registrar rostro';
    }
  }

  async function showDetail(visitorId) {
    const modal = new bootstrap.Modal(document.getElementById('visitorDetailModal'));
    modal.show();

    try {
      const params = { visitor_id: visitorId, limit: 50 };
      const logs = await Api.getEvents(params);
      const visitors = await Api.getVisitors({ limit: 200 });
      const visitor = visitors.find(v => v.id === visitorId);

      const body = document.getElementById('visitorDetailBody');
      body.innerHTML = `
        <div class="d-flex align-items-center gap-3 mb-4">
          ${visitor?.foto_path
            ? `<img src="/data/faces/${visitor.foto_path.split('/').pop()}" class="rounded" style="width:60px;height:60px;object-fit:cover" />`
            : `<div class="d-flex align-items-center justify-content-center bg-secondary rounded" style="width:60px;height:60px"><i class="bi bi-person fs-3 text-muted"></i></div>`
          }
          <div>
            <h5 class="mb-0">${visitor?.nombre || 'Visitante'}</h5>
            <small class="text-muted">Doc: ${visitor?.documento || '—'} | Tel: ${visitor?.telefono || '—'}</small><br/>
            <span class="badge bg-info text-dark">${visitor?.total_visitas || 0} visitas totales</span>
          </div>
        </div>
        <h6 class="text-muted mb-2">Últimas visitas</h6>
        <div class="table-responsive">
          <table class="table table-dark table-sm">
            <thead><tr><th>Fecha/Hora</th><th>Tipo</th><th>Confianza</th><th>Objetos</th></tr></thead>
            <tbody>
              ${logs.length === 0
                ? '<tr><td colspan="4" class="text-center text-muted">Sin registros</td></tr>'
                : logs.map(log => {
                    const ts = fmtDateTime(log.timestamp);
                    const conf = log.confianza_facial ? `${(log.confianza_facial * 100).toFixed(0)}%` : '—';
                    const objs = log.objetos_detectados ? JSON.parse(log.objetos_detectados).join(', ') : '—';
                    return `
                      <tr>
                        <td class="small">${ts}</td>
                        <td><span class="badge ${log.tipo === 'entrada' ? 'bg-success' : 'bg-secondary'}">${log.tipo}</span></td>
                        <td class="small">${conf}</td>
                        <td class="small text-muted">${objs}</td>
                      </tr>
                    `;
                  }).join('')
              }
            </tbody>
          </table>
        </div>
      `;
    } catch (e) {
      document.getElementById('visitorDetailBody').innerHTML =
        `<div class="alert alert-danger">${e.message}</div>`;
    }
  }

  return { render, openEdit, openFace, showDetail };
})();
