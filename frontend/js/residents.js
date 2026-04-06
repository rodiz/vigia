/**
 * VigIA Residents page
 */

const ResidentsPage = (() => {
  let currentPage = 1;
  const PAGE_SIZE = 20;
  let editingId = null;
  let uploadingFaceForId = null;
  let searchTerm = '';

  async function render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h4 class="mb-0 fw-bold"><i class="bi bi-people me-2 text-success"></i>Residentes</h4>
        <button class="btn btn-primary btn-sm" id="btnNewResident">
          <i class="bi bi-plus-lg me-1"></i>Nuevo residente
        </button>
      </div>

      <!-- Search + filter bar -->
      <div class="card bg-dark border-secondary mb-3">
        <div class="card-body py-2">
          <div class="row g-2 align-items-center">
            <div class="col-md-5">
              <div class="input-group input-group-sm">
                <span class="input-group-text bg-dark border-secondary"><i class="bi bi-search"></i></span>
                <input type="text" id="residentSearch" class="form-control bg-dark border-secondary text-white"
                       placeholder="Buscar por nombre o apartamento..." />
              </div>
            </div>
            <div class="col-md-3">
              <select id="residentFilter" class="form-select form-select-sm bg-dark border-secondary text-white">
                <option value="">Todos los estados</option>
                <option value="true">Activos</option>
                <option value="false">Inactivos</option>
              </select>
            </div>
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
                  <th>Foto</th><th>Nombre</th><th>Apartamento</th>
                  <th>Teléfono</th><th>Estado</th><th>Facial</th><th>Acciones</th>
                </tr>
              </thead>
              <tbody id="residentsBody">
                <tr><td colspan="7" class="text-center py-5">
                  <div class="spinner-border text-primary spinner-border-sm me-2"></div>Cargando...
                </td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="card-footer border-secondary d-flex justify-content-between align-items-center">
          <small class="text-muted" id="residentCount">—</small>
          <div class="btn-group btn-group-sm" id="residentPagination"></div>
        </div>
      </div>

      <!-- Add/Edit Modal -->
      <div class="modal fade" id="residentModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title" id="residentModalTitle">Nuevo Residente</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <form id="residentForm">
                <div class="row g-3">
                  <div class="col-8">
                    <label class="form-label">Nombre completo <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="rNombre" required />
                  </div>
                  <div class="col-4">
                    <label class="form-label">Apartamento <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="rApartamento" required placeholder="101A" />
                  </div>
                  <div class="col-6">
                    <label class="form-label">Teléfono</label>
                    <input type="tel" class="form-control" id="rTelefono" placeholder="+57 300..." />
                  </div>
                  <div class="col-6">
                    <label class="form-label">Email</label>
                    <input type="email" class="form-control" id="rEmail" />
                  </div>
                </div>
              </form>
            </div>
            <div class="modal-footer border-secondary">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-primary" id="btnSaveResident">
                <i class="bi bi-check-lg me-1"></i>Guardar
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Face enrollment modal -->
      <div class="modal fade" id="faceModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title"><i class="bi bi-person-bounding-box me-2"></i>Registrar Rostro</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <!-- Tabs -->
              <ul class="nav nav-tabs nav-tabs-dark mb-3" id="faceTabs">
                <li class="nav-item">
                  <button class="nav-link active" id="tabFile" data-tab="file">
                    <i class="bi bi-folder2-open me-1"></i>Subir archivo
                  </button>
                </li>
                <li class="nav-item">
                  <button class="nav-link" id="tabCamera" data-tab="camera">
                    <i class="bi bi-camera me-1"></i>Capturar de cámara
                  </button>
                </li>
              </ul>

              <!-- File tab -->
              <div id="faceTabFile">
                <div class="mb-3">
                  <input type="file" class="form-control" id="faceFileInput" accept="image/*" />
                  <div class="form-text">Foto clara de frente, buena iluminación.</div>
                </div>
              </div>

              <!-- Camera tab -->
              <div id="faceTabCamera" class="d-none">
                <div class="text-center mb-2">
                  <img id="faceCamPreview" src="" class="img-fluid rounded mb-2"
                       style="max-height:220px;width:100%;object-fit:cover;background:#111" />
                  <div class="d-flex gap-2 justify-content-center">
                    <button class="btn btn-sm btn-outline-primary" id="btnLoadCamStream">
                      <i class="bi bi-play me-1"></i>Ver cámara
                    </button>
                    <button class="btn btn-sm btn-warning" id="btnSnapFace">
                      <i class="bi bi-camera me-1"></i>Capturar foto
                    </button>
                  </div>
                </div>
              </div>

              <!-- Preview (shared) -->
              <div id="facePreviewWrap" class="text-center d-none mt-2">
                <img id="facePreviewImg" src="" alt="Preview" class="img-thumbnail mb-2" style="max-height:180px" />
                <div id="faceStatus" class="small text-success"><i class="bi bi-check-circle me-1"></i>Listo para registrar</div>
              </div>
              <div id="faceAlertArea"></div>
            </div>
            <div class="modal-footer border-secondary">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-success" id="btnUploadFace" disabled>
                <i class="bi bi-person-check me-1"></i>Registrar rostro
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    setupListeners();
    loadResidents();
  }

  async function loadResidents(page = 1) {
    currentPage = page;
    const search = document.getElementById('residentSearch')?.value || '';
    const filter = document.getElementById('residentFilter')?.value;
    const skip = (page - 1) * PAGE_SIZE;

    const params = { skip, limit: PAGE_SIZE };
    if (search) params.search = search;
    if (filter !== '') params.activo = filter;

    try {
      const residents = await Api.getResidents(params);
      renderTable(residents);
    } catch (e) {
      document.getElementById('residentsBody').innerHTML =
        `<tr><td colspan="7" class="text-center text-danger py-4">${e.message}</td></tr>`;
    }
  }

  function renderTable(residents) {
    const tbody = document.getElementById('residentsBody');
    document.getElementById('residentCount').textContent = `${residents.length} residente(s)`;

    if (residents.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center py-5 text-muted">Sin residentes encontrados</td></tr>';
      return;
    }

    tbody.innerHTML = residents.map(r => `
      <tr>
        <td>
          ${r.foto_path
            ? `<img src="/data/faces/${r.foto_path.split('/').pop()}" class="face-thumb" onerror="this.src=''" />`
            : `<div class="face-thumb d-flex align-items-center justify-content-center bg-secondary">
                 <i class="bi bi-person text-muted"></i>
               </div>`
          }
        </td>
        <td class="fw-semibold">${r.nombre}</td>
        <td><span class="badge bg-secondary">${r.apartamento}</span></td>
        <td class="text-muted small">${r.telefono || '—'}</td>
        <td>
          <span class="badge ${r.activo ? 'bg-success' : 'bg-danger'}">
            ${r.activo ? 'Activo' : 'Inactivo'}
          </span>
        </td>
        <td>
          ${r.foto_path
            ? '<span class="badge bg-success"><i class="bi bi-check-lg"></i> Registrado</span>'
            : '<span class="badge bg-secondary">Sin foto</span>'
          }
        </td>
        <td>
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-primary" onclick="ResidentsPage.openEdit(${r.id})" title="Editar">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-outline-success" onclick="ResidentsPage.openFace(${r.id})" title="Foto facial">
              <i class="bi bi-person-bounding-box"></i>
            </button>
            <button class="btn btn-outline-danger" onclick="ResidentsPage.confirmDelete(${r.id}, '${r.nombre}')" title="Desactivar">
              <i class="bi bi-person-x"></i>
            </button>
          </div>
        </td>
      </tr>
    `).join('');
  }

  function setupListeners() {
    document.getElementById('btnNewResident').addEventListener('click', () => {
      editingId = null;
      document.getElementById('residentModalTitle').textContent = 'Nuevo Residente';
      document.getElementById('residentForm').reset();
      new bootstrap.Modal(document.getElementById('residentModal')).show();
    });

    document.getElementById('btnSaveResident').addEventListener('click', saveResident);

    document.getElementById('residentSearch').addEventListener('input', debounce(() => loadResidents(), 400));
    document.getElementById('residentFilter').addEventListener('change', () => loadResidents());

    // Tab switching
    document.querySelectorAll('#faceTabs .nav-link').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#faceTabs .nav-link').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.getElementById('faceTabFile').classList.toggle('d-none', tab !== 'file');
        document.getElementById('faceTabCamera').classList.toggle('d-none', tab !== 'camera');
        document.getElementById('facePreviewWrap').classList.add('d-none');
        document.getElementById('btnUploadFace').disabled = true;
      });
    });

    // File input
    document.getElementById('faceFileInput').addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        document.getElementById('facePreviewImg').src = ev.target.result;
        document.getElementById('facePreviewWrap').classList.remove('d-none');
        document.getElementById('btnUploadFace').disabled = false;
      };
      reader.readAsDataURL(file);
    });

    // Load camera stream in camera tab
    document.getElementById('btnLoadCamStream').addEventListener('click', async () => {
      try {
        const cameras = await Api.getCameras();
        const first = cameras.find(c => c.activo);
        if (!first) { App.showToast('No hay cámaras activas', 'warning'); return; }
        const preview = document.getElementById('faceCamPreview');
        preview.src = Api.getStreamUrl(first.id) + '?t=' + Date.now();
        App.showToast('Stream iniciado - presiona Capturar para tomar la foto', 'info');
      } catch (e) {
        App.showToast('Error: ' + e.message, 'danger');
      }
    });

    // Capture snapshot from camera
    document.getElementById('btnSnapFace').addEventListener('click', async () => {
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
        document.getElementById('facePreviewImg').src = url;
        document.getElementById('facePreviewWrap').classList.remove('d-none');
        document.getElementById('btnUploadFace').disabled = false;
        // Store blob for upload
        document.getElementById('btnUploadFace').dataset.snapBlob = url;
        App.showToast('Foto capturada', 'success');
      } catch (e) {
        App.showToast('Error al capturar: ' + e.message, 'danger');
      }
    });

    document.getElementById('btnUploadFace').addEventListener('click', uploadFace);
  }

  async function saveResident() {
    const btn = document.getElementById('btnSaveResident');
    const data = {
      nombre: document.getElementById('rNombre').value.trim(),
      apartamento: document.getElementById('rApartamento').value.trim(),
      telefono: document.getElementById('rTelefono').value.trim() || null,
      email: document.getElementById('rEmail').value.trim() || null,
    };

    if (!data.nombre || !data.apartamento) {
      App.showToast('Nombre y apartamento son requeridos', 'warning');
      return;
    }

    btn.disabled = true;
    try {
      if (editingId) {
        await Api.updateResident(editingId, data);
        App.showToast('Residente actualizado', 'success');
      } else {
        await Api.createResident(data);
        App.showToast('Residente creado', 'success');
      }
      bootstrap.Modal.getInstance(document.getElementById('residentModal')).hide();
      loadResidents();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  async function openEdit(id) {
    editingId = id;
    try {
      const residents = await Api.getResidents({ limit: 200 });
      const r = residents.find(x => x.id === id);
      if (!r) return;

      document.getElementById('residentModalTitle').textContent = 'Editar Residente';
      document.getElementById('rNombre').value = r.nombre;
      document.getElementById('rApartamento').value = r.apartamento;
      document.getElementById('rTelefono').value = r.telefono || '';
      document.getElementById('rEmail').value = r.email || '';

      new bootstrap.Modal(document.getElementById('residentModal')).show();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    }
  }

  function openFace(residentId) {
    uploadingFaceForId = residentId;
    document.getElementById('faceFileInput').value = '';
    document.getElementById('facePreviewWrap').classList.add('d-none');
    const btn = document.getElementById('btnUploadFace');
    btn.disabled = true;
    btn.dataset.snapBlob = '';
    document.getElementById('faceAlertArea').innerHTML = '';
    // Reset to file tab
    document.querySelectorAll('#faceTabs .nav-link').forEach(b => b.classList.remove('active'));
    document.getElementById('tabFile').classList.add('active');
    document.getElementById('faceTabFile').classList.remove('d-none');
    document.getElementById('faceTabCamera').classList.add('d-none');
    document.getElementById('faceCamPreview').src = '';
    new bootstrap.Modal(document.getElementById('faceModal')).show();
  }

  async function uploadFace() {
    if (!uploadingFaceForId) return;

    const btn = document.getElementById('btnUploadFace');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Procesando...';
    document.getElementById('faceAlertArea').innerHTML = '';

    try {
      const fd = new FormData();
      const snapBlobUrl = btn.dataset.snapBlob;
      const fileInput = document.getElementById('faceFileInput');

      if (snapBlobUrl && snapBlobUrl.startsWith('blob:')) {
        // From camera capture
        const resp = await fetch(snapBlobUrl);
        const blob = await resp.blob();
        fd.append('file', blob, 'captura.jpg');
      } else if (fileInput.files[0]) {
        fd.append('file', fileInput.files[0]);
      } else {
        App.showToast('Selecciona o captura una foto primero', 'warning');
        return;
      }

      await Api.uploadResidentFace(uploadingFaceForId, fd);
      document.getElementById('faceAlertArea').innerHTML =
        '<div class="alert alert-success py-2"><i class="bi bi-check-circle me-2"></i>Rostro registrado correctamente</div>';
      App.showToast('Rostro facial registrado', 'success');
      btn.dataset.snapBlob = '';
      setTimeout(() => {
        bootstrap.Modal.getInstance(document.getElementById('faceModal')).hide();
        loadResidents();
      }, 1500);
    } catch (e) {
      document.getElementById('faceAlertArea').innerHTML =
        `<div class="alert alert-danger py-2"><i class="bi bi-exclamation-triangle me-2"></i>${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-person-check me-1"></i>Registrar rostro';
    }
  }

  async function confirmDelete(id, nombre) {
    if (!confirm(`¿Desactivar al residente "${nombre}"?`)) return;
    try {
      await Api.deleteResident(id);
      App.showToast('Residente desactivado', 'success');
      loadResidents();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    }
  }

  function debounce(fn, delay) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
  }

  return { render, openEdit, openFace, confirmDelete };
})();
