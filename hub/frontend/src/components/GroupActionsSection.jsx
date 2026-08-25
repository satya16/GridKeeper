import { useState } from 'react'
import { Button, Card, Input, Select, Space, Typography, message } from 'antd'
import { api } from '../api.js'

// B2: the group-scoped counterpart to FleetScheduleSection -- "suspend all
// of Lab 1" without opening each node card. Same effectiveGroup pattern:
// a group_manager (no "All machines" option) falls back to their own
// first group rather than a value they can't actually submit.
export function GroupActionsSection({ groups, backends, canIssueToAll, onIssued }) {
  const [group, setGroup] = useState('')
  const [backendName, setBackendName] = useState()
  const [action, setAction] = useState()
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
      message.error('Payload must be valid JSON (or left empty for {}).')
      return
    }
    setRunning(true)
    try {
      const results = effectiveGroup
        ? await api.issueCommandToGroup(effectiveGroup, backendName, action, payload)
        : await api.issueCommandToAll(backendName, action, payload)
      const ok = results.filter((r) => r.status === 'ok').length
      const skipped = results.filter((r) => r.status === 'skipped').length
      message.info(`${backendName}.${action}: ok on ${ok}/${results.length} machine(s)${skipped ? `, ${skipped} offline (skipped)` : ''}`)
      onIssued()
    } catch (err) {
      message.error(`Command failed: ${err.message}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <Card title="Group actions" style={{ marginTop: 16 }}>
      <Typography.Paragraph type="secondary" style={{ marginTop: -8, marginBottom: 12 }}>
        Run one command against every machine in a group (or the whole fleet) at once -- offline machines are skipped,
        not failed.
      </Typography.Paragraph>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space wrap>
          Target
          <Select
            style={{ minWidth: 180 }}
            value={effectiveGroup}
            onChange={setGroup}
            options={[...(canIssueToAll ? [{ value: '', label: 'All machines' }] : []), ...groups.map((g) => ({ value: g, label: g }))]}
          />
          Backend
          <Select
            style={{ minWidth: 160 }}
            placeholder="Backend…"
            value={backendName}
            onChange={(v) => {
              setBackendName(v)
              setAction(undefined)
            }}
            options={backends.map((b) => ({ value: b.name, label: b.label || b.name }))}
          />
          Action
          <Select
            style={{ minWidth: 160 }}
            placeholder="Action…"
            value={action}
            onChange={setAction}
            disabled={!backend}
            options={(backend?.actions || []).map((a) => ({ value: a, label: a }))}
          />
        </Space>
        <Input.TextArea
          value={payloadText}
          onChange={(e) => setPayloadText(e.target.value)}
          placeholder="{}"
          autoSize={{ minRows: 1, maxRows: 3 }}
          style={{ maxWidth: 400 }}
        />
        <Button type="primary" loading={running} disabled={running || !backendName || !action} onClick={handleRun}>
          {effectiveGroup ? `Run on "${effectiveGroup}"` : 'Run on all machines'}
        </Button>
      </Space>
    </Card>
  )
}
