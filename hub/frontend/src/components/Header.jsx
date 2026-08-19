import { Button } from 'antd'

export function Header({ onToggleSider, onLogout }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
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
      <Button onClick={onLogout}>Log out</Button>
    </div>
  )
}
