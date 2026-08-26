import { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'
import { usePolling } from '../usePolling.js'
import { SchedulePolicyForm } from './SchedulePolicyForm.jsx'

const DISCOVERY_REFRESH_INTERVAL_MS = 4000

function DiscoveryCard({ node, checked, onCheck, code, onCodeChange, onPaired }) {
  const address = node.addresses[0] || '?'
  const backends = node.backends.length ? ` — ${node.backends.join(', ')}` : ''

  const handlePair = async (e) => {
    e.preventDefault()
    try {
      const result = await api.pairDiscovered(node.discovery_id, code)
      notify.success(`Paired '${result.name}'.`)
      onPaired()
    } catch (err) {
      notify.error(`Pairing failed: ${err.message}`)
    }
  }

  return (
    <Card sx={{ width: 260 }}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', fontWeight: 600 }}>
          <Checkbox checked={checked} onChange={(e) => onCheck(e.target.checked)} size="small" sx={{ mr: 1, p: 0 }} />
          {node.hostname}
        </Box>
        <span className="muted">
          {address}:{node.port}
          {backends}
        </span>
        <Stack component="form" direction="row" spacing={0.75} onSubmit={handlePair}>
          <TextField
            size="small"
            placeholder="6-digit code"
            slotProps={{ htmlInput: { inputMode: 'numeric', maxLength: 6 } }}
            required
            value={code}
            onChange={(e) => onCodeChange(e.target.value)}
          />
          <Button type="submit" variant="outlined">
            Pair
          </Button>
        </Stack>
      </CardContent>
    </Card>
  )
}

// B1: pair several discovered-but-unpaired machines in one dashboard
// sitting. Each machine's code is still read off its own screen (that's
// the security model, see _docs/REQUIREMENTS.md section 6.5) -- this only
// collapses the dashboard side into one submit with a shared group/
// schedule instead of one open/fill/close cycle per machine.
function BulkPairBar({ selectedIds, codes, onCleared, onPaired }) {
  const [group, setGroup] = useState('')
  const [scheduling, setScheduling] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (schedule) => {
    setSubmitting(true)
    try {
      const pairs = selectedIds.map((id) => ({ discovery_id: id, code: codes[id] || '', name: '', group }))
      const results = await api.pairDiscoveredBatch(pairs, schedule)
      const ok = results.filter((r) => r.ok).length
      const failed = results.filter((r) => !r.ok)
      notify.info(
        `Paired ${ok}/${results.length} machine(s)` +
          (failed.length ? `. Failed: ${failed.map((r) => `${r.discovery_id} (${r.error})`).join('; ')}` : '')
      )
      onCleared()
      onPaired()
    } catch (err) {
      notify.error(`Bulk pairing failed: ${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card sx={{ mb: 1.5, bgcolor: 'var(--gk-card-bg)' }}>
      <CardContent>
        <Stack spacing={1.5} sx={{ width: '100%' }}>
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
            <Typography fontWeight={600}>{selectedIds.length} selected</Typography>
            <TextField
              size="small"
              placeholder="Group for all selected (optional)"
              sx={{ width: 220 }}
              value={group}
              onChange={(e) => setGroup(e.target.value)}
            />
            <label style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}>
              <Checkbox checked={scheduling} onChange={(e) => setScheduling(e.target.checked)} size="small" />
              Set a schedule for all selected
            </label>
          </Stack>
          {scheduling ? (
            <SchedulePolicyForm submitLabel={`Pair ${selectedIds.length} selected`} onSubmit={(policy) => handleSubmit(policy)} />
          ) : (
            <Button
              variant="contained"
              loading={submitting}
              disabled={submitting || !selectedIds.length}
              onClick={() => handleSubmit(null)}
              sx={{ alignSelf: 'flex-start' }}
            >
              Pair {selectedIds.length} selected
            </Button>
          )}
        </Stack>
      </CardContent>
    </Card>
  )
}

export function DiscoverySection({ onPaired }) {
  const { data, status, refresh } = usePolling(api.listDiscovered, DISCOVERY_REFRESH_INTERVAL_MS)
  const nodes = data || []
  const [banner, setBanner] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [codes, setCodes] = useState({})
  const [tokenSchedule, setTokenSchedule] = useState(null) // pending {label, group} awaiting a schedule submit, or null

  const handlePaired = () => {
    refresh()
    onPaired()
  }

  const toggleSelected = (discoveryId, checked) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(discoveryId)
      else next.delete(discoveryId)
      return next
    })
  }

  const setCode = (discoveryId, code) => setCodes((prev) => ({ ...prev, [discoveryId]: code }))

  const createToken = async (label, group, schedule) => {
    try {
      const created = await api.createPairingToken(label, group, schedule)
      setBanner({ token: created.token, label, group })
    } catch (err) {
      window.alert(`Failed to create pairing token: ${err.message}`)
    }
  }

  const handleNewToken = async () => {
    const label = window.prompt('Label for this machine (optional):', '') || ''
    const group = window.prompt('Group for this machine (e.g. "Lab 1"; optional):', '') || ''
    if (window.confirm('Set a default schedule for machines paired with this token? (Cancel = no restrictions)')) {
      setTokenSchedule({ label, group })
    } else {
      await createToken(label, group, null)
    }
  }

  return (
    <Card>
      <CardHeader title="Discovered on your network" action={<span className="muted">{status}</span>} />
      <CardContent sx={{ pt: 0 }}>
        <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 1.5 }}>
          <Button variant="contained" onClick={handleNewToken}>
            New pairing token
          </Button>
        </Stack>

        {tokenSchedule && (
          <Card sx={{ mb: 1.5 }}>
            <CardHeader title="Default schedule for this token's machines" />
            <CardContent sx={{ pt: 0 }}>
              <SchedulePolicyForm
                submitLabel="Create token"
                onSubmit={async (policy) => {
                  await createToken(tokenSchedule.label, tokenSchedule.group, policy)
                  setTokenSchedule(null)
                }}
              />
            </CardContent>
          </Card>
        )}

        {banner && (
          <Alert severity="info" onClose={() => setBanner(null)} sx={{ mb: 1.5 }}>
            Pairing token (use once, on the new machine){banner.group ? ` — group "${banner.group}"` : ''}: <code>{banner.token}</code>
            <br />
            Run: <code>grid-node enroll --hub &lt;hub-url&gt; --token {banner.token} --name "{banner.label || 'my-machine'}"</code>
          </Alert>
        )}

        {selected.size > 0 && (
          <BulkPairBar
            selectedIds={[...selected]}
            codes={codes}
            onCleared={() => setSelected(new Set())}
            onPaired={handlePaired}
          />
        )}

        {nodes.length ? (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mt: -0.5, mb: 1 }}>
              Onboarding a whole lab? Check several machines below, enter each one's code, then pair them all at once.
            </Typography>
            <Stack direction="row" spacing={2} flexWrap="wrap" alignItems="flex-start">
              {nodes.map((w) => (
                <DiscoveryCard
                  key={w.discovery_id}
                  node={w}
                  checked={selected.has(w.discovery_id)}
                  onCheck={(checked) => toggleSelected(w.discovery_id, checked)}
                  code={codes[w.discovery_id] || ''}
                  onCodeChange={(code) => setCode(w.discovery_id, code)}
                  onPaired={handlePaired}
                />
              ))}
            </Stack>
          </>
        ) : (
          <p className="muted">No unpaired machines seen on the network right now.</p>
        )}
      </CardContent>
    </Card>
  )
}
