import { useState } from 'react'
import {
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
} from '@mui/material'
import { api } from '../api.js'
import { notify } from '../snackbar.js'
import { usePolling } from '../usePolling.js'

const USERS_REFRESH_INTERVAL_MS = 15000

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin', full: 'Admin — full access to everything' },
  { value: 'group_manager', label: 'Group manager', full: 'Group manager — view/edit their own group(s)' },
  { value: 'machine_manager', label: 'Machine manager', full: 'Machine manager — view/edit their own machine(s)' },
  { value: 'viewer', label: 'Viewer', full: 'Viewer — read-only, everything' },
]

const ROLE_COLORS = { admin: 'error', group_manager: 'info', machine_manager: 'success', viewer: 'default' }

// Scope is a plain comma-separated list on the wire (see hub/app/db.py's
// User.scope docstring) -- group names for group_manager, node ids for
// machine_manager. The dashboard offers a friendlier multi-select over
// known groups/node names, but still round-trips through that same flat
// string.
function ScopeField({ role, groups, nodes, value, onChange }) {
  if (role === 'group_manager') {
    const selected = value ? value.split(',').filter(Boolean) : []
    return (
      <Autocomplete
        multiple
        freeSolo
        size="small"
        options={groups}
        value={selected}
        onChange={(_, vals) => onChange(vals.join(','))}
        sx={{ minWidth: 240 }}
        renderInput={(params) => <TextField {...params} placeholder="Group(s) this user manages" />}
      />
    )
  }
  if (role === 'machine_manager') {
    const selectedIds = value ? value.split(',').filter(Boolean) : []
    const selectedNodes = nodes.filter((n) => selectedIds.includes(n.id))
    return (
      <Autocomplete
        multiple
        size="small"
        options={nodes}
        getOptionLabel={(n) => n.name}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        value={selectedNodes}
        onChange={(_, vals) => onChange(vals.map((n) => n.id).join(','))}
        sx={{ minWidth: 240 }}
        renderInput={(params) => <TextField {...params} placeholder="Machine(s) this user manages" />}
      />
    )
  }
  return null
}

function EditUserModal({ user, groups, nodes, onClose, onSaved }) {
  const [role, setRole] = useState(user.role)
  const [scope, setScope] = useState(user.scope)
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)

  const handleOk = async () => {
    if (newPassword && newPassword.length < 4) return
    setSaving(true)
    try {
      const changes = { role, scope: role === 'admin' || role === 'viewer' ? '' : scope }
      if (newPassword) changes.password = newPassword
      await api.updateUser(user.id, changes)
      notify.success(`Updated '${user.username}'.`)
      onSaved()
    } catch (err) {
      notify.error(`Update failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Edit {user.username}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField select size="small" label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLE_OPTIONS.map((r) => (
              <MenuItem key={r.value} value={r.value}>
                {r.full}
              </MenuItem>
            ))}
          </TextField>
          {(role === 'group_manager' || role === 'machine_manager') && (
            <ScopeField role={role} groups={groups} nodes={nodes} value={scope} onChange={setScope} />
          )}
          <TextField
            type="password"
            size="small"
            label="Reset password (optional)"
            placeholder="Leave blank to keep current password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            error={newPassword.length > 0 && newPassword.length < 4}
            helperText={newPassword.length > 0 && newPassword.length < 4 ? 'At least 4 characters' : ' '}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleOk} loading={saving}>
          OK
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export function UsersSection({ groups, nodes }) {
  const { data: users, status, refresh } = usePolling(api.listUsers, USERS_REFRESH_INTERVAL_MS)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [createRole, setCreateRole] = useState('viewer')
  const [createScope, setCreateScope] = useState('')
  const [editing, setEditing] = useState(null)

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!username.trim() || password.length < 4) return
    try {
      const scope = createRole === 'admin' || createRole === 'viewer' ? '' : createScope
      await api.createUser(username.trim(), password, createRole, scope)
      notify.success(`Created '${username.trim()}'.`)
      setUsername('')
      setPassword('')
      setCreateRole('viewer')
      setCreateScope('')
      refresh()
    } catch (err) {
      notify.error(`Create failed: ${err.status === 409 ? 'that username is already taken.' : err.message}`)
    }
  }

  const handleDelete = async (user) => {
    if (!window.confirm(`Delete user '${user.username}'? This can't be undone.`)) return
    try {
      await api.deleteUser(user.id)
      refresh()
    } catch (err) {
      notify.error(`Delete failed: ${err.message}`)
    }
  }

  return (
    <Card>
      <CardHeader title="Users" action={<span className="muted">{status}</span>} />
      <CardContent sx={{ pt: 0 }}>
        <TableContainer sx={{ mb: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Username</TableCell>
                <TableCell>Role</TableCell>
                <TableCell>Scope</TableCell>
                <TableCell>Created</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {(users || []).map((user) => (
                <TableRow key={user.id}>
                  <TableCell>{user.username}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      color={ROLE_COLORS[user.role]}
                      label={ROLE_OPTIONS.find((r) => r.value === user.role)?.label || user.role}
                    />
                  </TableCell>
                  <TableCell>{user.scope || <span className="muted">—</span>}</TableCell>
                  <TableCell>{new Date(user.created_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1}>
                      <Button size="small" variant="outlined" onClick={() => setEditing(user)}>
                        Edit
                      </Button>
                      <Button size="small" variant="outlined" color="error" onClick={() => handleDelete(user)}>
                        Delete
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <Box component="form" onSubmit={handleCreate}>
          <Stack direction="row" spacing={1.5} flexWrap="wrap" alignItems="flex-start" useFlexGap>
            <TextField
              size="small"
              placeholder="Username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              sx={{ width: 160 }}
            />
            <TextField
              type="password"
              size="small"
              placeholder="Password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              sx={{ width: 160 }}
            />
            <TextField select size="small" value={createRole} onChange={(e) => setCreateRole(e.target.value)} sx={{ width: 200 }}>
              {ROLE_OPTIONS.map((r) => (
                <MenuItem key={r.value} value={r.value}>
                  {r.full}
                </MenuItem>
              ))}
            </TextField>
            {(createRole === 'group_manager' || createRole === 'machine_manager') && (
              <ScopeField role={createRole} groups={groups} nodes={nodes} value={createScope} onChange={setCreateScope} />
            )}
            <Button type="submit" variant="contained">
              Add
            </Button>
          </Stack>
        </Box>
      </CardContent>

      {editing && (
        <EditUserModal
          user={editing}
          groups={groups}
          nodes={nodes}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            refresh()
          }}
        />
      )}
    </Card>
  )
}
