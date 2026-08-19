import { Card, Table, Tabs, Typography } from 'antd'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'

const AUDIT_LOG_REFRESH_INTERVAL_MS = 10000

const columns = [
  { title: 'When', dataIndex: 'created_at', render: (v) => new Date(v).toLocaleString(), width: 190 },
  { title: 'User', dataIndex: 'username', width: 140 },
  { title: 'Action', dataIndex: 'action', width: 200 },
  { title: 'Target', dataIndex: 'target', render: (v) => v || <span className="muted">—</span> },
  {
    title: 'Detail',
    dataIndex: 'detail',
    render: (detail) => (detail ? <code style={{ fontSize: 12 }}>{JSON.stringify(detail)}</code> : <span className="muted">—</span>),
  },
]

function AuditLogSection() {
  const { data: entries, status } = usePolling(api.listAuditLog, AUDIT_LOG_REFRESH_INTERVAL_MS)

  return (
    <Card title="Audit log" extra={<span className="muted">{status}</span>}>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        The most recent actions taken by any user, newest first.
      </Typography.Paragraph>
      <Table
        rowKey="id"
        dataSource={entries || []}
        columns={columns}
        pagination={{ pageSize: 25 }}
        size="small"
        scroll={{ x: true }}
      />
    </Card>
  )
}

export function AuditLogPage({ tabBarExtraContent }) {
  const items = [{ key: 'audit-log', label: 'Audit Log', children: <AuditLogSection /> }]
  return <Tabs items={items} tabBarExtraContent={tabBarExtraContent} />
}
