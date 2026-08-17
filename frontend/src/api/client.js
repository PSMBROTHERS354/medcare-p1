// VITE_API_BASE_URL should point at the backend root, e.g.:
//   http://localhost:8000            (development)
//   https://medcare-p1-api.onrender.com   (production, example)
// The '/api' path prefix is appended automatically below, so it's fine to
// set the env var with or without a trailing '/api' — both forms work.
const RAW_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TRIMMED = RAW_BASE.replace(/\/+$/, '');
const BASE_URL = TRIMMED.endsWith('/api') ? TRIMMED : `${TRIMMED}/api`;

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (e) { /* ignore */ }
    throw new Error(`${res.status}: ${JSON.stringify(detail)}`);
  }
  return res.json();
}

export const api = {
  health: () => request('/health'),
  skus: () => request('/skus'),
  dcs: () => request('/dcs'),
  scenarios: () => request('/scenarios'),
  forecast: (sku, dc) => request(`/forecast/${sku}/${dc}`),
  inventory: (sku, dc) => request(`/inventory/${sku}/${dc}`),
  recommendation: (sku, dc) => request(`/recommendation/${sku}/${dc}`),
  networkAlternatives: (sku, dc) => request(`/network/${sku}/${dc}`),
  networkMap: () => request('/network-map'),
  attentionQueue: (limit = 10) => request(`/attention-queue?limit=${limit}`),
  networkHealth: () => request('/network-health'),
  monitoringMetrics: () => request('/monitoring/metrics'),
  monitoringHistory: () => request('/monitoring/history'),
  whatIf: (payload) => request('/what-if', { method: 'POST', body: JSON.stringify(payload) }),
};
