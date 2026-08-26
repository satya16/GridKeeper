import LogoutIcon from '@mui/icons-material/Logout'
import { IconButton, Tooltip } from '@mui/material'

export function LogoutButton({ onClick }) {
  return (
    <Tooltip title="Log out">
      <IconButton onClick={onClick} aria-label="Log out" size="small">
        <LogoutIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  )
}
