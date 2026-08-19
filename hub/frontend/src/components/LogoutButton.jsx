import { LogoutOutlined } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'

export function LogoutButton({ onClick }) {
  return (
    <Tooltip title="Log out">
      <Button onClick={onClick} aria-label="Log out" icon={<LogoutOutlined />} />
    </Tooltip>
  )
}
