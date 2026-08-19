import { Button, Typography } from 'antd'

export function Header({ onToggleSider, onLogout }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          type="button"
          onClick={onToggleSider}
          aria-label="Toggle menu"
          style={{
            background: 'transparent',
            border: 'none',
            color: 'inherit',
            fontSize: '1.3rem',
            lineHeight: 1,
            cursor: 'pointer',
            padding: '4px 6px',
          }}
        >
          ☰
        </button>
        <Typography.Title level={3} style={{ margin: 0 }}>
          GridKeeper
        </Typography.Title>
      </div>
      <Button onClick={onLogout}>Log out</Button>
    </div>
  )
}
