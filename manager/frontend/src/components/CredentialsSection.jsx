import { useState } from 'react'
import { Button, Card, Form, Input, Select, Space, Typography, message } from 'antd'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'

const CREDENTIALS_REFRESH_INTERVAL_MS = 10000

function CredentialRow({ credential, workers, onChanged, onWorkerChanged }) {
  const [workerId, setWorkerId] = useState()
  const [applying, setApplying] = useState(false)

  const handleApply = async () => {
    if (!workerId) return
    setApplying(true)
    try {
      const result = await api.applyCredential(credential.id, workerId)
      if (result.status !== 'ok') {
        message.warning(`Apply finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      } else {
        message.success(`Applied '${credential.name}' to the selected machine.`)
      }
      onChanged()
      onWorkerChanged()
    } catch (err) {
      message.error(`Apply failed: ${err.message}`)
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
      message.error(`Delete failed: ${err.message}`)
    }
  }

  return (
    <div className="task-row">
      <span>
        <strong>{credential.name}</strong> — {credential.project_url}
        <span className="muted">
          {' — '}
          {credential.last_used_at ? `last applied ${new Date(credential.last_used_at).toLocaleString()}` : 'never applied'}
        </span>
      </span>
      <Space size="small">
        <Select
          size="small"
          style={{ minWidth: 160 }}
          placeholder="Apply to machine…"
          value={workerId}
          onChange={setWorkerId}
          options={workers.map((w) => ({ value: w.id, label: w.name }))}
        />
        <Button size="small" type="primary" loading={applying} disabled={applying || !workerId} onClick={handleApply}>
          Apply
        </Button>
        <Button size="small" danger onClick={handleDelete}>
          Delete
        </Button>
      </Space>
    </div>
  )
}

export function CredentialsSection({ workers, onWorkerChanged }) {
  const { data: credentials, status, refresh } = usePolling(api.listCredentials, CREDENTIALS_REFRESH_INTERVAL_MS)
  const [form] = Form.useForm()

  const handleCreate = async (values) => {
    try {
      await api.createCredential(values.name.trim(), values.project_url.trim(), values.account_key.trim())
      message.success(`Saved '${values.name.trim()}'.`)
      form.resetFields()
      refresh()
    } catch (err) {
      message.error(`Save failed: ${err.message}`)
    }
  }

  return (
    <Card
      title="Saved BOINC account keys"
      extra={<span className="muted">{status}</span>}
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        Save a project account key once, then apply it to any machine below without pasting it into that
        machine's attach form each time.
      </Typography.Paragraph>

      {credentials && credentials.length ? (
        credentials.map((c) => (
          <CredentialRow key={c.id} credential={c} workers={workers} onChanged={refresh} onWorkerChanged={onWorkerChanged} />
        ))
      ) : (
        <p className="task-row muted">No saved credentials yet.</p>
      )}

      <Form form={form} layout="inline" onFinish={handleCreate} style={{ marginTop: 12 }}>
        <Form.Item name="name" rules={[{ required: true }]}>
          <Input placeholder="Name (e.g. School WCG account)" style={{ width: 220 }} />
        </Form.Item>
        <Form.Item name="project_url" rules={[{ required: true }]}>
          <Input placeholder="Project URL" style={{ width: 220 }} />
        </Form.Item>
        <Form.Item name="account_key" rules={[{ required: true }]}>
          <Input.Password placeholder="Account key" style={{ width: 200 }} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit">
            Save
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}
