import { useState } from 'react'
import { Button, Checkbox, InputNumber, Space } from 'antd'

export const DEFAULT_SCHEDULE_POLICY = {
  enabled: false,
  restrict_hours: false,
  active_start_hour: 22,
  active_end_hour: 6,
  only_when_idle: false,
  idle_threshold_minutes: 3,
}

export function scheduleSummary(policy) {
  if (!policy || !policy.enabled) return 'No restrictions -- always allowed to run'
  const parts = []
  if (policy.restrict_hours) parts.push(`${policy.active_start_hour}:00–${policy.active_end_hour}:00`)
  if (policy.only_when_idle) parts.push('idle only')
  return parts.length ? parts.join(', ') : 'Enabled (no conditions set)'
}

// Shared by the fleet-wide form and each worker card's per-machine
// override -- same fields, same semantics as the previous
// readSchedulePolicy()/renderScheduleBlock() in dashboard.js.
export function SchedulePolicyForm({ initialPolicy, submitLabel, onSubmit }) {
  const [policy, setPolicy] = useState(initialPolicy || DEFAULT_SCHEDULE_POLICY)

  const set = (patch) => setPolicy((p) => ({ ...p, ...patch }))

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit(policy)
      }}
    >
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Checkbox checked={policy.enabled} onChange={(e) => set({ enabled: e.target.checked })}>
          Enable schedule (unchecked = always allowed to run)
        </Checkbox>
        <Space wrap>
          <Checkbox checked={policy.restrict_hours} onChange={(e) => set({ restrict_hours: e.target.checked })}>
            Only between
          </Checkbox>
          <InputNumber
            min={0}
            max={23}
            value={policy.active_start_hour}
            onChange={(v) => set({ active_start_hour: v ?? 0 })}
          />
          :00 and
          <InputNumber
            min={0}
            max={23}
            value={policy.active_end_hour}
            onChange={(v) => set({ active_end_hour: v ?? 0 })}
          />
          :00
        </Space>
        <Space wrap>
          <Checkbox checked={policy.only_when_idle} onChange={(e) => set({ only_when_idle: e.target.checked })}>
            Only when idle (BOINC: exact; Folding@home: best-effort) -- threshold
          </Checkbox>
          <InputNumber
            min={1}
            value={policy.idle_threshold_minutes}
            onChange={(v) => set({ idle_threshold_minutes: v ?? 1 })}
          />
          min
        </Space>
        <Button type="primary" htmlType="submit">
          {submitLabel}
        </Button>
      </Space>
    </form>
  )
}
