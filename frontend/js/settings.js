/**
 * VigIA Settings page
 */

const SettingsPage = (() => {

  async function render() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="d-flex align-items-center mb-4">
        <h4 class="mb-0 fw-bold"><i class="bi bi-gear me-2 text-secondary"></i>Configuración</h4>
      </div>

      <div class="row g-4">
        <!-- Telegram section -->
        <div class="col-12 col-lg-6">
          <div class="card bg-dark border-secondary h-100">
            <div class="card-header border-secondary">
              <i class="bi bi-telegram me-2 text-info"></i>
              <span class="fw-semibold">Notificaciones Telegram</span>
            </div>
            <div class="card-body">
              <div class="mb-3">
                <label class="form-label">Bot Token</label>
                <input type="text" class="form-control" id="cfgTelegramToken"
                       placeholder="123456789:AABBcc..." autocomplete="off" />
                <div class="form-text">Obtén el token con @BotFather en Telegram</div>
              </div>
              <div class="mb-3">
                <label class="form-label">Chat ID</label>
                <input type="text" class="form-control" id="cfgTelegramChat"
                       placeholder="-100123456789" autocomplete="off" />
                <div class="form-text">ID del grupo o canal que recibirá las alertas</div>
              </div>
              <div id="telegramTestResult" class="mb-3"></div>
              <div class="d-flex gap-2">
                <button class="btn btn-info btn-sm" id="btnTestTelegram">
                  <i class="bi bi-send me-1"></i>Probar conexión
                </button>
                <button class="btn btn-primary btn-sm" id="btnSaveTelegram">
                  <i class="bi bi-save me-1"></i>Guardar
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Recognition section -->
        <div class="col-12 col-lg-6">
          <div class="card bg-dark border-secondary h-100">
            <div class="card-header border-secondary">
              <i class="bi bi-person-bounding-box me-2 text-warning"></i>
              <span class="fw-semibold">Reconocimiento Facial</span>
            </div>
            <div class="card-body">
              <div class="mb-4">
                <label class="form-label">
                  Umbral de confianza:
                  <strong class="text-warning ms-1" id="confThresholdVal">60%</strong>
                </label>
                <input type="range" class="form-range" id="cfgConfThreshold"
                       min="0.3" max="0.95" step="0.05" value="0.6" />
                <div class="d-flex justify-content-between text-muted small mt-1">
                  <span>30% (permisivo)</span><span>95% (estricto)</span>
                </div>
              </div>

              <div class="mb-3">
                <label class="form-label">Notificar cuando se detecta:</label>
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" id="notifyVisitor" checked />
                  <label class="form-check-label">Visitante conocido</label>
                </div>
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" id="notifyUnknown" checked />
                  <label class="form-check-label">Persona desconocida</label>
                </div>
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" id="notifyResident" />
                  <label class="form-check-label">Residente (entrada)</label>
                </div>
              </div>

              <button class="btn btn-primary btn-sm" id="btnSaveRecognition">
                <i class="bi bi-save me-1"></i>Guardar configuración
              </button>
            </div>
          </div>
        </div>

        <!-- Cameras section -->
        <div class="col-12">
          <div class="card bg-dark border-secondary">
            <div class="card-header border-secondary d-flex justify-content-between align-items-center">
              <div>
                <i class="bi bi-camera-video me-2 text-primary"></i>
                <span class="fw-semibold">Cámaras</span>
              </div>
              <button class="btn btn-sm btn-primary" id="btnAddCamera">
                <i class="bi bi-plus-lg me-1"></i>Agregar cámara
              </button>
            </div>
            <div class="card-body p-0">
              <div id="camerasList">
                <div class="text-center py-4">
                  <div class="spinner-border spinner-border-sm text-primary"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Timezone section -->
        <div class="col-12 col-lg-6">
          <div class="card bg-dark border-secondary">
            <div class="card-header border-secondary">
              <i class="bi bi-clock-history me-2 text-info"></i>
              <span class="fw-semibold">Región y Hora</span>
            </div>
            <div class="card-body">
              <div class="mb-3">
                <label class="form-label">Zona horaria</label>
                <select class="form-select" id="cfgTimezone">
                  <optgroup label="América">
                    <option value="America/Bogota">América/Bogotá (UTC-5)</option>
                    <option value="America/Lima">América/Lima (UTC-5)</option>
                    <option value="America/Guayaquil">América/Guayaquil (UTC-5)</option>
                    <option value="America/Caracas">América/Caracas (UTC-4)</option>
                    <option value="America/Santiago">América/Santiago (UTC-3/-4)</option>
                    <option value="America/Argentina/Buenos_Aires">América/Buenos Aires (UTC-3)</option>
                    <option value="America/Sao_Paulo">América/São Paulo (UTC-3)</option>
                    <option value="America/Mexico_City">América/Ciudad de México (UTC-6)</option>
                    <option value="America/New_York">América/Nueva York (UTC-5/-4)</option>
                  </optgroup>
                  <optgroup label="Europa">
                    <option value="Europe/Madrid">Europa/Madrid (UTC+1/+2)</option>
                    <option value="Europe/London">Europa/Londres (UTC+0/+1)</option>
                  </optgroup>
                  <optgroup label="UTC">
                    <option value="UTC">UTC (UTC+0)</option>
                  </optgroup>
                </select>
                <div class="form-text">Afecta la hora mostrada en toda la aplicación</div>
              </div>
              <div class="mb-3 p-2 rounded bg-black border border-secondary">
                <small class="text-muted">Hora actual en la zona seleccionada:</small>
                <div class="fw-bold text-info mt-1" id="tzPreview">—</div>
              </div>
              <button class="btn btn-primary btn-sm" id="btnSaveTimezone">
                <i class="bi bi-save me-1"></i>Guardar zona horaria
              </button>
            </div>
          </div>
        </div>

        <!-- System / Password section -->
        <div class="col-12 col-lg-6">
          <div class="card bg-dark border-secondary">
            <div class="card-header border-secondary">
              <i class="bi bi-shield-lock me-2 text-danger"></i>
              <span class="fw-semibold">Seguridad del Sistema</span>
            </div>
            <div class="card-body">
              <h6 class="text-muted mb-3">Cambiar contraseña de administrador</h6>
              <div class="mb-3">
                <label class="form-label">Contraseña actual</label>
                <input type="password" class="form-control" id="pwCurrent" autocomplete="current-password" />
              </div>
              <div class="mb-3">
                <label class="form-label">Nueva contraseña</label>
                <input type="password" class="form-control" id="pwNew" autocomplete="new-password" />
              </div>
              <div class="mb-3">
                <label class="form-label">Confirmar contraseña</label>
                <input type="password" class="form-control" id="pwConfirm" autocomplete="new-password" />
              </div>
              <div id="pwAlertArea"></div>
              <button class="btn btn-danger btn-sm" id="btnChangePassword">
                <i class="bi bi-key me-1"></i>Cambiar contraseña
              </button>
            </div>
          </div>
        </div>

        <!-- System Info -->
        <div class="col-12 col-lg-6">
          <div class="card bg-dark border-secondary">
            <div class="card-header border-secondary">
              <i class="bi bi-info-circle me-2 text-secondary"></i>
              <span class="fw-semibold">Información del Sistema</span>
            </div>
            <div class="card-body">
              <table class="table table-dark table-sm mb-0">
                <tbody>
                  <tr><td class="text-muted">Aplicación</td><td>VigIA v1.0.0</td></tr>
                  <tr><td class="text-muted">Backend</td><td>FastAPI + SQLite</td></tr>
                  <tr><td class="text-muted">Facial</td><td>face_recognition (dlib)</td></tr>
                  <tr><td class="text-muted">Detección</td><td>YOLOv8n (ultralytics)</td></tr>
                  <tr><td class="text-muted">Zona horaria</td><td>America/Bogota</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- Camera modal -->
      <div class="modal fade" id="cameraModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary">
              <h5 class="modal-title" id="cameraModalTitle">Agregar Cámara</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <form id="cameraForm">
                <div class="mb-3">
                  <label class="form-label">Nombre <span class="text-danger">*</span></label>
                  <input type="text" class="form-control" id="camNombre" required placeholder="Entrada principal" />
                </div>
                <div class="mb-3">
                  <label class="form-label">URL / Índice <span class="text-danger">*</span></label>
                  <input type="text" class="form-control" id="camUrl" required
                         placeholder="rtsp://usuario:pass@192.168.1.10:554/stream  ó  0" />
                  <div class="form-text">Usa <code>0</code>, <code>1</code>... para webcam local, o URL RTSP completa</div>
                </div>
                <div class="mb-3">
                  <label class="form-label">Tipo</label>
                  <select class="form-select" id="camTipo">
                    <option value="entrada">Entrada</option>
                    <option value="salida">Salida</option>
                    <option value="interior">Interior</option>
                  </select>
                </div>
                <div class="form-check mb-3">
                  <input class="form-check-input" type="checkbox" id="camActivo" checked />
                  <label class="form-check-label">Cámara activa</label>
                </div>
              </form>
            </div>
            <div class="modal-footer border-secondary">
              <button class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
              <button class="btn btn-primary" id="btnSaveCamera">
                <i class="bi bi-check-lg me-1"></i>Guardar
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    setupListeners();
    loadSettings();
    loadCameras();
  }

  let editingCameraId = null;

  async function loadSettings() {
    try {
      const settings = await Api.getSettings();

      if (settings.telegram_bot_token)
        document.getElementById('cfgTelegramToken').value = settings.telegram_bot_token;
      if (settings.telegram_chat_id)
        document.getElementById('cfgTelegramChat').value = settings.telegram_chat_id;

      const threshold = parseFloat(settings.face_confidence_threshold || '0.6');
      document.getElementById('cfgConfThreshold').value = threshold;
      document.getElementById('confThresholdVal').textContent = Math.round(threshold * 100) + '%';

      if (settings.notify_visitor !== undefined)
        document.getElementById('notifyVisitor').checked = settings.notify_visitor === 'true';
      if (settings.notify_unknown !== undefined)
        document.getElementById('notifyUnknown').checked = settings.notify_unknown === 'true';
      if (settings.notify_resident !== undefined)
        document.getElementById('notifyResident').checked = settings.notify_resident === 'true';
    } catch (e) {
      console.warn('Error loading settings:', e);
    }
  }

  async function loadCameras() {
    try {
      const cameras = await Api.getCameras();
      renderCameraList(cameras);
    } catch (e) {
      document.getElementById('camerasList').innerHTML =
        `<div class="alert alert-danger m-3">${e.message}</div>`;
    }
  }

  function renderCameraList(cameras) {
    const el = document.getElementById('camerasList');
    if (cameras.length === 0) {
      el.innerHTML = '<p class="text-muted text-center py-4">Sin cámaras configuradas</p>';
      return;
    }

    el.innerHTML = `
      <table class="table table-dark table-sm table-hover mb-0">
        <thead>
          <tr><th>Estado</th><th>Nombre</th><th>URL</th><th>Tipo</th><th>Acciones</th></tr>
        </thead>
        <tbody>
          ${cameras.map(cam => `
            <tr>
              <td>
                <span class="cam-status ${cam.activo ? 'online' : 'offline'}"></span>
                <small class="ms-1 text-muted">${cam.activo ? 'Activa' : 'Inactiva'}</small>
              </td>
              <td class="fw-semibold">${cam.nombre}</td>
              <td class="text-muted small text-truncate" style="max-width:200px">${cam.url}</td>
              <td><span class="badge bg-secondary">${cam.tipo}</span></td>
              <td>
                <div class="btn-group btn-group-sm">
                  <button class="btn btn-outline-secondary" onclick="SettingsPage.testCameraStream(${cam.id})" title="Ver stream">
                    <i class="bi bi-play-circle"></i>
                  </button>
                  <button class="btn btn-outline-primary" onclick="SettingsPage.openEditCamera(${cam.id})" title="Editar">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-outline-danger" onclick="SettingsPage.deleteCamera(${cam.id},'${cam.nombre}')" title="Eliminar">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  function setupListeners() {
    // Confidence threshold slider
    document.getElementById('cfgConfThreshold').addEventListener('input', (e) => {
      document.getElementById('confThresholdVal').textContent =
        Math.round(parseFloat(e.target.value) * 100) + '%';
    });

    // Telegram
    document.getElementById('btnTestTelegram').addEventListener('click', testTelegram);
    document.getElementById('btnSaveTelegram').addEventListener('click', saveTelegramSettings);

    // Recognition
    document.getElementById('btnSaveRecognition').addEventListener('click', saveRecognitionSettings);

    // Timezone
    const tzSelect = document.getElementById('cfgTimezone');
    tzSelect.value = getTimezone();
    updateTzPreview();
    tzSelect.addEventListener('change', updateTzPreview);
    document.getElementById('btnSaveTimezone').addEventListener('click', () => {
      const tz = tzSelect.value;
      localStorage.setItem('vigia_timezone', tz);
      updateTzPreview();
      App.showToast(`Zona horaria guardada: ${tz}`, 'success');
      // Restart clock with new timezone
      App.restartClock();
    });

    // Camera
    document.getElementById('btnAddCamera').addEventListener('click', () => {
      editingCameraId = null;
      document.getElementById('cameraModalTitle').textContent = 'Agregar Cámara';
      document.getElementById('cameraForm').reset();
      document.getElementById('camActivo').checked = true;
      new bootstrap.Modal(document.getElementById('cameraModal')).show();
    });

    document.getElementById('btnSaveCamera').addEventListener('click', saveCamera);

    // Password
    document.getElementById('btnChangePassword').addEventListener('click', changePassword);
  }

  async function testTelegram() {
    const btn = document.getElementById('btnTestTelegram');
    const resultEl = document.getElementById('telegramTestResult');

    // Save first
    await saveTelegramSettings(true);

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Probando...';
    resultEl.innerHTML = '';

    try {
      const result = await Api.testTelegram();
      resultEl.innerHTML = `
        <div class="alert alert-${result.success ? 'success' : 'danger'} py-2">
          <i class="bi ${result.success ? 'bi-check-circle' : 'bi-exclamation-triangle'} me-2"></i>
          ${result.message}
        </div>`;
    } catch (e) {
      resultEl.innerHTML = `<div class="alert alert-danger py-2">${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-send me-1"></i>Probar conexión';
    }
  }

  async function saveTelegramSettings(silent = false) {
    const token = document.getElementById('cfgTelegramToken').value.trim();
    const chat  = document.getElementById('cfgTelegramChat').value.trim();

    try {
      await Api.updateSettings({
        telegram_bot_token: token,
        telegram_chat_id: chat,
      });
      if (!silent) App.showToast('Configuración Telegram guardada', 'success');
    } catch (e) {
      if (!silent) App.showToast('Error: ' + e.message, 'danger');
    }
  }

  async function saveRecognitionSettings() {
    const threshold = document.getElementById('cfgConfThreshold').value;
    const notifyVisitor  = document.getElementById('notifyVisitor').checked;
    const notifyUnknown  = document.getElementById('notifyUnknown').checked;
    const notifyResident = document.getElementById('notifyResident').checked;

    try {
      await Api.updateSettings({
        face_confidence_threshold: threshold,
        notify_visitor: String(notifyVisitor),
        notify_unknown: String(notifyUnknown),
        notify_resident: String(notifyResident),
      });
      App.showToast('Configuración de reconocimiento guardada', 'success');
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    }
  }

  async function saveCamera() {
    const nombre = document.getElementById('camNombre').value.trim();
    const url    = document.getElementById('camUrl').value.trim();
    const tipo   = document.getElementById('camTipo').value;
    const activo = document.getElementById('camActivo').checked;

    if (!nombre || !url) {
      App.showToast('Nombre y URL son requeridos', 'warning');
      return;
    }

    const btn = document.getElementById('btnSaveCamera');
    btn.disabled = true;

    try {
      if (editingCameraId) {
        await Api.updateCamera(editingCameraId, { nombre, url, tipo, activo });
        App.showToast('Cámara actualizada', 'success');
      } else {
        await Api.createCamera({ nombre, url, tipo });
        App.showToast('Cámara agregada', 'success');
      }
      bootstrap.Modal.getInstance(document.getElementById('cameraModal')).hide();
      loadCameras();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    } finally {
      btn.disabled = false;
    }
  }

  async function openEditCamera(id) {
    editingCameraId = id;
    try {
      const cameras = await Api.getCameras();
      const cam = cameras.find(c => c.id === id);
      if (!cam) return;

      document.getElementById('cameraModalTitle').textContent = 'Editar Cámara';
      document.getElementById('camNombre').value = cam.nombre;
      document.getElementById('camUrl').value = cam.url;
      document.getElementById('camTipo').value = cam.tipo;
      document.getElementById('camActivo').checked = cam.activo;

      new bootstrap.Modal(document.getElementById('cameraModal')).show();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    }
  }

  async function deleteCamera(id, nombre) {
    if (!confirm(`¿Eliminar la cámara "${nombre}"?`)) return;
    try {
      await Api.deleteCamera(id);
      App.showToast('Cámara eliminada', 'success');
      loadCameras();
    } catch (e) {
      App.showToast('Error: ' + e.message, 'danger');
    }
  }

  function testCameraStream(id) {
    window.open(Api.getStreamUrl(id), '_blank');
  }

  async function changePassword() {
    const current = document.getElementById('pwCurrent').value;
    const newPw   = document.getElementById('pwNew').value;
    const confirm = document.getElementById('pwConfirm').value;
    const alertEl = document.getElementById('pwAlertArea');

    alertEl.innerHTML = '';

    if (!current || !newPw) {
      alertEl.innerHTML = '<div class="alert alert-warning py-2">Completa todos los campos</div>';
      return;
    }
    if (newPw !== confirm) {
      alertEl.innerHTML = '<div class="alert alert-danger py-2">Las contraseñas no coinciden</div>';
      return;
    }
    if (newPw.length < 6) {
      alertEl.innerHTML = '<div class="alert alert-warning py-2">La contraseña debe tener al menos 6 caracteres</div>';
      return;
    }

    const btn = document.getElementById('btnChangePassword');
    btn.disabled = true;

    try {
      await Api.post('/auth/change-password', {
        current_password: current,
        new_password: newPw
      });
      alertEl.innerHTML = '<div class="alert alert-success py-2"><i class="bi bi-check-circle me-2"></i>Contraseña actualizada</div>';
      document.getElementById('pwCurrent').value = '';
      document.getElementById('pwNew').value = '';
      document.getElementById('pwConfirm').value = '';
    } catch (e) {
      alertEl.innerHTML = `<div class="alert alert-danger py-2">${e.message}</div>`;
    } finally {
      btn.disabled = false;
    }
  }

  function updateTzPreview() {
    const tz = document.getElementById('cfgTimezone').value;
    document.getElementById('tzPreview').textContent =
      new Date().toLocaleString('es-CO', {
        timeZone: tz,
        weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
  }

  return { render, openEditCamera, deleteCamera, testCameraStream };
})();
