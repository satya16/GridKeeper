import { useState } from 'react'
import { Card, Input, Button, Space, message } from 'antd'
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

  const handlePaired = () => {
    refresh()
    onPaired()
  }

  return (
    <Card title="Discovered on your network" extra={<span className="muted">{status}</span>}>
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
