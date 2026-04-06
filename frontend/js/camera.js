/**
 * VigIA Camera page - live stream + smart action panel
 */

const CameraPage = (() => {
  let ws = null;
  let currentCameraId = null;
  let reconnectTimer = null;
  let lastDetection = { faces: [], objects: [] };
  let expandedUnknown = null;
  // Presence log: deduplicates consecutive detections of the same person set
  let _lastLogKey = '';
  const _presenceLog = []; // [{names, ts, types}] max 8 entries
  // Generation counter — incremented on every loadCameras() call and on destroy().
  // A resolving call checks its own generation; if stale, it silently exits.
  let _loadGen = 0;

  // ── Render ────────────────────────────────────────────────────────────────

  function render() {
    document.getElementById('content').innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-3">
        <h4 class="mb-0 fw-bold"><i class="bi bi-camera-video me-2 text-primary"></i>Cámara en vivo</h4>
        <div class="d-flex gap-2 align-items-center">
          <select id="cameraSelect" class="form-select form-select-sm" style="width:auto">
            <option value="">Seleccionar cámara...</option>
          </select>
          <button class="btn btn-sm btn-outline-light" id="btnCapture" title="Capturar foto">
            <i class="bi bi-camera me-1"></i>Capturar
          </button>
        </div>
      </div>

      <div class="row g-3">
        <!-- ── Cámara ── -->
        <div class="col-12 col-lg-7">
          <div class="card bg-dark border-secondary h-100">
            <div class="card-body p-2">
              <div class="position-relative bg-black rounded" style="min-height:420px">
                <img id="cameraFeed" class="w-100 rounded d-none"
                     style="max-height:540px;object-fit:contain" crossorigin="anonymous" />
                <div id="cameraPlaceholder" class="d-flex align-items-center justify-content-center"
                     style="min-height:420px">
                  <div class="text-center text-muted">
                    <i class="bi bi-camera-video-off fs-1 d-block mb-2"></i>
                    Selecciona una cámara para iniciar
                  </div>
                </div>
                <!-- Status bar -->
                <div class="position-absolute bottom-0 start-0 end-0 px-3 py-1 d-flex justify-content-between align-items-center"
                     style="background:rgba(0,0,0,0.55);border-radius:0 0 8px 8px">
                  <span class="text-white small" id="camStatusLabel">—</span>
                  <span class="badge bg-success pulse-dot d-none" id="liveIndicator">EN VIVO</span>
                  <span class="text-white small" id="camTimestamp">—</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Panel de acción ── -->
        <div class="col-12 col-lg-5">
          <!-- Personas detectadas con acciones -->
          <div class="card bg-dark border-secondary mb-3">
            <div class="card-header border-secondary py-2 d-flex align-items-center justify-content-between">
              <span class="fw-semibold"><i class="bi bi-person-bounding-box me-2 text-warning"></i>Personas detectadas</span>
              <span class="badge bg-warning text-dark" id="faceCount">0</span>
            </div>
            <div id="actionPanel" class="p-2">
              <p class="text-muted small text-center py-3 mb-0">Sin personas en cámara</p>
            </div>
          </div>

          <!-- Objetos -->
          <div class="card bg-dark border-secondary mb-3">
            <div class="card-header border-secondary py-2">
              <i class="bi bi-boxes me-2 text-info"></i>
              <span class="fw-semibold">Objetos detectados</span>
              <span class="badge bg-info text-dark ms-2" id="objectCount">0</span>
            </div>
            <div class="card-body py-2 px-3" id="objectPanel">
              <p class="text-muted small text-center mb-0">Sin objetos</p>
            </div>
          </div>

          <!-- Presencia reciente -->
          <div class="card bg-dark border-secondary">
            <div class="card-header border-secondary py-2 d-flex align-items-center justify-content-between">
              <span class="fw-semibold small"><i class="bi bi-clock-history me-2 text-secondary"></i>Presencia reciente</span>
              <button class="btn btn-link btn-sm text-secondary p-0 lh-1" style="font-size:11px" onclick="CameraPage.clearPresenceLog()" title="Limpiar">
                <i class="bi bi-trash3"></i>
              </button>
            </div>
            <div id="presenceLog" class="px-2 py-1" style="min-height:48px"></div>
          </div>
        </div>
      </div>

      <!-- Modal: Registrar visitante desconocido -->
      <div class="modal fade" id="registerUnknownModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title"><i class="bi bi-person-plus me-2 text-warning"></i>Registrar Visitante</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div class="row mb-3">
                <div class="col-5 text-center">
                  <img id="unknownSnapshot" src="" class="img-thumbnail w-100" style="max-height:180px;object-fit:cover" />
                  <button class="btn btn-sm btn-outline-secondary mt-2 w-100" id="btnRetakeSnapshot">
                    <i class="bi bi-camera me-1"></i>Recapturar
                  </button>
                </div>
                <div class="col-7">
                  <div class="mb-2">
                    <label class="form-label form-label-sm">Nombre completo <span class="text-danger">*</span></label>
                    <input type="text" class="form-control form-control-sm" id="unNombre" placeholder="Nombre del visitante" />
                  </div>
                  <div class="mb-2">
                    <label class="form-label form-label-sm"><i class="bi bi-house-door me-1 text-warning"></i>Visita al apartamento <span class="text-danger">*</span></label>
                    <input type="text" class="form-control form-control-sm" id="unApartamento" placeholder="Ej: 514, 302-B..." />
                  </div>
                  <div class="mb-2">
                    <label class="form-label form-label-sm">Documento</label>
                    <input type="text" class="form-control form-control-sm" id="unDocumento" placeholder="CC / CE / PA" />
                  </div>
                  <div class="mb-2">
                    <label class="form-label form-label-sm">Teléfono</label>
                    <input type="tel" class="form-control form-control-sm" id="unTelefono" placeholder="+57 300..." />
                  </div>
                </div>
              </div>
              <div class="mb-2">
                <label class="form-label form-label-sm">Tipo de acceso</label>
                <div class="btn-group w-100" role="group">
                  <input type="radio" class="btn-check" name="unTipo" id="unEntrada" value="entrada" checked>
                  <label class="btn btn-outline-success btn-sm" for="unEntrada"><i class="bi bi-box-arrow-in-right me-1"></i>Entrada</label>
                  <input type="radio" class="btn-check" name="unTipo" id="unSalida" value="salida">
                  <label class="btn btn-outline-secondary btn-sm" for="unSalida"><i class="bi bi-box-arrow-right me-1"></i>Salida</label>
                </div>
              </div>
              <div id="unAlertArea"></div>
            </div>
            <div class="modal-footer border-secondary">
              <button class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-sm btn-outline-secondary" id="btnLogAnon">
                <i class="bi bi-incognito me-1"></i>Solo registrar anónimo
              </button>
              <button class="btn btn-sm btn-warning" id="btnSaveUnknown">
                <i class="bi bi-person-check me-1"></i>Guardar y registrar acceso
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Modal: Confirmar acceso (residente/visitante conocido) -->
      <div class="modal fade" id="confirmAccessModal" tabindex="-1">
        <div class="modal-dialog modal-sm">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary py-2">
              <h6 class="modal-title" id="confirmAccessTitle">Registrar Acceso</h6>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body py-3" id="confirmAccessBody"></div>
            <div class="modal-footer border-secondary py-2 justify-content-center gap-2">
              <button class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-success btn-sm" id="btnDoEntrada">
                <i class="bi bi-box-arrow-in-right me-1"></i>Aceptar Entrada
              </button>
              <button class="btn btn-outline-secondary btn-sm" id="btnDoSalida">
                <i class="bi bi-box-arrow-right me-1"></i>Registrar Salida
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    setupEventListeners();
    renderPresenceLog();

    // Instant startup: if a previous camera was active, start streaming NOW before
    // the API call returns. The select dropdown will be populated in the background.
    const savedId = parseInt(sessionStorage.getItem('vigia_camera_id'));
    if (savedId) startStream(savedId);

    loadCameras();

    // Reload stream when tab becomes visible again (fixes black screen after tab switch)
    document.addEventListener('visibilitychange', _onVisibilityChange);
  }

  function _onVisibilityChange() {
    if (document.visibilityState === 'visible' && currentCameraId) {
      reloadFeed(currentCameraId);
    }
  }

  // ── Camera loading ────────────────────────────────────────────────────────

  async function loadCameras() {
    const myGen = ++_loadGen;
    try {
      const cameras = await Api.getCameras();

      // Stale check: destroy() or a newer loadCameras() call was made while we awaited
      if (myGen !== _loadGen) return;

      const select = document.getElementById('cameraSelect');
      if (!select) return;

      const activeCams = cameras.filter(c => c.activo);
      activeCams.forEach(cam => {
        const opt = document.createElement('option');
        opt.value = cam.id;
        opt.textContent = `${cam.nombre} (${cam.tipo})`;
        select.appendChild(opt);
      });

      // Sync dropdown to whichever camera is already streaming (or pick preferred)
      const savedId = parseInt(sessionStorage.getItem('vigia_camera_id'));
      const preferred = activeCams.find(c => c.id === savedId) || activeCams[0];
      if (preferred) {
        select.value = preferred.id;
        // Only start stream if not already streaming this camera (instant-start may
        // have already done it above)
        if (currentCameraId !== preferred.id) startStream(preferred.id);
      }
    } catch (e) {
      if (myGen !== _loadGen) return; // stale — don't show error for cancelled call
      if (document.getElementById('cameraSelect')) {
        App.showToast('Error cargando cámaras: ' + e.message, 'danger');
      }
    }
  }

  let streamRetryTimer = null;

  function startStream(cameraId) {
    // Guard: already streaming this camera — avoid WebSocket reconnection storm
    if (currentCameraId === cameraId) return;
    currentCameraId = cameraId;
    sessionStorage.setItem('vigia_camera_id', cameraId);
    reloadFeed(cameraId);
    connectDetectionWs(cameraId);
  }

  // Helper: get a DOM element only while the camera page is still mounted
  function _el(id) { return currentCameraId !== null ? document.getElementById(id) : null; }

  function reloadFeed(cameraId) {
    clearTimeout(streamRetryTimer);
    const feed = document.getElementById('cameraFeed');
    if (!feed) return;

    // Cache-buster prevents browser from serving stale/broken stream
    feed.src = Api.getStreamUrl(cameraId) + '?t=' + Date.now();
    feed.classList.remove('d-none');
    document.getElementById('cameraPlaceholder')?.classList.add('d-none');
    document.getElementById('liveIndicator')?.classList.remove('d-none');
    const lbl = document.getElementById('camStatusLabel');
    if (lbl) lbl.textContent = `📹 Conectando...`;

    // Callbacks fire asynchronously — always guard against stale DOM
    feed.onload = () => {
      const l = _el('camStatusLabel');
      if (l) l.textContent = `📹 En vivo`;
    };

    feed.onerror = () => {
      const l = _el('camStatusLabel');
      const ind = _el('liveIndicator');
      if (l) l.textContent = `⚠ Error — reintentando...`;
      if (ind) ind.classList.add('d-none');
      streamRetryTimer = setTimeout(() => {
        if (currentCameraId === cameraId) reloadFeed(cameraId);
      }, 3000);
    };
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────

  function connectDetectionWs(cameraId) {
    if (ws) { ws.close(); ws = null; }
    clearTimeout(reconnectTimer);

    ws = new WebSocket(Api.getWsUrl(`/ws/camera/${cameraId}`));

    ws.onopen = () => {
      const l = _el('camStatusLabel'); if (l) l.textContent = `📹 Conectado`;
    };
    ws.onmessage = (e) => {
      if (e.data instanceof Blob) return;
      if (!currentCameraId) return; // page already unmounted
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'detection') handleDetection(data);
        if (data.type === 'error') { const l = _el('camStatusLabel'); if (l) l.textContent = `⚠ ${data.message}`; }
      } catch {}
    };
    ws.onclose = () => {
      const l = _el('camStatusLabel');
      const ind = _el('liveIndicator');
      if (l) l.textContent = '⚠ Reconectando...';
      if (ind) ind.classList.add('d-none');
      reconnectTimer = setTimeout(() => { if (currentCameraId) connectDetectionWs(currentCameraId); }, 4000);
    };
    ws.onerror = () => ws.close();
  }

  // ── Detection handling ────────────────────────────────────────────────────

  function handleDetection(data) {
    if (!currentCameraId) return; // page unmounted
    lastDetection = { faces: data.faces || [], objects: data.objects || [] };
    const ts = fmtTime(data.timestamp);
    const tsEl = document.getElementById('camTimestamp');
    const fcEl = document.getElementById('faceCount');
    if (tsEl) tsEl.textContent = ts;
    if (fcEl) fcEl.textContent = lastDetection.faces.length;
    renderActionPanel(lastDetection.faces, ts);
    renderObjectPanel(lastDetection.objects);
    appendToLog(lastDetection.faces, ts);
  }

  // ── Action Panel ──────────────────────────────────────────────────────────

  function renderActionPanel(faces, ts) {
    const panel = document.getElementById('actionPanel');
    if (faces.length === 0) {
      panel.innerHTML = '<p class="text-muted small text-center py-3 mb-0">Sin personas en cámara</p>';
      return;
    }

    panel.innerHTML = faces.map((f, idx) => {
      const confPct = Math.round((f.confianza || 0) * 100);

      if (f.type === 'resident') {
        return `
          <div class="border border-success rounded p-2 mb-2">
            <div class="d-flex align-items-center gap-2 mb-2">
              <div class="rounded-circle bg-success d-flex align-items-center justify-content-center" style="width:36px;height:36px;flex-shrink:0">
                <i class="bi bi-house-fill text-white small"></i>
              </div>
              <div class="flex-grow-1 overflow-hidden">
                <div class="fw-bold small text-truncate">${f.nombre}</div>
                <div class="text-muted" style="font-size:11px">Residente · ${confPct}% coincidencia</div>
              </div>
              <span class="badge bg-success">${confPct}%</span>
            </div>
            <button class="btn btn-success btn-sm w-100"
              onclick="CameraPage.openConfirmAccess('resident', ${f.id}, '${escHtml(f.nombre)}')">
              <i class="bi bi-person-check me-1"></i>Registrar Acceso
            </button>
          </div>`;
      }

      if (f.type === 'visitor') {
        return `
          <div class="border border-primary rounded p-2 mb-2">
            <div class="d-flex align-items-center gap-2 mb-2">
              <div class="rounded-circle bg-primary d-flex align-items-center justify-content-center" style="width:36px;height:36px;flex-shrink:0">
                <i class="bi bi-person-badge-fill text-white small"></i>
              </div>
              <div class="flex-grow-1 overflow-hidden">
                <div class="fw-bold small text-truncate">${f.nombre}</div>
                <div class="text-muted" style="font-size:11px">Visitante · ${confPct}% coincidencia</div>
              </div>
              <span class="badge bg-primary">${confPct}%</span>
            </div>
            <button class="btn btn-primary btn-sm w-100"
              onclick="CameraPage.openConfirmAccess('visitor', ${f.id}, '${escHtml(f.nombre)}')">
              <i class="bi bi-person-check me-1"></i>Registrar Acceso
            </button>
          </div>`;
      }

      // Unknown person
      return `
        <div class="border border-warning rounded p-2 mb-2">
          <div class="d-flex align-items-center gap-2 mb-2">
            <div class="rounded-circle bg-warning d-flex align-items-center justify-content-center" style="width:36px;height:36px;flex-shrink:0">
              <i class="bi bi-question-lg text-dark small"></i>
            </div>
            <div class="flex-grow-1">
              <div class="fw-bold small text-warning">Persona no identificada</div>
              <div class="text-muted" style="font-size:11px">Rostro detectado en cámara</div>
            </div>
          </div>
          <div class="d-flex gap-2">
            <button class="btn btn-warning btn-sm flex-fill text-dark"
              onclick="CameraPage.openRegisterUnknown(${idx})">
              <i class="bi bi-person-plus me-1"></i>Registrar visitante
            </button>
            <button class="btn btn-outline-secondary btn-sm"
              onclick="CameraPage.logAnonymous()"
              title="Registrar como acceso anónimo">
              <i class="bi bi-incognito"></i>
            </button>
          </div>
        </div>`;
    }).join('');
  }

  function renderObjectPanel(objects) {
    const panel = document.getElementById('objectPanel');
    document.getElementById('objectCount').textContent = objects.length;
    if (objects.length === 0) {
      panel.innerHTML = '<p class="text-muted small text-center mb-0">Sin objetos</p>';
      return;
    }
    const counts = {};
    objects.forEach(o => { counts[o.class] = (counts[o.class] || 0) + 1; });
    const icons = { person:'bi-person', car:'bi-car-front', motorcycle:'bi-bicycle',
                    truck:'bi-truck', backpack:'bi-backpack', handbag:'bi-bag', suitcase:'bi-briefcase' };
    panel.innerHTML = `<div class="d-flex flex-wrap gap-2">` +
      Object.entries(counts).map(([cls, cnt]) =>
        `<span class="badge bg-info text-dark"><i class="bi ${icons[cls]||'bi-box'} me-1"></i>${cls} ${cnt > 1 ? '×'+cnt : ''}</span>`
      ).join('') + `</div>`;
  }

  function appendToLog(faces, ts) {
    // Only record when the set of detected people changes (deduplicate spam)
    const key = faces.map(f => f.nombre + ':' + f.type).sort().join('|');
    if (!key || key === _lastLogKey) return;
    _lastLogKey = key;

    _presenceLog.unshift({ faces: faces.slice(), ts });
    if (_presenceLog.length > 8) _presenceLog.length = 8;
    renderPresenceLog();
  }

  function renderPresenceLog() {
    const el = document.getElementById('presenceLog');
    if (!el) return;
    if (_presenceLog.length === 0) {
      el.innerHTML = '<p class="text-muted" style="font-size:11px;padding:6px 0 4px">Sin detecciones recientes</p>';
      return;
    }
    el.innerHTML = _presenceLog.map((entry, i) => {
      const chips = entry.faces.map(f => {
        const cls = f.type === 'resident' ? 'bg-success' : f.type === 'visitor' ? 'bg-primary' : 'bg-warning text-dark';
        const icon = f.type === 'resident' ? 'bi-house-fill' : f.type === 'visitor' ? 'bi-person-badge-fill' : 'bi-question-lg';
        return `<span class="badge ${cls} d-inline-flex align-items-center gap-1"><i class="bi ${icon}" style="font-size:9px"></i>${escHtml(f.nombre)}</span>`;
      }).join(' ');
      const opacity = i === 0 ? '1' : (0.75 - i * 0.07).toFixed(2);
      return `
        <div class="d-flex align-items-center gap-2 py-1 border-bottom border-secondary border-opacity-25" style="opacity:${opacity}">
          <span class="text-muted flex-shrink-0" style="font-size:10px;min-width:70px">${entry.ts}</span>
          <div class="d-flex flex-wrap gap-1">${chips}</div>
        </div>`;
    }).join('');
  }

  function clearPresenceLog() {
    _presenceLog.length = 0;
    _lastLogKey = '';
    renderPresenceLog();
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  // Open confirm modal for known person — guard chooses entrada or salida
  function openConfirmAccess(personType, personId, nombre) {
    document.getElementById('confirmAccessTitle').textContent = nombre;
    document.getElementById('confirmAccessBody').innerHTML = `
      <div class="d-flex align-items-center gap-3">
        <div class="rounded-circle ${personType === 'resident' ? 'bg-success' : 'bg-primary'} d-flex align-items-center justify-content-center" style="width:48px;height:48px;flex-shrink:0">
          <i class="bi ${personType === 'resident' ? 'bi-house-fill' : 'bi-person-badge-fill'} text-white fs-5"></i>
        </div>
        <div>
          <div class="fw-bold">${nombre}</div>
          <div class="text-muted small">${personType === 'resident' ? 'Residente' : 'Visitante'}</div>
          <div class="text-muted small mt-1">¿Entrada o salida?</div>
        </div>
      </div>`;

    // Wire up buttons fresh (clone to remove old listeners)
    ['btnDoEntrada', 'btnDoSalida'].forEach(id => {
      const old = document.getElementById(id);
      const fresh = old.cloneNode(true);
      old.parentNode.replaceChild(fresh, old);
      const tipo = id === 'btnDoEntrada' ? 'entrada' : 'salida';
      fresh.addEventListener('click', () => doAccess(personType, personId, nombre, tipo));
    });

    new bootstrap.Modal(document.getElementById('confirmAccessModal')).show();
  }

  async function doAccess(personType, personId, nombre, tipo) {
    const btnE = document.getElementById('btnDoEntrada');
    const btnS = document.getElementById('btnDoSalida');
    btnE.disabled = true; btnS.disabled = true;
    try {
      const payload = { tipo };
      if (personType === 'visitor') payload.visitor_id = personId;
      else payload.resident_id = personId;
      await Api.createManualLog(payload);
      bootstrap.Modal.getInstance(document.getElementById('confirmAccessModal')).hide();
      const icon = tipo === 'entrada' ? '🟢' : '🔴';
      App.showToast(`${icon} ${tipo === 'entrada' ? 'Entrada' : 'Salida'} registrada: ${nombre}`, 'success');
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    } finally {
      btnE.disabled = false; btnS.disabled = false;
    }
  }

  // Open modal to register unknown person as visitor
  async function openRegisterUnknown(unknownIdx) {
    document.getElementById('unNombre').value = '';
    document.getElementById('unApartamento').value = '';
    document.getElementById('unDocumento').value = '';
    document.getElementById('unTelefono').value = '';
    document.getElementById('unAlertArea').innerHTML = '';
    document.getElementById('unknownSnapshot').src = '';

    // Capture snapshot from camera
    if (currentCameraId) {
      try {
        const snapshotUrl = `${API_BASE}/cameras/${currentCameraId}/snapshot?t=${Date.now()}`;
        const token = localStorage.getItem('vigia_token');
        const resp = await fetch(snapshotUrl, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
        if (resp.ok) {
          const blob = await resp.blob();
          document.getElementById('unknownSnapshot').src = URL.createObjectURL(blob);
        }
      } catch {}
    }

    const modal = new bootstrap.Modal(document.getElementById('registerUnknownModal'));
    modal.show();
  }

  // Log anonymous access (unknown, no registration)
  async function logAnonymous() {
    try {
      await Api.createManualLog({ tipo: 'entrada', notas: 'Persona no identificada - acceso anónimo' });
      App.showToast('Acceso anónimo registrado', 'warning');
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    }
  }

  // ── Capture button ────────────────────────────────────────────────────────

  async function captureSnapshot() {
    if (!currentCameraId) { App.showToast('Selecciona una cámara primero', 'warning'); return; }
    try {
      const token = localStorage.getItem('vigia_token');
      const resp = await fetch(`${API_BASE}/cameras/${currentCameraId}/snapshot`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (!resp.ok) throw new Error('Sin respuesta de la cámara');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vigia_captura_${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.jpg`;
      a.click();
      URL.revokeObjectURL(url);
      App.showToast('Foto capturada y descargada', 'success');
    } catch (e) {
      App.showToast('Error al capturar: ' + e.message, 'danger');
    }
  }

  // ── Event listeners ───────────────────────────────────────────────────────

  function setupEventListeners() {
    document.getElementById('cameraSelect').addEventListener('change', e => {
      const id = parseInt(e.target.value);
      if (!id) return;
      // Force-switch even if same ID (user explicitly picking = wants a reset)
      currentCameraId = null;
      startStream(id);
    });

    document.getElementById('btnCapture').addEventListener('click', captureSnapshot);

    // Retake snapshot in unknown modal
    document.getElementById('btnRetakeSnapshot').addEventListener('click', async () => {
      if (!currentCameraId) return;
      try {
        const token = localStorage.getItem('vigia_token');
        const resp = await fetch(`${API_BASE}/cameras/${currentCameraId}/snapshot?t=${Date.now()}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (resp.ok) {
          const blob = await resp.blob();
          document.getElementById('unknownSnapshot').src = URL.createObjectURL(blob);
        }
      } catch {}
    });

    // Save unknown visitor + log access
    document.getElementById('btnSaveUnknown').addEventListener('click', saveUnknownVisitor);

    // Log anonymous from modal
    document.getElementById('btnLogAnon').addEventListener('click', async () => {
      bootstrap.Modal.getInstance(document.getElementById('registerUnknownModal')).hide();
      await logAnonymous();
    });
  }

  async function saveUnknownVisitor() {
    const nombreEl = document.getElementById('unNombre');
    const alertEl  = document.getElementById('unAlertArea');
    const btn      = document.getElementById('btnSaveUnknown');
    if (!nombreEl || !btn) return; // page was unmounted

    const nombre = nombreEl.value.trim();
    if (!nombre) {
      alertEl.innerHTML = '<div class="alert alert-warning py-1 small">El nombre es requerido</div>';
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Guardando...';

    try {
      const tipo = document.querySelector('input[name="unTipo"]:checked')?.value || 'entrada';

      // 1. Create visitor
      const visitor = await Api.createVisitor({
        nombre,
        apartamento_destino: document.getElementById('unApartamento').value.trim() || null,
        documento: document.getElementById('unDocumento').value.trim() || null,
        telefono: document.getElementById('unTelefono').value.trim() || null,
      });

      // 2. Upload snapshot as face if available
      const snapSrc = document.getElementById('unknownSnapshot').src;
      if (snapSrc && snapSrc.startsWith('blob:')) {
        try {
          const snapResp = await fetch(snapSrc);
          const blob = await snapResp.blob();
          const fd = new FormData();
          fd.append('file', blob, 'snapshot.jpg');
          await Api.uploadVisitorFace(visitor.id, fd);
        } catch {}
      }

      // 3. Log access
      await Api.createManualLog({ tipo, visitor_id: visitor.id });

      const modal = document.getElementById('registerUnknownModal');
      if (modal) bootstrap.Modal.getInstance(modal)?.hide();
      App.showToast(`Visitante "${nombre}" registrado y acceso anotado`, 'success');
    } catch (e) {
      const alertEl = document.getElementById('unAlertArea');
      if (alertEl) alertEl.innerHTML = `<div class="alert alert-danger py-1 small">${e.message}</div>`;
    } finally {
      const btn = document.getElementById('btnSaveUnknown');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-person-check me-1"></i>Guardar y registrar acceso';
      }
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function escHtml(str) {
    return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;');
  }

  function destroy() {
    _loadGen++; // invalidates any in-flight loadCameras() call

    // Abort the MJPEG stream and clear callbacks BEFORE nulling currentCameraId,
    // so _el() guards still work if anything fires synchronously during cleanup
    const feed = document.getElementById('cameraFeed');
    if (feed) {
      feed.onload = null;
      feed.onerror = null;
      feed.src = ''; // stops the browser from downloading further MJPEG frames
    }

    if (ws) { ws.close(); ws = null; }
    clearTimeout(reconnectTimer);
    clearTimeout(streamRetryTimer);
    document.removeEventListener('visibilitychange', _onVisibilityChange);

    // Null AFTER clearing callbacks — _el() uses this as the "mounted" sentinel
    currentCameraId = null;
    _lastLogKey = '';
    _presenceLog.length = 0;
  }

  return { render, destroy, openConfirmAccess, openRegisterUnknown, logAnonymous, clearPresenceLog };
})();
