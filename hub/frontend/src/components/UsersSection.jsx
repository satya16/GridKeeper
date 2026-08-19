import { useState } from 'react'
import { Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography, message } from 'antd'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'

const USERS_REFRESH_INTERVAL_MS = 15000

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin — full access to everything' },
  { value: 'group_manager', label: 'Group manager — view/edit their own group(s)' },
  { value: 'machine_manager', label: 'Machine manager — view/edit their own machine(s)' },
  { value: 'viewer', label: 'Viewer — read-only, everything' },
]

const ROLE_COLORS = { admin: 'red', group_manager: 'blue', machine_manager: 'green', viewer: 'default' }

// Scope is a plain comma-separated list on the wire (see hub/app/db.py's
// User.scope docstring) -- group names for group_manager, node ids for
// machine_manager. The dashboard offers a friendlier multi-select over
// known groups/node names, but still round-trips through that same flat
// string.
function ScopeField({ role, groups, nodes, value, onChange }) {
  if (role === 'group_manager') {
    return (
      <Select
        mode="tags"
        placeholder="Group(s) this user manages"
        style={{ minWidth: 240 }}
        value={value ? value.split(',').filter(Boolean) : []}
        onChange={(vals) => onChange(vals.join(','))}
        options={groups.map((g) => ({ value: g, label: g }))}
      />
    )
  }
  if (role === 'machine_manager') {
    return (
      <Select
        mode="multiple"
        placeholder="Machine(s) this user manages"
        style={{ minWidth: 240 }}
        value={value ? value.split(',').filter(Boolean) : []}
        onChange={(vals) => onChange(vals.join(','))}
        options={nodes.map((n) => ({ value: n.id, label: n.name }))}
      />
    )
  }
  return null
}

function EditUserModal({ user, groups, nodes, onClose, onSaved }) {
  const [form] = Form.useForm()
  const [role, setRole] = useState(user.role)
  const [scope, setScope] = useState(user.scope)
  const [saving, setSaving] = useState(false)

  const handleOk = async () => {
    setSaving(true)
    try {
      const values = await form.validateFields()
      const changes = { role, scope: role === 'admin' || role === 'viewer' ? '' : scope }
      if (values.new_password) changes.password = values.new_password
      await api.updateUser(user.id, changes)
      message.success(`Updated '${user.username}'.`)
      onSaved()
    } catch (err) {
      if (err?.errorFields) return // form validation error, already shown inline
      message.error(`Update failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Edit ${user.username}`} open onOk={handleOk} onCancel={onClose} confirmLoading={saving}>
      <Form form={form} layout="vertical">
        <Form.Item label="Role">
          <Select value={role} onChange={setRole} options={ROLE_OPTIONS} />
        </Form.Item>
        {(role === 'group_manager' || role === 'machine_manager') && (
          <Form.Item label="Scope">
            <ScopeField role={role} groups={groups} nodes={nodes} value={scope} onChange={setScope} />
          </Form.Item>
        )}
        <Form.Item name="new_password" label="Reset password (optional)" rules={[{ min: 4 }]}>
          <Input.Password placeholder="Leave blank to keep current password" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export function UsersSection({ groups, nodes }) {
  const { data: users, status, refresh } = usePolling(api.listUsers, USERS_REFRESH_INTERVAL_MS)
  const [form] = Form.useForm()
  const [createRole, setCreateRole] = useState('viewer')
  const [createScope, setCreateScope] = useState('')
  const [editing, setEditing] = useState(null)

  const handleCreate = async (values) => {
    try {
      const scope = createRole === 'admin' || createRole === 'viewer' ? '' : createScope
      await api.createUser(values.username.trim(), values.password, createRole, scope)
      message.success(`Created '${values.username.trim()}'.`)
      form.resetFields()
      setCreateRole('viewer')
      setCreateScope('')
      refresh()
    } catch (err) {
      message.error(`Create failed: ${err.status === 409 ? 'that username is already taken.' : err.message}`)
    }
  }

  const handleDelete = async (user) => {
    if (!window.confirm(`Delete user '${user.username}'? This can't be undone.`)) return
    try {
      await api.deleteUser(user.id)
      refresh()
    } catch (err) {
      message.error(`Delete failed: ${err.message}`)
    }
  }

  const columns = [
    { title: 'Username', dataIndex: 'username' },
    {
      title: 'Role',
      dataIndex: 'role',
      render: (role) => <Tag color={ROLE_COLORS[role]}>{ROLE_OPTIONS.find((r) => r.value === role)?.label.split(' — ')[0] || role}</Tag>,
    },
    { title: 'Scope', dataIndex: 'scope', render: (scope) => scope || <span className="muted">—</span> },
    { title: 'Created', dataIndex: 'created_at', render: (v) => new Date(v).toLocaleString() },
    {
      title: '',
      key: 'actions',
      render: (_, user) => (
        <Space size="small">
          <Button size="small" onClick={() => setEditing(user)}>
            Edit
          </Button>
          <Button size="small" danger onClick={() => handleDelete(user)}>
            Delete
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Card title="Users" extra={<span className="muted">{status}</span>}>
      <Table
        rowKey="id"
        dataSource={users || []}
        columns={columns}
        pagination={false}
        size="small"
        scroll={{ x: true }}
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5}>Add a user</Typography.Title>
      <Form form={form} layout="inline" onFinish={handleCreate} style={{ rowGap: 8 }}>
        <Form.Item name="username" rules={[{ required: true }]}>
          <Input placeholder="Username" style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="password" rules={[{ required: true, min: 4 }]}>
          <Input.Password placeholder="Password" style={{ width: 160 }} />
        </Form.Item>
        <Form.Item>
          <Select value={createRole} onChange={setCreateRole} options={ROLE_OPTIONS} style={{ width: 200 }} />
        </Form.Item>
        {(createRole === 'group_manager' || createRole === 'machine_manager') && (
          <Form.Item>
            <ScopeField role={createRole} groups={groups} nodes={nodes} value={createScope} onChange={setCreateScope} />
          </Form.Item>
        )}
        <Form.Item>
          <Button type="primary" htmlType="submit">
            Add
          </Button>
        </Form.Item>
      </Form>

      {editing && (
        <EditUserModal
          user={editing}
          groups={groups}
          nodes={nodes}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            refresh()
          }}
        />
      )}
    </Card>
  )
}
