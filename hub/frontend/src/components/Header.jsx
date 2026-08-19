import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import { Button } from 'antd'

export function Header({ siderCollapsed, onToggleSider, onLogout }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
      <Button
        type="text"
        onClick={onToggleSider}
        aria-label="Toggle menu"
        icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        style={{ fontSize: '1.1rem' }}
      />
      <Button onClick={onLogout}>Log out</Button>
    </div>
  )
}
