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
  listNodes: () => request('/api/nodes'),
  listGroups: () => request('/api/groups'),
  setNodeGroup: (nodeId, group) =>
    request(`/api/nodes/${encodeURIComponent(nodeId)}/group`, { method: 'PUT', body: JSON.stringify({ group }) }),
  issueCommand: (nodeId, backend, action, payload = {}) =>
    request(`/api/nodes/${encodeURIComponent(nodeId)}/commands`, {
      method: 'POST',
      body: JSON.stringify({ backend, action, payload }),
    }),
  setNodeSchedule: (nodeId, policy) =>
    request(`/api/nodes/${encodeURIComponent(nodeId)}/schedule`, { method: 'PUT', body: JSON.stringify(policy) }),
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
  applyCredential: (credentialId, nodeId) =>
    request(`/api/credentials/${encodeURIComponent(credentialId)}/apply`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId }),
    }),
  applyCredentialToGroup: (credentialId, group) =>
    request(`/api/credentials/${encodeURIComponent(credentialId)}/apply-group/${encodeURIComponent(group)}`, {
      method: 'POST',
    }),
  applyCredentialToAll: (credentialId) =>
    request(`/api/credentials/${encodeURIComponent(credentialId)}/apply-all`, { method: 'POST' }),
}
