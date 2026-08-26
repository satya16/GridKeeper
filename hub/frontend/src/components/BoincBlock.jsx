import { useState } from 'react'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { Accordion, AccordionDetails, AccordionSummary, Box, Button, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'

function pct(fraction) {
  return `${Math.round((fraction || 0) * 100)}%`
}

export function BoincBlock({ nodeId, boinc, canWrite, onChanged }) {
  const [projectUrl, setProjectUrl] = useState('')
  const [accountKey, setAccountKey] = useState('')
  // Command dispatch already blocks until the node's real result comes
  // back (or a 15s timeout) -- these track "is that wait still in flight"
  // so buttons can disable/spin rather than let a fast double-click (e.g.
  // Start while Stop hasn't resolved yet) race against stale local state.
  // attaching specifically also guards against a real BOINC quirk
  // (confirmed live 2026-08-19): a repeat attach_project call isn't
  // reliably rejected by BOINC itself and can create a genuine duplicate
  // project entry -- see node/grid_node/backends/boinc.py.
  const [pendingProjects, setPendingProjects] = useState(new Set())
  const [pendingAll, setPendingAll] = useState(false)
  const [attaching, setAttaching] = useState(false)

  if (!boinc) return null

  const projects = boinc.projects || []
  const tasks = boinc.tasks || []
  const runMode = boinc.run_mode || 'unknown'
  const suspendReason = boinc.cpu_suspend_reason

  const run = async (action, payload) => {
    try {
      const result = await api.issueCommand(nodeId, 'boinc', action, payload)
      if (result.status !== 'ok') notify.warning(`Command finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      onChanged()
    } catch (err) {
      notify.error(`Command failed: ${err.message}`)
    }
  }

  const runForProject = async (action, projectUrl) => {
    setPendingProjects((prev) => new Set(prev).add(projectUrl))
    try {
      await run(action, { project_url: projectUrl })
    } finally {
      setPendingProjects((prev) => {
        const next = new Set(prev)
        next.delete(projectUrl)
        return next
      })
    }
  }

  const runForAll = async (action) => {
    setPendingAll(true)
    try {
      await run(action, {})
    } finally {
      setPendingAll(false)
    }
  }

  const detach = (projectUrl) => {
    if (!window.confirm(`Detach from ${projectUrl}? Any work in progress for this project will be abandoned.`)) return
    runForProject('detach_project', projectUrl)
  }

  const handleAttach = async (e) => {
    e.preventDefault()
    if (!projectUrl.trim() || !accountKey.trim()) return
    setAttaching(true)
    try {
      await run('attach_project', { project_url: projectUrl.trim(), account_key: accountKey.trim() })
      setProjectUrl('')
      setAccountKey('')
    } finally {
      setAttaching(false)
    }
  }

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        BOINC — run mode: {runMode}
      </Typography>
      {suspendReason && (
        <Box>
          <Typography variant="body2" color="warning.main">
            CPU suspended: {suspendReason}
          </Typography>
        </Box>
      )}

      {projects.length ? (
        projects.map((p) => {
          const isPending = pendingProjects.has(p.url)
          return (
            <div className="task-row" key={p.url}>
              <span>
                {p.name || p.url}
                {p.suspended ? ' (suspended)' : ''}
              </span>
              {canWrite && (
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  <Button
                    size="small"
                    variant="outlined"
                    loading={isPending}
                    disabled={isPending}
                    onClick={() => runForProject(p.suspended ? 'resume_project' : 'suspend_project', p.url)}
                  >
                    {p.suspended ? 'Start' : 'Stop'}
                  </Button>
                  <Button size="small" variant="outlined" color="error" loading={isPending} disabled={isPending} onClick={() => detach(p.url)}>
                    Detach
                  </Button>
                </Stack>
              )}
            </div>
          )
        })
      ) : (
        <p className="task-row muted">no attached projects reported</p>
      )}

      {tasks.map((t) => (
        <div key={t.name}>
          <div className="task-row">
            <span>{t.name}</span>
            <span>{pct(t.fraction_done)}</span>
          </div>
          <div className="progress-bar">
            <div style={{ width: pct(t.fraction_done) }} />
          </div>
        </div>
      ))}

      {canWrite && (
        <>
          <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 1 }}>
            <Button size="small" variant="outlined" loading={pendingAll} disabled={pendingAll} onClick={() => runForAll('resume_all')}>
              Resume all
            </Button>
            <Button size="small" variant="outlined" color="error" loading={pendingAll} disabled={pendingAll} onClick={() => runForAll('suspend_all')}>
              Suspend all
            </Button>
          </Stack>

          <Accordion disableGutters elevation={0} square sx={{ mt: 1, bgcolor: 'transparent', '&:before': { display: 'none' } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 0, '& .MuiAccordionSummary-content': { my: 0.5 } }}>
              <Typography variant="body2">Attach a project…</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 0 }}>
              <Stack component="form" onSubmit={handleAttach} spacing={1.5}>
                <TextField
                  size="small"
                  label="Project URL"
                  required
                  placeholder="https://example.org/project/"
                  value={projectUrl}
                  onChange={(e) => setProjectUrl(e.target.value)}
                />
                <TextField
                  size="small"
                  type="password"
                  label="Account key"
                  required
                  placeholder="from the project's “your account” page"
                  value={accountKey}
                  onChange={(e) => setAccountKey(e.target.value)}
                />
                <Button type="submit" variant="contained" size="small" loading={attaching} disabled={attaching} sx={{ alignSelf: 'flex-start' }}>
                  Attach
                </Button>
              </Stack>
            </AccordionDetails>
          </Accordion>
        </>
      )}
    </Box>
  )
}
