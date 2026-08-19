import { useState } from 'react'
import { Button, Collapse, Form, Input, Space, Typography, message } from 'antd'
import { api } from '../api.js'

function pct(fraction) {
  return `${Math.round((fraction || 0) * 100)}%`
}

export function BoincBlock({ nodeId, boinc, canWrite, onChanged }) {
  const [attachForm] = Form.useForm()
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
      if (result.status !== 'ok') message.warning(`Command finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      onChanged()
    } catch (err) {
      message.error(`Command failed: ${err.message}`)
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

  const handleAttach = async (values) => {
    setAttaching(true)
    try {
      await run('attach_project', { project_url: values.project_url.trim(), account_key: values.account_key.trim() })
      attachForm.resetFields()
    } finally {
      setAttaching(false)
    }
  }

  return (
    <div>
      <Typography.Text type="secondary" style={{ textTransform: 'uppercase', fontSize: 12, letterSpacing: '0.04em' }}>
        BOINC — run mode: {runMode}
      </Typography.Text>
      {suspendReason && (
        <div>
          <Typography.Text type="warning">CPU suspended: {suspendReason}</Typography.Text>
        </div>
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
                <Space size="small" wrap>
                  <Button
                    size="small"
                    loading={isPending}
                    disabled={isPending}
                    onClick={() => runForProject(p.suspended ? 'resume_project' : 'suspend_project', p.url)}
                  >
                    {p.suspended ? 'Start' : 'Stop'}
                  </Button>
                  <Button size="small" danger loading={isPending} disabled={isPending} onClick={() => detach(p.url)}>
                    Detach
                  </Button>
                </Space>
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
          <Space style={{ marginTop: 8 }} wrap>
            <Button loading={pendingAll} disabled={pendingAll} onClick={() => runForAll('resume_all')}>
              Resume all
            </Button>
            <Button danger loading={pendingAll} disabled={pendingAll} onClick={() => runForAll('suspend_all')}>
              Suspend all
            </Button>
          </Space>

          <Collapse
            ghost
            size="small"
            style={{ marginTop: 8 }}
            items={[
              {
                key: 'attach',
                label: 'Attach a project…',
                children: (
                  <Form form={attachForm} layout="vertical" onFinish={handleAttach} size="small">
                    <Form.Item name="project_url" label="Project URL" rules={[{ required: true }]}>
                      <Input placeholder="https://example.org/project/" />
                    </Form.Item>
                    <Form.Item name="account_key" label="Account key" rules={[{ required: true }]}>
                      <Input.Password placeholder="from the project's “your account” page" />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={attaching} disabled={attaching}>
                        Attach
                      </Button>
                    </Form.Item>
                  </Form>
                ),
              },
            ]}
          />
        </>
      )}
    </div>
  )
}
