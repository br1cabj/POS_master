const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

try {
  new URL(configuredBaseUrl, window.location.origin);
} catch {
  throw new Error('VITE_API_BASE_URL debe ser una URL válida o una ruta relativa.');
}

export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '');

export function getSessionToken() {
  return localStorage.getItem('cloudpos_web_session');
}

export async function apiRequest(path, { method = 'GET', body, authenticated = true } = {}) {
  const headers = { Accept: 'application/json' };
  const token = authenticated ? getSessionToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.detail || 'No se pudo completar la solicitud.');
  return payload;
}

export function fetchTable(table, options) {
  return apiRequest(`/data/${encodeURIComponent(table)}`, { method: 'POST', body: options });
}
