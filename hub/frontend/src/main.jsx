import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import App from './App.jsx'
import './index.css'

// Same color tokens as the previous dashboard.css (--bg/--card/--border/
// --text/--muted/--accent), fed into antd's dark algorithm so its
// components (Button, Card, Select, ...) match rather than clashing with
// the hand-rolled chart SVGs, which reuse these exact hexes too.
const gridHubTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorBgBase: '#0f1115',
    colorBgContainer: '#171a21',
    colorBorder: '#2a2e38',
    colorText: '#e6e8eb',
    colorTextSecondary: '#8a8f98',
    colorPrimary: '#4f8cff',
    colorSuccess: '#3ecf8e',
    colorWarning: '#f2a93c',
    colorError: '#f2545b',
    borderRadius: 8,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider theme={gridHubTheme}>
      <App />
    </ConfigProvider>
  </StrictMode>,
)
