import { useState } from 'react'
import { Alert, Button, Card, Checkbox, Input, Space, Typography, message } from 'antd'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'

const DISCOVERY_REFRESH_INTERVAL_MS = 4000

function DiscoveryCard({ node, checked, onCheck, code, onCodeChange, onPaired }) {
  const address = node.addresses[0] || '?'
  const backends = node.backends.length ? ` — ${node.backends.join(', ')}` : ''

  const handlePair = async (e) => {
    e.preventDefault()
    try {
      const result = await api.pairDiscovered(node.discovery_id, code)
      message.success(`Paired '${result.name}'.`)
      onPaired()
    } catch (err) {
      message.error(`Pairing failed: ${err.message}`)
    }
  }

  return (
    <Card size="small" styles={{ body: { display: 'flex', flexDirection: 'column', gap: 6 } }}>
      <span style={{ fontWeight: 600 }}>
        <Checkbox checked={checked} onChange={(e) => onCheck(e.target.checked)} style={{ marginRight: 8 }} />
        {node.hostname}
      </span>
      <span className="muted">
        {address}:{node.port}
        {backends}
      </span>
      <form onSubmit={handlePair} style={{ display: 'flex', gap: 6 }}>
        <Input
          placeholder="6-digit code"
          inputMode="numeric"
          maxLength={6}
          required
          value={code}
          onChange={(e) => onCodeChange(e.target.value)}
        />
        <Button htmlType="submit">Pair</Button>
      </form>
    </Card>
  )
}

// B1: pair several discovered-but-unpaired machines in one dashboard
// sitting. Each machine's code is still read off its own screen (that's
// the security model, see _docs/REQUIREMENTS.md section 6.5) -- this only
// collapses the dashboard side into one submit with a shared group
// instead of one open/fill/close cycle per machine.
function BulkPairBar({ selectedIds, codes, onCleared, onPaired }) {
  const [group, setGroup] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const pairs = selectedIds.map((id) => ({ discovery_id: id, code: codes[id] || '', name: '', group }))
      const results = await api.pairDiscoveredBatch(pairs)
      const ok = results.filter((r) => r.ok).length
      const failed = results.filter((r) => !r.ok)
      message.info(
        `Paired ${ok}/${results.length} machine(s)` +
          (failed.length ? `. Failed: ${failed.map((r) => `${r.discovery_id} (${r.error})`).join('; ')}` : '')
      )
      onCleared()
      onPaired()
    } catch (err) {
      message.error(`Bulk pairing failed: ${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card size="small" style={{ marginBottom: 12, background: 'var(--gk-card)' }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space wrap>
          <strong>{selectedIds.length} selected</strong>
          <Input placeholder="Group for all selected (optional)" style={{ width: 220 }} value={group} onChange={(e) => setGroup(e.target.value)} />
        </Space>
        <Button type="primary" loading={submitting} disabled={submitting || !selectedIds.length} onClick={handleSubmit}>
          Pair {selectedIds.length} selected
        </Button>
      </Space>
    </Card>
  )
}

export function DiscoverySection({ onPaired }) {
  const { data, status, refresh } = usePolling(api.listDiscovered, DISCOVERY_REFRESH_INTERVAL_MS)
  const nodes = data || []
  const [banner, setBanner] = useState(null)
  const [selected, setSelected] = useState(new Set())
  const [codes, setCodes] = useState({})

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

  const handleNewToken = async () => {
    const label = window.prompt('Label for this machine (optional):', '') || ''
    const group = window.prompt('Group for this machine (e.g. "Lab 1"; optional):', '') || ''
    try {
      const { token } = await api.createPairingToken(label, group)
      setBanner({ token, label, group })
    } catch (err) {
      window.alert(`Failed to create pairing token: ${err.message}`)
    }
  }

  return (
    <Card
      title="Discovered on your network"
      extra={<span className="muted">{status}</span>}
    >
      <Space style={{ marginBottom: 12 }} wrap>
        <Button type="primary" onClick={handleNewToken}>
          New pairing token
        </Button>
      </Space>

      {banner && (
        <Alert
          type="info"
          closable
          onClose={() => setBanner(null)}
          style={{ marginBottom: 12 }}
          message={
            <span>
              Pairing token (use once, on the new machine){banner.group ? ` — group "${banner.group}"` : ''}: <code>{banner.token}</code>
              <br />
              Run: <code>grid-node enroll --hub &lt;hub-url&gt; --token {banner.token} --name "{banner.label || 'my-machine'}"</code>
            </span>
          }
        />
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
          <Typography.Paragraph type="secondary" style={{ marginTop: -4, marginBottom: 8 }}>
            Onboarding a whole lab? Check several machines below, enter each one's code, then pair them all at once.
          </Typography.Paragraph>
          <Space wrap size="middle" align="start">
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
          </Space>
        </>
      ) : (
        <p className="muted">No unpaired machines seen on the network right now.</p>
      )}
    </Card>
  )
}
