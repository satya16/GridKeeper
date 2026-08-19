import { useState } from 'react'
import { Alert, Button, Card, Input, Space, message } from 'antd'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'

const DISCOVERY_REFRESH_INTERVAL_MS = 4000

function DiscoveryCard({ node, onPaired }) {
  const [code, setCode] = useState('')
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
      <span style={{ fontWeight: 600 }}>{node.hostname}</span>
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
          onChange={(e) => setCode(e.target.value)}
        />
        <Button htmlType="submit">Pair</Button>
      </form>
    </Card>
  )
}

export function DiscoverySection({ onPaired }) {
  const { data, status, refresh } = usePolling(api.listDiscovered, DISCOVERY_REFRESH_INTERVAL_MS)
  const nodes = data || []
  const [banner, setBanner] = useState(null)

  const handlePaired = () => {
    refresh()
    onPaired()
  }

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

      {nodes.length ? (
        <Space wrap size="middle" align="start">
          {nodes.map((w) => (
            <DiscoveryCard key={w.discovery_id} node={w} onPaired={handlePaired} />
          ))}
        </Space>
      ) : (
        <p className="muted">No unpaired machines seen on the network right now.</p>
      )}
    </Card>
  )
}
