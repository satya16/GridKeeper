// Thin fetch wrapper -- same-origin REST calls to the FastAPI backend.
// Auth is a session cookie (see hub/app/auth.py for why this replaced
// HTTP Basic -- its native browser prompt turned out not to render at
// all in some real mobile browsers), sent automatically by the browser
// on every same-origin request once `/api/login` sets it -- nothing to
// do here beyond `credentials: "same-origin"`.
//
// `onUnauthorized`, set by App.jsx, fires whenever any call gets a 401 --
// not just the initial session check -- so a session that expires (or
// gets invalidated by a hub restart) mid-use kicks the UI back to the
// login screen instead of every poll silently failing forever.
let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 401) onUnauthorized()
    const err = new Error(body.detail || `${options.method || 'GET'} ${path} -> ${res.status}`)
    err.status = res.status
    err.body = body
    throw err
  }
  return body
}

export const api = {
  login: (username, password) => request('/api/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request('/api/logout', { method: 'POST' }),
  checkSession: () => request('/api/session'),
  getMe: () => request('/api/me'),
  changeOwnPassword: (currentPassword, newPassword) =>
    request('/api/me/password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  listUsers: () => request('/api/users'),
  createUser: (username, password, role, scope) =>
    request('/api/users', { method: 'POST', body: JSON.stringify({ username, password, role, scope }) }),
  updateUser: (userId, changes) =>
    request(`/api/users/${encodeURIComponent(userId)}`, { method: 'PUT', body: JSON.stringify(changes) }),
  deleteUser: (userId) => request(`/api/users/${encodeURIComponent(userId)}`, { method: 'DELETE' }),
  listAuditLog: () => request('/api/audit-log'),
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
