import { useState } from 'react'
import { Button, Input, Select, Space, Typography, message } from 'antd'
import { api } from '../api.js'

// Fallback UI for any backend that isn't boinc/fah -- i.e. a third-party
// grid_node.backends plugin (see node/grid_node/backends/base.py). Not as
// polished as BoincBlock/FahBlock (raw status JSON + a free-form action
// picker instead of purpose-built controls), but it makes a plugin usable
// from the dashboard immediately, with zero hub-side code for that
// specific backend. `actions` comes from the hub's BackendCapability
// registry (GET /api/backends, see hub/app/api/backends.py) -- reported by
// a node's own status frame, not guessed.
export function GenericBackendBlock({ nodeId, backendName, backendStatus, actions, canWrite, onChanged }) {
  const [action, setAction] = useState()
  const [payloadText, setPayloadText] = useState('{}')
  const [running, setRunning] = useState(false)

  const handleRun = async () => {
    if (!action) return
    let payload
    try {
      payload = payloadText.trim() ? JSON.parse(payloadText) : {}
    } catch {
      message.error('Payload must be valid JSON (or left empty for {}).')
      return
    }
    setRunning(true)
    try {
      const result = await api.issueCommand(nodeId, backendName, action, payload)
      if (result.status !== 'ok') {
        message.warning(`Command finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      } else {
        message.success(`${backendName}.${action} → ok`)
      }
      onChanged()
    } catch (err) {
      message.error(`Command failed: ${err.message}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <Typography.Text type="secondary" style={{ textTransform: 'uppercase', fontSize: 12, letterSpacing: '0.04em' }}>
        {backendName}
      </Typography.Text>
      <pre
        style={{
          background: 'var(--gk-card)',
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
        <Space direction="vertical" size="small" style={{ width: '100%', marginTop: 4 }}>
          <Space wrap>
            <Select
              size="small"
              style={{ minWidth: 160 }}
              placeholder="Action…"
              value={action}
              onChange={setAction}
              options={actions.map((a) => ({ value: a, label: a }))}
            />
            <Button size="small" type="primary" loading={running} disabled={running || !action} onClick={handleRun}>
              Run
            </Button>
          </Space>
          <Input.TextArea
            size="small"
            value={payloadText}
            onChange={(e) => setPayloadText(e.target.value)}
            placeholder="{}"
            autoSize={{ minRows: 1, maxRows: 3 }}
          />
        </Space>
      )}
    </div>
  )
}
