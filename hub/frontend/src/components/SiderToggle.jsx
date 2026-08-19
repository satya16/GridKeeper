import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import { Button } from 'antd'

export function SiderToggle({ collapsed, onClick }) {
  return (
    <Button
      type="text"
      onClick={onClick}
      aria-label="Toggle menu"
      icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
      style={{ fontSize: '1.1rem' }}
    />
  )
}
