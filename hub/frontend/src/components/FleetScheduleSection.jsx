import { useState } from 'react'
import { Card, CardContent, CardHeader, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'
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
      notify.success(`Schedule applied to ${result.length} machine(s).`)
      onApplied()
    } catch (err) {
      notify.error(`Failed to apply schedule: ${err.message}`)
    }
  }

  return (
    <Card>
      <CardHeader title="Fleet schedule" />
      <CardContent sx={{ pt: 0 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Applies to a group, or every machine at once.
        </Typography>
        <Stack spacing={1.5} sx={{ width: '100%' }}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Typography variant="body2">Apply to</Typography>
            <TextField select size="small" value={effectiveGroup} onChange={(e) => setGroup(e.target.value)} sx={{ minWidth: 180 }}>
              {canApplyToAll && <MenuItem value="">All machines</MenuItem>}
              {groups.map((g) => (
                <MenuItem key={g} value={g}>
                  {g}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
          <SchedulePolicyForm
            submitLabel={effectiveGroup ? `Apply to "${effectiveGroup}"` : 'Apply to all machines'}
            onSubmit={handleSubmit}
          />
        </Stack>
      </CardContent>
    </Card>
  )
}
