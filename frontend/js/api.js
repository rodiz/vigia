/**
 * VigIA API client
 * Auto-attaches JWT, handles 401 redirect
 */

// Dynamic base URLs — work on localhost AND via ngrok/any proxy
const _host    = window.location.hostname;
const _port    = window.location.port ? `:${window.location.port}` : '';
const _isHttps = window.location.protocol === 'https:';
const API_BASE = `${window.location.protocol}//${_host}${_port}/api`;
const WS_BASE  = `${_isHttps ? 'wss' : 'ws'}://${_host}${_port}`;

// ── Timezone helpers ──────────────────────────────────────────────────────────
function getTimezone() {
  return localStorage.getItem('vigia_timezone') || 'America/Bogota';
}

// Backend returns timestamps without timezone ("2026-04-06 20:56:30" — stored as UTC).
// Append 'Z' so JavaScript parses them as UTC before converting to the configured zone.
function _toUTC(ts) {
  if (!ts) return new Date();
  if (ts instanceof Date) return ts;
  const s = String(ts);
  // Already has timezone info (ISO with Z or +offset) — leave as-is
  if (s.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
  // SQLite format "YYYY-MM-DD HH:MM:SS" → force UTC
  return new Date(s.replace(' ', 'T') + 'Z');
}

function fmtDateTime(ts) {
  return _toUTC(ts).toLocaleString('es-CO', {
    timeZone: getTimezone(),
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function fmtTime(ts) {
  return _toUTC(ts).toLocaleTimeString('es-CO', {
    timeZone: getTimezone(),
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function fmtDate(ts) {
  return _toUTC(ts).toLocaleDateString('es-CO', {
    timeZone: getTimezone(),
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
}

const Api = (() => {
  function getToken() {
    return localStorage.getItem('vigia_token');
  }

  function getHeaders(extra = {}) {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json', ...extra };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
  }

  async function request(method, path, body = null, options = {}) {
    const url = `${API_BASE}${path}`;
    const config = {
      method,
      headers: getHeaders(options.headers || {}),
    };

    if (body !== null && !(body instanceof FormData)) {
      config.body = JSON.stringify(body);
    } else if (body instanceof FormData) {
      // Remove Content-Type so browser sets multipart boundary
      const token = getToken();
      config.headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      config.body = body;
    }

    let resp;
    try {
      resp = await fetch(url, config);
    } catch (err) {
      throw new Error('No se puede conectar al servidor. Verifique que el backend esté corriendo.');
    }

    if (resp.status === 401) {
      localStorage.removeItem('vigia_token');
      localStorage.removeItem('vigia_user');
      if (window.App) App.showLogin();
      throw new Error('Sesión expirada. Por favor inicie sesión nuevamente.');
    }

    if (resp.status === 204) return null;

    const data = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      const msg = data.detail || `Error ${resp.status}`;
      throw new Error(Array.isArray(msg) ? msg.map(e => e.msg).join(', ') : msg);
    }

    return data;
  }

  return {
    get:    (path, opts)        => request('GET',    path, null, opts),
    post:   (path, body, opts)  => request('POST',   path, body, opts),
    put:    (path, body, opts)  => request('PUT',    path, body, opts),
    delete: (path, opts)        => request('DELETE', path, null, opts),
    patch:  (path, body, opts)  => request('PATCH',  path, body, opts),

    // Auth
    login: (username, password) =>
      request('POST', '/auth/login', { username, password }),

    // Residents
    getResidents: (params = {}) =>
      request('GET', `/residents?${new URLSearchParams(params)}`),
    createResident: (data) => request('POST', '/residents', data),
    updateResident: (id, data) => request('PUT', `/residents/${id}`, data),
    deleteResident: (id) => request('DELETE', `/residents/${id}`),
    uploadResidentFace: (id, formData) => request('POST', `/residents/${id}/face`, formData),

    // Visitors
    getVisitors: (params = {}) =>
      request('GET', `/visitors?${new URLSearchParams(params)}`),
    createVisitor: (data) => request('POST', '/visitors', data),
    updateVisitor: (id, data) => request('PUT', `/visitors/${id}`, data),
    uploadVisitorFace: (id, formData) => request('POST', `/visitors/${id}/face`, formData),

    // Events
    getEvents: (params = {}) =>
      request('GET', `/events?${new URLSearchParams(params)}`),
    getStats: () => request('GET', '/events/stats'),
    createManualLog: (data) => request('POST', '/events/manual', data),
    exportCsv: (params = {}) => {
      const token = getToken();
      const qs = new URLSearchParams(params);
      window.open(`${API_BASE}/events/export/csv?${qs}`, '_blank');
    },

    // Settings
    getSettings: () => request('GET', '/settings'),
    updateSettings: (settings) => request('PUT', '/settings', { settings }),
    testTelegram: () => request('POST', '/settings/test-telegram'),
    getCameras: () => request('GET', '/settings/cameras'),
    createCamera: (data) => request('POST', '/settings/cameras', data),
    updateCamera: (id, data) => request('PUT', `/settings/cameras/${id}`, data),
    deleteCamera: (id) => request('DELETE', `/settings/cameras/${id}`),
    getCameraStatus: (id) => request('GET', `/settings/cameras/${id}/status`),
    testCameraUrl: (url) => request('POST', '/settings/cameras/test-url', { url }),

    // Camera
    startCamera: (id) => request('POST', `/cameras/${id}/start`),
    stopCamera:  (id) => request('POST', `/cameras/${id}/stop`),
    getStreamUrl: (id) => `${API_BASE}/cameras/${id}/stream`,
    getWsUrl: (path) => `${WS_BASE}${path}`,
  };
})();
