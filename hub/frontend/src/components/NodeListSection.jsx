import { useState } from 'react'
import { Card, Select, Space } from 'antd'
import { NodeCard } from './NodeCard.jsx'

export function NodeListSection({ nodes, groups, onChanged }) {
  const [groupFilter, setGroupFilter] = useState('')
  const filtered = groupFilter ? nodes.filter((w) => w.group === groupFilter) : nodes

  return (
    <Card
      title="Machines"
      extra={
        <Space size="small" className="muted">
          Group
          <Select
            style={{ minWidth: 140 }}
            size="small"
            value={groupFilter}
            onChange={setGroupFilter}
            options={[{ value: '', label: 'All' }, ...groups.map((g) => ({ value: g, label: g }))]}
          />
        </Space>
      }
    >
      {filtered.length ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {filtered.map((w) => (
            <NodeCard key={w.id} node={w} onChanged={onChanged} />
          ))}
        </div>
      ) : nodes.length ? (
        <p className="muted">No machines in this group.</p>
      ) : (
        <p className="muted">No nodes enrolled yet. Use "New pairing token" to add one.</p>
      )}
    </Card>
  )
}
