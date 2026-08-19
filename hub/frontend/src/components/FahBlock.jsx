import { Button, Checkbox, Collapse, Form, Input, InputNumber, Select, Space, Typography, message } from 'antd'
import { api } from '../api.js'

// From https://api.foldingathome.org/project/cause, minus "unspecified"
// (the client itself substitutes "any" for that) -- fetched and confirmed
// live 2026-08-18 against the same endpoint the official web-control
// frontend (fah-web-client-bastet's CommonSettings.vue) calls. Static
// here rather than fetched at runtime -- see knowledge-graph/fah-backend.md.
const FAH_CAUSES = ['any', 'alzheimers', 'cancer', 'covid-19', 'diabetes', 'huntingtons', 'influenza', 'parkinsons']

function pct(fraction) {
  return `${Math.round((fraction || 0) * 100)}%`
}

export function FahBlock({ nodeId, fah, onChanged }) {
  const [form] = Form.useForm()

  if (!fah) return null

  const slots = fah.slots || []
  const account = fah.account || { user: 'Anonymous', team: 0, cause: 'any', fold_anon: false }

  const run = async (action, payload) => {
    try {
      const result = await api.issueCommand(nodeId, 'fah', action, payload)
      if (result.status !== 'ok') message.warning(`Command finished with status "${result.status}": ${JSON.stringify(result.result)}`)
      onChanged()
    } catch (err) {
      message.error(`Command failed: ${err.message}`)
    }
  }

  const handleSave = async (values) => {
    // cause/fold_anon always have a value; user/team/passkey are only
    // sent if the admin actually typed something -- an empty field
    // shouldn't overwrite a real value with blank/zero.
    const fields = { cause: values.cause, fold_anon: !!values.fold_anon }
    if (values.user?.trim()) fields.user = values.user.trim()
    if (values.team !== null && values.team !== undefined && values.team !== '') fields.team = values.team
    if (values.passkey?.trim()) fields.passkey = values.passkey.trim()
    await run('set_config', fields)
    form.setFieldValue('passkey', '')
  }

  return (
    <div>
      <Typography.Text type="secondary" style={{ textTransform: 'uppercase', fontSize: 12, letterSpacing: '0.04em' }}>
        Folding@home
      </Typography.Text>
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

      <Space style={{ marginTop: 8 }}>
        <Button onClick={() => run('unpause_all', {})}>Resume all</Button>
        <Button danger onClick={() => run('pause_all', {})}>
          Pause all
        </Button>
      </Space>

      <Collapse
        ghost
        size="small"
        style={{ marginTop: 8 }}
        items={[
          {
            key: 'config',
            label: 'Account & cause…',
            children: (
              <Form
                form={form}
                layout="vertical"
                size="small"
                onFinish={handleSave}
                initialValues={{ cause: account.cause, fold_anon: account.fold_anon }}
              >
                <Form.Item name="cause" label="Cause">
                  <Select options={FAH_CAUSES.map((c) => ({ value: c, label: c }))} />
                </Form.Item>
                <Form.Item name="fold_anon" valuePropName="checked">
                  <Checkbox>Fold anonymously (no account needed)</Checkbox>
                </Form.Item>
                <Form.Item name="user" label="Username">
                  <Input placeholder={account.user} />
                </Form.Item>
                <Form.Item name="team" label="Team number">
                  <InputNumber min={0} style={{ width: '100%' }} placeholder={String(account.team)} />
                </Form.Item>
                <Form.Item name="passkey" label="Passkey">
                  <Input.Password placeholder="from your F@H account page (optional)" />
                </Form.Item>
                <Form.Item>
                  <Button type="primary" htmlType="submit">
                    Save
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
