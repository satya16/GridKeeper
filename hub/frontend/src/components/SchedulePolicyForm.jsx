import { useState } from 'react'
import { Box, Button, Checkbox, FormControlLabel, Stack, TextField, Typography } from '@mui/material'

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

function clampHour(n) {
  return Math.min(23, Math.max(0, n))
}

// Shared by the fleet-wide form and each node card's per-machine
// override -- same fields, same semantics as the previous
// readSchedulePolicy()/renderScheduleBlock() in dashboard.js.
export function SchedulePolicyForm({ initialPolicy, submitLabel, onSubmit }) {
  const [policy, setPolicy] = useState(initialPolicy || DEFAULT_SCHEDULE_POLICY)

  const set = (patch) => setPolicy((p) => ({ ...p, ...patch }))

  return (
    <Box
      component="form"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit(policy)
      }}
    >
      <Stack spacing={1} sx={{ width: '100%' }}>
        <FormControlLabel
          control={<Checkbox checked={policy.enabled} onChange={(e) => set({ enabled: e.target.checked })} />}
          label="Enable schedule (unchecked = always allowed to run)"
        />
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <FormControlLabel
            control={<Checkbox checked={policy.restrict_hours} onChange={(e) => set({ restrict_hours: e.target.checked })} />}
            label="Only between"
          />
          <TextField
            type="number"
            size="small"
            value={policy.active_start_hour}
            onChange={(e) => set({ active_start_hour: clampHour(Number(e.target.value) || 0) })}
            slotProps={{ htmlInput: { min: 0, max: 23 } }}
            sx={{ width: 80 }}
          />
          <Typography variant="body2">:00 and</Typography>
          <TextField
            type="number"
            size="small"
            value={policy.active_end_hour}
            onChange={(e) => set({ active_end_hour: clampHour(Number(e.target.value) || 0) })}
            slotProps={{ htmlInput: { min: 0, max: 23 } }}
            sx={{ width: 80 }}
          />
          <Typography variant="body2">:00</Typography>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <FormControlLabel
            control={<Checkbox checked={policy.only_when_idle} onChange={(e) => set({ only_when_idle: e.target.checked })} />}
            label="Only when idle (BOINC: exact; Folding@home: best-effort) -- threshold"
          />
          <TextField
            type="number"
            size="small"
            value={policy.idle_threshold_minutes}
            onChange={(e) => set({ idle_threshold_minutes: Math.max(1, Number(e.target.value) || 1) })}
            slotProps={{ htmlInput: { min: 1 } }}
            sx={{ width: 80 }}
          />
          <Typography variant="body2">min</Typography>
        </Stack>
        <Button type="submit" variant="contained" sx={{ alignSelf: 'flex-start' }}>
          {submitLabel}
        </Button>
      </Stack>
    </Box>
  )
}
