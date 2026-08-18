import { useState } from 'react'
import { Card, Select, Space } from 'antd'
import { WorkerCard } from './WorkerCard.jsx'

export function WorkerListSection({ workers, groups, onChanged }) {
  const [groupFilter, setGroupFilter] = useState('')
  const filtered = groupFilter ? workers.filter((w) => w.group === groupFilter) : workers

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
            <WorkerCard key={w.id} worker={w} onChanged={onChanged} />
          ))}
        </div>
      ) : workers.length ? (
        <p className="muted">No machines in this group.</p>
      ) : (
        <p className="muted">No workers enrolled yet. Use "New pairing token" to add one.</p>
      )}
    </Card>
  )
}
