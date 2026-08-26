import MenuIcon from '@mui/icons-material/Menu'
import MenuOpenIcon from '@mui/icons-material/MenuOpen'
import { IconButton } from '@mui/material'

export function SiderToggle({ collapsed, onClick }) {
  return (
    <IconButton onClick={onClick} aria-label="Toggle menu" size="small">
      {collapsed ? <MenuIcon fontSize="small" /> : <MenuOpenIcon fontSize="small" />}
    </IconButton>
  )
}
