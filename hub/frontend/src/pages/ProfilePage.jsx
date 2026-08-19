import { useEffect, useState } from 'react'
import { Button, Card, Descriptions, Form, Input, Tabs, Typography, message } from 'antd'
import { api } from '../api.js'

const ROLE_LABELS = {
  admin: 'Admin',
  group_manager: 'Group manager',
  machine_manager: 'Machine manager',
  viewer: 'Viewer',
}

function ProfileSection() {
  const [me, setMe] = useState(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getMe().then(setMe).catch((err) => message.error(`Could not load profile: ${err.message}`))
  }, [])

  const handleChangePassword = async ({ current_password, new_password }) => {
    setSaving(true)
    try {
      await api.changeOwnPassword(current_password, new_password)
      message.success('Password changed.')
      form.resetFields()
    } catch (err) {
      message.error(err.status === 401 ? 'Current password is wrong.' : `Change failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Card title="Your profile" style={{ marginBottom: 16 }}>
        {me && (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Username">{me.username}</Descriptions.Item>
            <Descriptions.Item label="Role">{ROLE_LABELS[me.role] || me.role}</Descriptions.Item>
            {me.scope && <Descriptions.Item label="Scope">{me.scope}</Descriptions.Item>}
            <Descriptions.Item label="Account created">{new Date(me.created_at).toLocaleString()}</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Card title="Change password">
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          Changing your password logs out any other browser session immediately -- everyone's session
          just checks the password hash currently on your account.
        </Typography.Paragraph>
        <Form form={form} layout="inline" onFinish={handleChangePassword}>
          <Form.Item name="current_password" rules={[{ required: true }]}>
            <Input.Password placeholder="Current password" style={{ width: 200 }} />
          </Form.Item>
          <Form.Item name="new_password" rules={[{ required: true, min: 4 }]}>
            <Input.Password placeholder="New password" style={{ width: 200 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={saving}>
              Change password
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </>
  )
}

export function ProfilePage({ tabBarExtraContent }) {
  const items = [{ key: 'profile', label: 'Profile', children: <ProfileSection /> }]
  return <Tabs items={items} tabBarExtraContent={tabBarExtraContent} />
}
