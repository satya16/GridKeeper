import { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, TextField, Typography } from '@mui/material'
import { api } from '../api.js'

export function LoginForm({ onLoggedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username || !password) return
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
    <Box sx={{ display: 'flex', justifyContent: 'center', pt: '15vh' }}>
      <Card sx={{ width: 320 }}>
        <CardContent>
          <Typography variant="h5" sx={{ mt: 0, mb: 3, textAlign: 'center', fontWeight: 600 }}>
            GridKeeper
          </Typography>
          <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <TextField
              autoFocus
              required
              label="Username"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              size="small"
              fullWidth
            />
            <TextField
              required
              type="password"
              label="Password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              size="small"
              fullWidth
            />
            {error && <Alert severity="error">{error}</Alert>}
            <Button type="submit" variant="contained" loading={loading} fullWidth>
              Log in
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}
