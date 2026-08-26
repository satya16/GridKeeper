import { useState } from 'react'
import { Box, Button, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'

// Fallback UI for any backend that isn't boinc/fah -- i.e. a third-party
// grid_node.backends plugin (see node/grid_node/backends/base.py). Not as
// polished as BoincBlock/FahBlock (raw status JSON + a free-form action
// picker instead of purpose-built controls), but it makes a plugin usable
// from the dashboard immediately, with zero hub-side code for that
// specific backend. `actions` comes from the hub's BackendCapability
// registry (GET /api/backends, see hub/app/api/backends.py) -- reported by
// a node's own status frame, not guessed.
export function GenericBackendBlock({ nodeId, backendName, backendStatus, actions, canWrite, onChanged }) {
  const [action, setAction] = useState('')
  const [payloadText, setPayloadText] = useState('{}')
  const [running, setRunning] = useState(false)

  const handleRun = async () => {
    if (!action) return
    let payload
    try {
      payload = payloadText.trim() ? JSON.parse(payloadText) : {}
    } catch {
      notify.error('Payload must be valid JSON (or left empty for {}).')
      return
    }
    setRunning(true)
    try {
      const result = await api.issueCommand(nodeId, backendName, action, payload)
      if (result.status !== 'ok') {
        notify.warning(`Command finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      } else {
        notify.success(`${backendName}.${action} → ok`)
      }
      onChanged()
    } catch (err) {
      notify.error(`Command failed: ${err.message}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {backendName}
      </Typography>
      <pre
        style={{
          background: 'var(--gk-card-bg)',
          border: '1px solid var(--gk-border)',
          borderRadius: 6,
          padding: 8,
          fontSize: 12,
          maxHeight: 160,
          overflow: 'auto',
          marginTop: 4,
        }}
      >
        {JSON.stringify(backendStatus, null, 2)}
      </pre>
      {canWrite && actions && actions.length > 0 && (
        <Stack spacing={1} sx={{ width: '100%', mt: 0.5 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <TextField
              select
              size="small"
              label="Action"
              value={action}
              onChange={(e) => setAction(e.target.value)}
              sx={{ minWidth: 160 }}
            >
              {actions.map((a) => (
                <MenuItem key={a} value={a}>
                  {a}
                </MenuItem>
              ))}
            </TextField>
            <Button size="small" variant="contained" loading={running} disabled={running || !action} onClick={handleRun}>
              Run
            </Button>
          </Stack>
          <TextField
            size="small"
            multiline
            minRows={1}
            maxRows={3}
            value={payloadText}
            onChange={(e) => setPayloadText(e.target.value)}
            placeholder="{}"
          />
        </Stack>
      )}
    </Box>
  )
}
