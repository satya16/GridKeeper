import { useState } from 'react'
import { Button, Card, CardContent, CardHeader, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'

// B2: the group-scoped counterpart to FleetScheduleSection -- "suspend all
// of Lab 1" without opening each node card. Same effectiveGroup pattern:
// a group_manager (no "All machines" option) falls back to their own
// first group rather than a value they can't actually submit.
export function GroupActionsSection({ groups, backends, canIssueToAll, onIssued }) {
  const [group, setGroup] = useState('')
  const [backendName, setBackendName] = useState('')
  const [action, setAction] = useState('')
  const [payloadText, setPayloadText] = useState('{}')
  const [running, setRunning] = useState(false)

  const effectiveGroup = group || (!canIssueToAll && groups.length ? groups[0] : '')
  const backend = backends.find((b) => b.name === backendName)

  const handleRun = async () => {
    if (!backendName || !action) return
    let payload
    try {
      payload = payloadText.trim() ? JSON.parse(payloadText) : {}
    } catch {
      notify.error('Payload must be valid JSON (or left empty for {}).')
      return
    }
    setRunning(true)
    try {
      const results = effectiveGroup
        ? await api.issueCommandToGroup(effectiveGroup, backendName, action, payload)
        : await api.issueCommandToAll(backendName, action, payload)
      const ok = results.filter((r) => r.status === 'ok').length
      const skipped = results.filter((r) => r.status === 'skipped').length
      notify.info(`${backendName}.${action}: ok on ${ok}/${results.length} machine(s)${skipped ? `, ${skipped} offline (skipped)` : ''}`)
      onIssued()
    } catch (err) {
      notify.error(`Command failed: ${err.message}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <Card sx={{ mt: 2 }}>
      <CardHeader title="Group actions" />
      <CardContent sx={{ pt: 0 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Run one command against every machine in a group (or the whole fleet) at once -- offline machines are skipped,
          not failed.
        </Typography>
        <Stack spacing={1.5} sx={{ width: '100%' }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Typography variant="body2">Target</Typography>
            <TextField select size="small" value={effectiveGroup} onChange={(e) => setGroup(e.target.value)} sx={{ minWidth: 180 }}>
              {canIssueToAll && <MenuItem value="">All machines</MenuItem>}
              {groups.map((g) => (
                <MenuItem key={g} value={g}>
                  {g}
                </MenuItem>
              ))}
            </TextField>
            <Typography variant="body2">Backend</Typography>
            <TextField
              select
              size="small"
              value={backendName}
              onChange={(e) => {
                setBackendName(e.target.value)
                setAction('')
              }}
              sx={{ minWidth: 160 }}
            >
              {backends.map((b) => (
                <MenuItem key={b.name} value={b.name}>
                  {b.label || b.name}
                </MenuItem>
              ))}
            </TextField>
            <Typography variant="body2">Action</Typography>
            <TextField
              select
              size="small"
              value={action}
              onChange={(e) => setAction(e.target.value)}
              disabled={!backend}
              sx={{ minWidth: 160 }}
            >
              {(backend?.actions || []).map((a) => (
                <MenuItem key={a} value={a}>
                  {a}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <TextField
            size="small"
            multiline
            minRows={1}
            maxRows={3}
            value={payloadText}
            onChange={(e) => setPayloadText(e.target.value)}
            placeholder="{}"
            sx={{ maxWidth: 400 }}
          />
          <Button variant="contained" loading={running} disabled={running || !backendName || !action} onClick={handleRun} sx={{ alignSelf: 'flex-start' }}>
            {effectiveGroup ? `Run on "${effectiveGroup}"` : 'Run on all machines'}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  )
}
