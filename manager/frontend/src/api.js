// Thin fetch wrapper -- same-origin REST calls to the FastAPI backend.
// Auth is HTTP Basic, handled entirely by the browser (it challenges once
// on page load and then attaches credentials to every same-origin request
// automatically) -- nothing to do here beyond `credentials: "same-origin"`.

async function request(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(body.detail || `${options.method || 'GET'} ${path} -> ${res.status}`)
    err.status = res.status
    err.body = body
    throw err
  }
  return body
}

export const api = {
  listWorkers: () => request('/api/workers'),
  listGroups: () => request('/api/groups'),
  setWorkerGroup: (workerId, group) =>
    request(`/api/workers/${encodeURIComponent(workerId)}/group`, { method: 'PUT', body: JSON.stringify({ group }) }),
  issueCommand: (workerId, backend, action, payload = {}) =>
    request(`/api/workers/${encodeURIComponent(workerId)}/commands`, {
      method: 'POST',
      body: JSON.stringify({ backend, action, payload }),
    }),
  setWorkerSchedule: (workerId, policy) =>
    request(`/api/workers/${encodeURIComponent(workerId)}/schedule`, { method: 'PUT', body: JSON.stringify(policy) }),
  applySchedule: (group, policy) =>
    request(group ? `/api/schedule/apply-group/${encodeURIComponent(group)}` : '/api/schedule/apply-all', {
      method: 'POST',
      body: JSON.stringify(policy),
    }),
  listDiscovered: () => request('/api/discovery'),
  pairDiscovered: (discoveryId, code) =>
    request(`/api/discovery/${encodeURIComponent(discoveryId)}/pair`, {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  createPairingToken: (label, group) =>
    request('/api/pairing-tokens', { method: 'POST', body: JSON.stringify({ label, group }) }),
  getMetrics: () => request('/api/metrics'),
  listCredentials: () => request('/api/credentials'),
  createCredential: (name, projectUrl, accountKey) =>
    request('/api/credentials', {
      method: 'POST',
      body: JSON.stringify({ name, project_url: projectUrl, account_key: accountKey }),
    }),
  deleteCredential: (credentialId) =>
    request(`/api/credentials/${encodeURIComponent(credentialId)}`, { method: 'DELETE' }),
  applyCredential: (credentialId, workerId) =>
    request(`/api/credentials/${encodeURIComponent(credentialId)}/apply`, {
      method: 'POST',
      body: JSON.stringify({ worker_id: workerId }),
    }),
  applyCredentialToGroup: (credentialId, group) =>
    request(`/api/credentials/${encodeURIComponent(credentialId)}/apply-group/${encodeURIComponent(group)}`, {
      method: 'POST',
    }),
  applyCredentialToAll: (credentialId) =>
    request(`/api/credentials/${encodeURIComponent(credentialId)}/apply-all`, { method: 'POST' }),
}
