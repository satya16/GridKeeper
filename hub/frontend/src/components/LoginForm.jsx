import { useState } from 'react'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { api } from '../api.js'

export function LoginForm({ onLoggedIn }) {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async ({ username, password }) => {
    setError('')
    setLoading(true)
    try {
      const { role } = await api.login(username, password)
      onLoggedIn(role)
    } catch (err) {
      setError(err.status === 401 ? 'Wrong username or password.' : `Login failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '15vh' }}>
      <Card style={{ width: 320 }}>
        <Typography.Title level={3} style={{ marginTop: 0, textAlign: 'center' }}>
          GridKeeper
        </Typography.Title>
        <Form layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="username" label="Username" rules={[{ required: true }]}>
            <Input autoFocus placeholder="Username" />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: true }]}>
            <Input.Password placeholder="Password" />
          </Form.Item>
          {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Log in
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
