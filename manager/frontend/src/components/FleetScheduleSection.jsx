import { useState } from 'react'
import { Card, Select, Space, message } from 'antd'
import { api } from '../api.js'
import { SchedulePolicyForm } from './SchedulePolicyForm.jsx'

export function FleetScheduleSection({ groups, onApplied }) {
  const [group, setGroup] = useState('')

  const handleSubmit = async (policy) => {
    try {
      const result = await api.applySchedule(group, policy)
      message.success(`Schedule applied to ${result.length} machine(s).`)
      onApplied()
    } catch (err) {
      message.error(`Failed to apply schedule: ${err.message}`)
    }
  }

  return (
    <Card
      title="Fleet schedule"
      extra={<span className="muted">applies to a group, or every machine at once</span>}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          Apply to
          <Select
            style={{ minWidth: 180 }}
            value={group}
            onChange={setGroup}
            options={[{ value: '', label: 'All machines' }, ...groups.map((g) => ({ value: g, label: g }))]}
          />
        </Space>
        <SchedulePolicyForm submitLabel={group ? `Apply to "${group}"` : 'Apply to all machines'} onSubmit={handleSubmit} />
      </Space>
    </Card>
  )
}
