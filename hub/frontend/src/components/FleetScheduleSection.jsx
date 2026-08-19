import { useState } from 'react'
import { Card, Select, Space, Typography, message } from 'antd'
import { api } from '../api.js'
import { SchedulePolicyForm } from './SchedulePolicyForm.jsx'

export function FleetScheduleSection({ groups, canApplyToAll, onApplied }) {
  const [group, setGroup] = useState('')
  // A group_manager has no "All machines" option (backend rejects
  // apply-all for anyone but admin) -- fall back to their own first
  // group rather than leaving the selection on a value they can't
  // actually submit. Derived at render time, not via an effect, since
  // it's just "pick a sane default until the user picks one themself."
  const effectiveGroup = group || (!canApplyToAll && groups.length ? groups[0] : '')

  const handleSubmit = async (policy) => {
    try {
      const result = await api.applySchedule(effectiveGroup, policy)
      message.success(`Schedule applied to ${result.length} machine(s).`)
      onApplied()
    } catch (err) {
      message.error(`Failed to apply schedule: ${err.message}`)
    }
  }

  return (
    <Card title="Fleet schedule">
      <Typography.Paragraph type="secondary" style={{ marginTop: -8, marginBottom: 12 }}>
        Applies to a group, or every machine at once.
      </Typography.Paragraph>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space wrap>
          Apply to
          <Select
            style={{ minWidth: 180 }}
            value={effectiveGroup}
            onChange={setGroup}
            options={[
              ...(canApplyToAll ? [{ value: '', label: 'All machines' }] : []),
              ...groups.map((g) => ({ value: g, label: g })),
            ]}
          />
        </Space>
        <SchedulePolicyForm
          submitLabel={effectiveGroup ? `Apply to "${effectiveGroup}"` : 'Apply to all machines'}
          onSubmit={handleSubmit}
        />
      </Space>
    </Card>
  )
}
