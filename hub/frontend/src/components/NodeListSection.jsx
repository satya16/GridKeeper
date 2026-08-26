import { useState } from 'react'
import { Card, CardContent, CardHeader, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { NodeCard } from './NodeCard.jsx'

export function NodeListSection({ nodes, groups, backends, canWrite, onChanged }) {
  const [groupFilter, setGroupFilter] = useState('')
  const filtered = groupFilter ? nodes.filter((w) => w.group === groupFilter) : nodes

  return (
    <Card>
      <CardHeader
        title="Machines"
        action={
          <Stack direction="row" spacing={1} alignItems="center" className="muted">
            <Typography variant="body2" color="text.secondary">
              Group
            </Typography>
            <TextField select size="small" value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)} sx={{ minWidth: 140 }}>
              <MenuItem value="">All</MenuItem>
              {groups.map((g) => (
                <MenuItem key={g} value={g}>
                  {g}
                </MenuItem>
              ))}
            </TextField>
          </Stack>
        }
      />
      <CardContent sx={{ pt: 0 }}>
        {filtered.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(340px, 100%), 1fr))', gap: 16 }}>
            {filtered.map((w) => (
              <NodeCard key={w.id} node={w} backends={backends} canWrite={canWrite} onChanged={onChanged} />
            ))}
          </div>
        ) : nodes.length ? (
          <p className="muted">No machines in this group.</p>
        ) : (
          <p className="muted">No nodes enrolled yet. Use "New pairing token" to add one.</p>
        )}
      </CardContent>
    </Card>
  )
}
