import { useState } from 'react'
import { Button, Collapse, Form, Input, Space, Typography, message } from 'antd'
import { api } from '../api.js'

function pct(fraction) {
  return `${Math.round((fraction || 0) * 100)}%`
}

export function BoincBlock({ workerId, boinc, onChanged }) {
  const [attachForm] = Form.useForm()

  if (!boinc) return null

  const projects = boinc.projects || []
  const tasks = boinc.tasks || []
  const runMode = boinc.run_mode || 'unknown'

  const run = async (action, payload) => {
    try {
      const result = await api.issueCommand(workerId, 'boinc', action, payload)
      if (result.status !== 'ok') message.warning(`Command finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      onChanged()
    } catch (err) {
      message.error(`Command failed: ${err.message}`)
    }
  }

  const detach = (projectUrl) => {
    if (!window.confirm(`Detach from ${projectUrl}? Any work in progress for this project will be abandoned.`)) return
    run('detach_project', { project_url: projectUrl })
  }

  const handleAttach = async (values) => {
    await run('attach_project', { project_url: values.project_url.trim(), account_key: values.account_key.trim() })
    attachForm.resetFields()
  }

  return (
    <div>
      <Typography.Text type="secondary" style={{ textTransform: 'uppercase', fontSize: 12, letterSpacing: '0.04em' }}>
        BOINC — run mode: {runMode}
      </Typography.Text>

      {projects.length ? (
        projects.map((p) => (
          <div className="task-row" key={p.url}>
            <span>
              {p.name || p.url}
              {p.suspended ? ' (suspended)' : ''}
            </span>
            <Space size="small">
              <Button
                size="small"
                onClick={() => run(p.suspended ? 'resume_project' : 'suspend_project', { project_url: p.url })}
              >
                {p.suspended ? 'Start' : 'Stop'}
              </Button>
              <Button size="small" danger onClick={() => detach(p.url)}>
                Detach
              </Button>
            </Space>
          </div>
        ))
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

      <Space style={{ marginTop: 8 }}>
        <Button onClick={() => run('resume_all', {})}>Resume all</Button>
        <Button danger onClick={() => run('suspend_all', {})}>
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
                  <Button type="primary" htmlType="submit">
                    Attach
                  </Button>
                </Form.Item>
              </Form>
            ),
          },
        ]}
      />
    </div>
  )
}
