import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'

export function ThemeToggle({ themeMode, onToggle }) {
  const isDark = themeMode === 'dark'
  return (
    <Tooltip title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
      <Button
        type="text"
        onClick={onToggle}
        aria-label="Toggle color theme"
        icon={isDark ? <SunOutlined /> : <MoonOutlined />}
      />
    </Tooltip>
  )
}
