import { useState } from 'react'
import { Alert, Button, Space, Typography } from 'antd'
import { api } from '../api.js'

export function Header() {
  const [banner, setBanner] = useState(null)

  const handleNewToken = async () => {
    const label = window.prompt('Label for this machine (optional):', '') || ''
    const group = window.prompt('Group for this machine (e.g. "Lab 1"; optional):', '') || ''
    try {
      const { token } = await api.createPairingToken(label, group)
      setBanner({ token, label, group })
    } catch (err) {
      window.alert(`Failed to create pairing token: ${err.message}`)
    }
  }

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Grid Manager
        </Typography.Title>
        <Button type="primary" onClick={handleNewToken}>
          New pairing token
        </Button>
      </div>

      {banner && (
        <Alert
          type="info"
          closable
          onClose={() => setBanner(null)}
          message={
            <span>
              Pairing token (use once, on the new machine){banner.group ? ` — group "${banner.group}"` : ''}: <code>{banner.token}</code>
              <br />
              Run: <code>grid-worker enroll --manager &lt;manager-url&gt; --token {banner.token} --name "{banner.label || 'my-machine'}"</code>
            </span>
          }
        />
      )}
    </>
  )
}
