import { useState } from 'react'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'

// From https://api.foldingathome.org/project/cause, minus "unspecified"
// (the client itself substitutes "any" for that) -- fetched and confirmed
// live 2026-08-18 against the same endpoint the official web-control
// frontend (fah-web-client-bastet's CommonSettings.vue) calls. Static
// here rather than fetched at runtime -- see _docs/knowledge-graph/fah-backend.md.
const FAH_CAUSES = ['any', 'alzheimers', 'cancer', 'covid-19', 'diabetes', 'huntingtons', 'influenza', 'parkinsons']

function pct(fraction) {
  return `${Math.round((fraction || 0) * 100)}%`
}

export function FahBlock({ nodeId, fah, canWrite, onChanged }) {
  const account = fah?.account || { user: 'Anonymous', team: 0, cause: 'any', fold_anon: false }
  const [cause, setCause] = useState(account.cause)
  const [foldAnon, setFoldAnon] = useState(account.fold_anon)
  const [user, setUser] = useState('')
  const [team, setTeam] = useState('')
  const [passkey, setPasskey] = useState('')
  const [saving, setSaving] = useState(false)

  if (!fah) return null

  const slots = fah.slots || []

  const run = async (action, payload) => {
    try {
      const result = await api.issueCommand(nodeId, 'fah', action, payload)
      if (result.status !== 'ok') notify.warning(`Command finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      onChanged()
    } catch (err) {
      notify.error(`Command failed: ${err.message}`)
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      // cause/fold_anon always have a value; user/team/passkey are only
      // sent if the admin actually typed something -- an empty field
      // shouldn't overwrite a real value with blank/zero.
      const fields = { cause, fold_anon: !!foldAnon }
      if (user.trim()) fields.user = user.trim()
      if (team !== '') fields.team = Number(team)
      if (passkey.trim()) fields.passkey = passkey.trim()
      await run('set_config', fields)
      setPasskey('')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        Folding@home
      </Typography>
      <p className="task-row muted">
        {account.fold_anon ? 'Folding anonymously' : `As ${account.user}${account.team ? ` (team ${account.team})` : ''}`}
        {' — cause: '}
        {account.cause}
      </p>

      {slots.length ? (
        slots.map((s, i) => (
          <div key={i}>
            <div className="task-row">
              <span>
                Slot {s.id || '(default)'} — {s.status}
                {s.project ? ` (${s.project})` : ''}
              </span>
              <span>{pct(s.progress)}</span>
            </div>
            <div className="progress-bar">
              <div style={{ width: pct(s.progress) }} />
            </div>
          </div>
        ))
      ) : (
        <p className="task-row muted">no slots reported</p>
      )}

      {canWrite && (
        <>
          <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 1 }}>
            <Button size="small" variant="outlined" onClick={() => run('unpause_all', {})}>
              Resume all
            </Button>
            <Button size="small" variant="outlined" color="error" onClick={() => run('pause_all', {})}>
              Pause all
            </Button>
          </Stack>

          <Accordion disableGutters elevation={0} square sx={{ mt: 1, bgcolor: 'transparent', '&:before': { display: 'none' } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 0, '& .MuiAccordionSummary-content': { my: 0.5 } }}>
              <Typography variant="body2">Account & cause…</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 0 }}>
              <Stack component="form" onSubmit={handleSave} spacing={1.5}>
                <TextField select size="small" label="Cause" value={cause} onChange={(e) => setCause(e.target.value)}>
                  {FAH_CAUSES.map((c) => (
                    <MenuItem key={c} value={c}>
                      {c}
                    </MenuItem>
                  ))}
                </TextField>
                <FormControlLabel
                  control={<Checkbox checked={foldAnon} onChange={(e) => setFoldAnon(e.target.checked)} />}
                  label="Fold anonymously (no account needed)"
                />
                <TextField size="small" label="Username" placeholder={account.user} value={user} onChange={(e) => setUser(e.target.value)} />
                <TextField
                  type="number"
                  size="small"
                  label="Team number"
                  placeholder={String(account.team)}
                  value={team}
                  onChange={(e) => setTeam(e.target.value)}
                  slotProps={{ htmlInput: { min: 0 } }}
                />
                <TextField
                  type="password"
                  size="small"
                  label="Passkey"
                  placeholder="from your F@H account page (optional)"
                  value={passkey}
                  onChange={(e) => setPasskey(e.target.value)}
                />
                <Button type="submit" variant="contained" size="small" loading={saving} sx={{ alignSelf: 'flex-start' }}>
                  Save
                </Button>
              </Stack>
            </AccordionDetails>
          </Accordion>
        </>
      )}
    </Box>
  )
}
