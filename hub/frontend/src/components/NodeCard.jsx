import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { Accordion, AccordionDetails, AccordionSummary, Box, Card, CardContent, CardHeader, Divider, Typography } from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'
import { BoincBlock } from './BoincBlock.jsx'
import { FahBlock } from './FahBlock.jsx'
import { GenericBackendBlock } from './GenericBackendBlock.jsx'
import { SchedulePolicyForm, scheduleSummary } from './SchedulePolicyForm.jsx'

const KNOWN_BACKENDS = new Set(['boinc', 'fah'])

export function NodeCard({ node, backends, canWrite, onChanged }) {
  const status = node.status || {}
  // Any status key that isn't boinc/fah is a third-party plugin backend
  // (see node/grid_node/backends/base.py) -- rendered with the generic
  // fallback block instead of a bespoke component.
  const otherBackendNames = Object.keys(status).filter((name) => !KNOWN_BACKENDS.has(name))

  const handleSetGroup = async () => {
    const next = window.prompt('Group for this machine (e.g. "Lab 1", "Library"; blank to ungroup):', node.group)
    if (next === null || next === node.group) return
    try {
      await api.setNodeGroup(node.id, next)
      onChanged()
    } catch (err) {
      notify.error(`Failed to set group: ${err.message}`)
    }
  }

  const handleSaveSchedule = async (policy) => {
    try {
      await api.setNodeSchedule(node.id, policy)
      onChanged()
    } catch (err) {
      notify.error(`Failed to save schedule: ${err.message}`)
    }
  }

  return (
    <Card>
      <CardHeader
        sx={{ pb: 1 }}
        title={
          <span title={node.name} style={{ display: 'flex', alignItems: 'center', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            <span className={`dot ${node.online ? 'online' : 'offline'}`} />
            {node.name}
          </span>
        }
        action={<span className="muted">{node.os_name}</span>}
      />
      <CardContent sx={{ pt: 0 }}>
        {canWrite ? (
          <button
            type="button"
            onClick={handleSetGroup}
            style={{
              background: 'transparent',
              border: '1px dashed var(--gk-border)',
              color: 'var(--gk-muted)',
              borderRadius: 999,
              padding: '2px 10px',
              fontSize: '0.75rem',
              cursor: 'pointer',
              marginBottom: 8,
            }}
          >
            {node.group || 'Set group…'}
          </button>
        ) : (
          node.group && (
            <span
              style={{
                display: 'inline-block',
                border: '1px solid var(--gk-border)',
                color: 'var(--gk-muted)',
                borderRadius: 999,
                padding: '2px 10px',
                fontSize: '0.75rem',
                marginBottom: 8,
              }}
            >
              {node.group}
            </span>
          )
        )}

        <BoincBlock nodeId={node.id} boinc={status.boinc} canWrite={canWrite} onChanged={onChanged} />
        {status.boinc && status.fah && <Divider sx={{ my: 1 }} />}
        <FahBlock nodeId={node.id} fah={status.fah} canWrite={canWrite} onChanged={onChanged} />
        {otherBackendNames.map((name) => (
          <Box key={name}>
            {(status.boinc || status.fah) && <Divider sx={{ my: 1 }} />}
            <GenericBackendBlock
              nodeId={node.id}
              backendName={name}
              backendStatus={status[name]}
              actions={(backends || []).find((b) => b.name === name)?.actions}
              canWrite={canWrite}
              onChanged={onChanged}
            />
          </Box>
        ))}
        {!status.boinc && !status.fah && !otherBackendNames.length && (
          <Typography variant="body2" color="text.secondary">
            No status reported yet.
          </Typography>
        )}

        {canWrite ? (
          <Accordion disableGutters elevation={0} square sx={{ mt: 1, bgcolor: 'transparent', '&:before': { display: 'none' } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 0, '& .MuiAccordionSummary-content': { my: 0.5 } }}>
              <Typography variant="body2">Schedule: {scheduleSummary(node.schedule)}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 0 }}>
              <SchedulePolicyForm initialPolicy={node.schedule} submitLabel="Save schedule" onSubmit={handleSaveSchedule} />
            </AccordionDetails>
          </Accordion>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Schedule: {scheduleSummary(node.schedule)}
          </Typography>
        )}
      </CardContent>
    </Card>
  )
}
