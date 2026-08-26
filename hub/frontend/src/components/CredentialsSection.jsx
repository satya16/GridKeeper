import { useState } from 'react'
import { Box, Button, Card, CardContent, CardHeader, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'
import { usePolling } from '../usePolling.js'

const CREDENTIALS_REFRESH_INTERVAL_MS = 10000

function summarizeBulkResults(results) {
  const applied = results.filter((r) => r.online).length
  const skipped = results.length - applied
  const failed = results.filter((r) => r.online && r.status !== 'ok').length
  let msg = `Applied to ${applied}/${results.length} machine(s)`
  if (skipped) msg += `, ${skipped} offline (skipped)`
  if (failed) msg += `, ${failed} failed`
  return msg
}

function CredentialRow({ credential, nodes, groups, perms, onChanged, onNodeChanged }) {
  const [target, setTarget] = useState('')
  const [applying, setApplying] = useState(false)

  const handleApply = async () => {
    if (!target) return
    setApplying(true)
    try {
      if (target === 'all') {
        notify.info(summarizeBulkResults(await api.applyCredentialToAll(credential.id)))
      } else if (target.startsWith('group:')) {
        const group = target.slice('group:'.length)
        notify.info(summarizeBulkResults(await api.applyCredentialToGroup(credential.id, group)))
      } else {
        const nodeId = target.slice('node:'.length)
        const result = await api.applyCredential(credential.id, nodeId)
        if (result.status !== 'ok') {
          notify.warning(`Apply finished with status "${result.status}": ${JSON.stringify(result.result)}`)
        } else {
          notify.success(`Applied '${credential.name}' to the selected machine.`)
        }
      }
      onChanged()
      onNodeChanged()
    } catch (err) {
      notify.error(`Apply failed: ${err.message}`)
    } finally {
      setApplying(false)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm(`Delete saved credential '${credential.name}'? This can't be undone.`)) return
    try {
      await api.deleteCredential(credential.id)
      onChanged()
    } catch (err) {
      notify.error(`Delete failed: ${err.message}`)
    }
  }

  const staticFieldsSummary = Object.entries(credential.static_fields || {})
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ')

  return (
    <div className="task-row">
      <span>
        <strong>{credential.name}</strong> — {credential.backend}
        {staticFieldsSummary ? ` (${staticFieldsSummary})` : ''}
        <span className="muted">
          {' — '}
          {credential.last_used_at ? `last applied ${new Date(credential.last_used_at).toLocaleString()}` : 'never applied'}
        </span>
      </span>
      <Stack direction="row" spacing={1} flexWrap="wrap">
        {perms.canApplyCredential && (
          <>
            <TextField select size="small" value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 200 }} displayEmpty>
              <MenuItem value="">
                <em>Apply to…</em>
              </MenuItem>
              {perms.canApplyCredentialToAll && <MenuItem value="all">All machines</MenuItem>}
              {perms.canApplyCredentialToGroup && groups.map((g) => <MenuItem key={g} value={`group:${g}`}>{g}</MenuItem>)}
              {nodes.map((n) => (
                <MenuItem key={n.id} value={`node:${n.id}`}>
                  {n.name}
                </MenuItem>
              ))}
            </TextField>
            <Button size="small" variant="contained" loading={applying} disabled={applying || !target} onClick={handleApply}>
              Apply
            </Button>
          </>
        )}
        {perms.canManageCredentials && (
          <Button size="small" variant="outlined" color="error" onClick={handleDelete}>
            Delete
          </Button>
        )}
      </Stack>
    </div>
  )
}

export function CredentialsSection({ nodes, groups, backends, perms, onNodeChanged }) {
  const { data: credentials, status, refresh } = usePolling(api.listCredentials, CREDENTIALS_REFRESH_INTERVAL_MS)
  const [name, setName] = useState('')
  const [backendName, setBackendName] = useState('')
  const [staticFieldValues, setStaticFieldValues] = useState({})
  const [secret, setSecret] = useState('')
  // Only backends that declared a CREDENTIAL_ACTION (see
  // node/grid_node/backends/base.py) support a saved credential -- e.g.
  // fah.py deliberately doesn't (its passkey isn't shaped like a reusable
  // project account key), same boundary this had before it was
  // generalized, now driven by the registry instead of hardcoded here.
  const credentialBackends = (backends || []).filter((b) => b.credential_action)
  const selectedBackend = credentialBackends.find((b) => b.name === backendName)
  const staticFieldNames = selectedBackend?.credential_action?.static_fields || []
  const secretFieldLabel = selectedBackend?.credential_action?.key_field || 'secret'

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim() || !backendName || !secret.trim()) return
    try {
      const staticFields = Object.fromEntries(staticFieldNames.map((f) => [f, (staticFieldValues[f] || '').trim()]))
      await api.createCredential(name.trim(), backendName, staticFields, secret.trim())
      notify.success(`Saved '${name.trim()}'.`)
      setName('')
      setBackendName('')
      setStaticFieldValues({})
      setSecret('')
      refresh()
    } catch (err) {
      notify.error(`Save failed: ${err.message}`)
    }
  }

  return (
    <Card>
      <CardHeader title="Saved credentials" action={<span className="muted">{status}</span>} />
      <CardContent sx={{ pt: 0 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Save a project credential once, then apply it to any machine below without pasting it into that machine's
          attach form each time.
        </Typography>

        {credentials && credentials.length ? (
          credentials.map((c) => (
            <CredentialRow
              key={c.id}
              credential={c}
              nodes={nodes}
              groups={groups}
              perms={perms}
              onChanged={refresh}
              onNodeChanged={onNodeChanged}
            />
          ))
        ) : (
          <p className="task-row muted">No saved credentials yet.</p>
        )}

        {perms.canManageCredentials && (
          <Box component="form" onSubmit={handleCreate} sx={{ mt: 1.5 }}>
            <Stack direction="row" spacing={1.5} flexWrap="wrap" alignItems="flex-start" useFlexGap>
              <TextField
                size="small"
                placeholder="Name (e.g. School WCG account)"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                sx={{ width: 220 }}
              />
              <TextField
                select
                size="small"
                label="Backend"
                required
                value={backendName}
                onChange={(e) => {
                  setBackendName(e.target.value)
                  setStaticFieldValues({})
                }}
                sx={{ width: 160 }}
                displayEmpty
              >
                <MenuItem value="">
                  <em>Backend</em>
                </MenuItem>
                {credentialBackends.map((b) => (
                  <MenuItem key={b.name} value={b.name}>
                    {b.label || b.name}
                  </MenuItem>
                ))}
              </TextField>
              {staticFieldNames.map((fieldName) => (
                <TextField
                  key={fieldName}
                  size="small"
                  placeholder={fieldName}
                  required
                  value={staticFieldValues[fieldName] || ''}
                  onChange={(e) => setStaticFieldValues((prev) => ({ ...prev, [fieldName]: e.target.value }))}
                  sx={{ width: 200 }}
                />
              ))}
              <TextField
                type="password"
                size="small"
                placeholder={secretFieldLabel}
                required
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                sx={{ width: 200 }}
              />
              <Button type="submit" variant="contained" disabled={!backendName}>
                Save
              </Button>
            </Stack>
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
