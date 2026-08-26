import { useEffect, useState } from 'react'
import { Box, Button, Card, CardContent, CardHeader, Stack, TextField, Typography } from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'
import { PageTabBar } from '../components/PageTabBar.jsx'

const ROLE_LABELS = {
  admin: 'Admin',
  group_manager: 'Group manager',
  machine_manager: 'Machine manager',
  viewer: 'Viewer',
}

function ProfileField({ label, value }) {
  return (
    <Box sx={{ display: 'flex', gap: 2, py: 0.5 }}>
      <Typography variant="body2" color="text.secondary" sx={{ width: 140, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography variant="body2">{value}</Typography>
    </Box>
  )
}

function ProfileSection() {
  const [me, setMe] = useState(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getMe().then(setMe).catch((err) => notify.error(`Could not load profile: ${err.message}`))
  }, [])

  const handleChangePassword = async (e) => {
    e.preventDefault()
    if (!currentPassword || newPassword.length < 4) return
    setSaving(true)
    try {
      await api.changeOwnPassword(currentPassword, newPassword)
      notify.success('Password changed.')
      setCurrentPassword('')
      setNewPassword('')
    } catch (err) {
      notify.error(err.status === 401 ? 'Current password is wrong.' : `Change failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <Card sx={{ mb: 2 }}>
        <CardHeader title="Your profile" />
        <CardContent sx={{ pt: 0 }}>
          {me && (
            <Box>
              <ProfileField label="Username" value={me.username} />
              <ProfileField label="Role" value={ROLE_LABELS[me.role] || me.role} />
              {me.scope && <ProfileField label="Scope" value={me.scope} />}
              <ProfileField label="Account created" value={new Date(me.created_at).toLocaleString()} />
            </Box>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Change password" />
        <CardContent sx={{ pt: 0 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Changing your password logs out any other browser session immediately -- everyone's session
            just checks the password hash currently on your account.
          </Typography>
          <Stack component="form" direction="row" spacing={1.5} flexWrap="wrap" alignItems="flex-start" onSubmit={handleChangePassword}>
            <TextField
              type="password"
              size="small"
              label="Current password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              sx={{ width: 200 }}
            />
            <TextField
              type="password"
              size="small"
              label="New password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              sx={{ width: 200 }}
            />
            <Button type="submit" variant="contained" loading={saving}>
              Change password
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </>
  )
}

export function ProfilePage({ tabBarExtraContent }) {
  const items = [{ key: 'profile', label: 'Profile', children: <ProfileSection /> }]
  return <PageTabBar items={items} tabBarExtraContent={tabBarExtraContent} />
}
