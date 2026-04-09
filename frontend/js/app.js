/**
 * VigIA SPA router and main app controller
 */

const App = (() => {
  let currentPage = null;
  let eventsWs = null;
  let clockInterval = null;

  // ── Auth ──────────────────────────────────────────────────────────────────

  function isAuthenticated() {
    return !!localStorage.getItem('vigia_token');
  }

  function showLogin() {
    document.getElementById('appShell').classList.add('d-none');
    document.getElementById('loginOverlay').classList.remove('d-none');
  }

  function showApp() {
    document.getElementById('loginOverlay').classList.add('d-none');
    document.getElementById('appShell').classList.remove('d-none');
    const user = JSON.parse(localStorage.getItem('vigia_user') || '{}');
    document.getElementById('navbarUsername').textContent = user.username || 'admin';
    startClock();
    connectEventsWs();
  }

  async function login(username, password) {
    const data = await Api.login(username, password);
    localStorage.setItem('vigia_token', data.access_token);
    localStorage.setItem('vigia_user', JSON.stringify({ username: data.username, role: data.role }));
    showApp();
    navigate('dashboard');
  }

  function logout() {
    if (currentPage === 'camera') CameraPage.destroy();
    localStorage.removeItem('vigia_token');
    localStorage.removeItem('vigia_user');
    stopClock();
    disconnectEventsWs();
    showLogin();
  }

  // ── Clock ─────────────────────────────────────────────────────────────────

  function startClock() {
    const el = document.getElementById('navbarClock');
    if (!el) return;
    function tick() {
      el.textContent = new Date().toLocaleString('es-CO', {
        timeZone: getTimezone(),
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        day: '2-digit', month: 'short'
      });
    }
    tick();
    clockInterval = setInterval(tick, 1000);
  }

  function stopClock() {
    if (clockInterval) clearInterval(clockInterval);
  }

  // ── Events WebSocket ──────────────────────────────────────────────────────

  function connectEventsWs() {
    if (!localStorage.getItem('vigia_token')) return;

    try {
      eventsWs = new WebSocket(Api.getWsUrl('/ws/events'));

      eventsWs.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'access_log') {
            appendLiveEvent(data);
          }
        } catch {}
      };

      eventsWs.onclose = () => {
        setTimeout(() => {
          if (isAuthenticated()) connectEventsWs();
        }, 5000);
      };

      eventsWs.onerror = () => eventsWs.close();
    } catch (e) {
      console.warn('Events WS error:', e);
    }
  }

  function disconnectEventsWs() {
    if (eventsWs) { eventsWs.close(); eventsWs = null; }
  }

  function appendLiveEvent(event) {
    const container = document.getElementById('liveEventsBody');
    if (!container) return;

    // Remove "no events" placeholder if present
    const empty = container.querySelector('td[colspan]');
    if (empty) empty.closest('tr').remove();

    const typeIcon = event.person_type === 'resident' ? '🏠' :
                     event.person_type === 'visitor'  ? '👤' : '❓';
    const ts = fmtTime(event.timestamp);
    const tipo = event.tipo || 'entrada';
    const badgeClass = tipo === 'entrada' ? 'bg-success' : 'bg-secondary';
    const tipoLabel = tipo === 'entrada' ? 'Entrada' : 'Salida';

    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="text-muted small">${ts}</td>
      <td class="fw-semibold">${typeIcon} ${event.person_name}</td>
      <td><span class="badge ${badgeClass}">${tipoLabel}</span></td>
      <td class="text-muted small">${(event.objects || []).join(', ') || '—'}</td>
    `;
    row.style.animation = 'fadeIn 0.3s ease';
    container.prepend(row);

    while (container.children.length > 20) container.removeChild(container.lastChild);

    const toastIcon = tipo === 'entrada' ? '🟢' : '🔴';
    showToast(`${toastIcon} ${tipoLabel}: ${event.person_name}`, tipo === 'entrada' ? 'success' : 'secondary');
  }

  // ── Router ────────────────────────────────────────────────────────────────

  const pages = {
    dashboard: renderDashboard,
    camera:    () => CameraPage.render(),
    residents: () => ResidentsPage.render(),
    visitors:  () => VisitorsPage.render(),
    events:    () => EventsPage.render(),
    settings:  () => SettingsPage.render(),
  };

  async function navigate(page) {
    if (!page || !pages[page]) page = 'dashboard';

    // Cleanup previous page
    if (currentPage === 'camera') CameraPage.destroy();

    currentPage = page;

    // Update sidebar active state
    document.querySelectorAll('.sidebar-link').forEach(link => {
      link.classList.toggle('active', link.dataset.page === page);
    });

    // Update URL hash
    window.location.hash = page;

    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="text-center py-5">
        <div class="spinner-border text-primary" role="status"></div>
      </div>`;

    try {
      await pages[page]();
    } catch (err) {
      content.innerHTML = `
        <div class="alert alert-danger">
          <i class="bi bi-exclamation-triangle me-2"></i>
          Error cargando página: ${err.message}
        </div>`;
    }
  }

  // ── Dashboard ─────────────────────────────────────────────────────────────

  async function renderDashboard() {
    const content = document.getElementById('content');
    content.innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h4 class="mb-0 fw-bold"><i class="bi bi-speedometer2 me-2 text-primary"></i>Dashboard</h4>
        <span class="d-flex align-items-center gap-2"><span class="pulse-dot"></span><small class="text-muted">En vivo</small></span>
      </div>

      <!-- Stats cards -->
      <div class="row g-3 mb-4" id="statsRow">
        ${[
          { id:'stat-entradas', label:'Entradas Hoy', icon:'bi-box-arrow-in-right', color:'success' },
          { id:'stat-salidas',  label:'Salidas Hoy',  icon:'bi-box-arrow-right',    color:'secondary' },
          { id:'stat-visitantes', label:'Visitantes del Mes', icon:'bi-person-badge', color:'info' },
          { id:'stat-alertas', label:'Desconocidos Hoy', icon:'bi-exclamation-triangle', color:'warning' },
        ].map(s => `
          <div class="col-6 col-md-3">
            <div class="stat-card h-100">
              <div class="d-flex align-items-center gap-3">
                <div class="stat-icon bg-${s.color} bg-opacity-15">
                  <i class="bi ${s.icon} text-${s.color}"></i>
                </div>
                <div>
                  <div class="fs-2 fw-bold" id="${s.id}">—</div>
                  <div class="text-muted small">${s.label}</div>
                </div>
              </div>
            </div>
          </div>
        `).join('')}
      </div>

      <div class="row g-3">
        <!-- Live events feed -->
        <div class="col-12 col-lg-7">
          <div class="card bg-dark border-secondary h-100">
            <div class="card-header border-secondary d-flex justify-content-between align-items-center">
              <span class="fw-semibold"><i class="bi bi-activity me-2 text-success"></i>Eventos recientes</span>
              <button class="btn btn-sm btn-outline-secondary" onclick="App.navigate('events')">Ver todos</button>
            </div>
            <div class="card-body p-0">
              <div class="table-responsive live-events-container">
                <table class="table table-dark table-sm table-hover mb-0">
                  <thead class="sticky-top bg-dark">
                    <tr>
                      <th>Hora</th><th>Persona</th><th>Tipo</th><th>Objetos</th>
                    </tr>
                  </thead>
                  <tbody id="liveEventsBody">
                    <tr><td colspan="4" class="text-center text-muted py-4">Sin eventos recientes</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <!-- Mini camera preview -->
        <div class="col-12 col-lg-5">
          <div class="card bg-dark border-secondary h-100">
            <div class="card-header border-secondary d-flex justify-content-between align-items-center">
              <span class="fw-semibold"><i class="bi bi-camera-video me-2 text-primary"></i>Cámara principal</span>
              <button class="btn btn-sm btn-outline-primary" onclick="App.navigate('camera')">
                <i class="bi bi-fullscreen me-1"></i>Ampliar
              </button>
            </div>
            <div class="card-body p-2">
              <div id="dashCameraWrap" class="bg-black rounded" style="min-height:200px">
                <p class="text-muted text-center pt-5 small" id="dashCamMsg">Cargando cámara...</p>
                <img id="dashCameraImg" class="w-100 rounded d-none" style="max-height:260px;object-fit:contain" />
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Load stats
    try {
      const stats = await Api.getStats();
      document.getElementById('stat-entradas').textContent = stats.entradas_hoy;
      document.getElementById('stat-salidas').textContent = stats.salidas_hoy;
      document.getElementById('stat-visitantes').textContent = stats.visitantes_mes;
      document.getElementById('stat-alertas').textContent = stats.alertas_hoy;
    } catch (e) {
      console.warn('Stats load error:', e);
    }

    // Load recent events
    try {
      const logs = await Api.getEvents({ limit: 15 });
      const tbody = document.getElementById('liveEventsBody');
      if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Sin eventos recientes</td></tr>';
      } else {
        tbody.innerHTML = logs.map(log => {
          const nombre = log.visitor?.nombre || log.resident?.nombre || 'Desconocido';
          const icon = log.resident_id ? '🏠' : log.visitor_id ? '👤' : '❓';
          const ts = fmtTime(log.timestamp);
          const badge = log.tipo === 'entrada' ? 'bg-success' : 'bg-secondary';
          return `
            <tr>
              <td class="text-muted small">${ts}</td>
              <td>${icon} ${nombre}</td>
              <td><span class="badge ${badge}">${log.tipo}</span></td>
              <td class="text-muted small">${log.objetos_detectados ? JSON.parse(log.objetos_detectados).join(', ') : '—'}</td>
            </tr>
          `;
        }).join('');
      }
    } catch (e) {
      console.warn('Events load error:', e);
    }

    // Mini camera
    try {
      const cameras = await Api.getCameras();
      const activeCam = cameras.find(c => c.activo);
      if (activeCam) {
        document.getElementById('dashCamMsg').classList.add('d-none');
        const img = document.getElementById('dashCameraImg');
        img.classList.remove('d-none');
        img.src = Api.getStreamUrl(activeCam.id);
        img.onerror = () => {
          img.classList.add('d-none');
          document.getElementById('dashCamMsg').textContent = 'Cámara no disponible';
          document.getElementById('dashCamMsg').classList.remove('d-none');
        };
      } else {
        document.getElementById('dashCamMsg').textContent = 'Sin cámaras configuradas';
      }
    } catch (e) {
      document.getElementById('dashCamMsg').textContent = 'Error cargando cámara';
    }
  }

  // ── Toast helper ──────────────────────────────────────────────────────────

  function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const id = `toast_${Date.now()}`;
    const iconMap = { info: 'bi-info-circle', success: 'bi-check-circle', danger: 'bi-exclamation-triangle', warning: 'bi-exclamation' };
    const colorMap = { info: 'text-info', success: 'text-success', danger: 'text-danger', warning: 'text-warning' };

    const toastEl = document.createElement('div');
    toastEl.id = id;
    toastEl.className = 'toast align-items-center border-0 bg-dark';
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="bi ${iconMap[type] || 'bi-info-circle'} ${colorMap[type] || ''}"></i>
          <span>${message}</span>
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    `;
    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  function init() {
    // Login form
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = document.getElementById('loginUsername').value;
      const password = document.getElementById('loginPassword').value;
      const errorEl = document.getElementById('loginError');
      const btn = e.target.querySelector('button[type=submit]');

      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Ingresando...';
      errorEl.classList.add('d-none');

      try {
        await login(username, password);
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove('d-none');
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-box-arrow-in-right me-2"></i>Ingresar';
      }
    });

    // Logout
    document.getElementById('logoutBtn').addEventListener('click', (e) => {
      e.preventDefault();
      logout();
    });

    // Sidebar links
    document.querySelectorAll('.sidebar-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.dataset.page;
        navigate(page);

        // Close mobile sidebar
        const sidebar = document.getElementById('sidebar');
        sidebar.classList.remove('show');
      });
    });

    // Mobile sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('show');
      });
    }

    // Check auth and route
    if (isAuthenticated()) {
      showApp();
      const hash = window.location.hash.replace('#', '') || 'dashboard';
      navigate(hash);
    } else {
      showLogin();
    }

    // Hash change
    window.addEventListener('hashchange', () => {
      if (!isAuthenticated()) return;
      const page = window.location.hash.replace('#', '') || 'dashboard';
      navigate(page);
    });
  }

  function restartClock() {
    stopClock();
    startClock();
  }

  return { init, navigate, showLogin, showApp, showToast, isAuthenticated, restartClock };
})();

// Bootstrap
document.addEventListener('DOMContentLoaded', App.init);
