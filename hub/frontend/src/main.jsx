import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import App from './App.jsx'
import './index.css'

const THEME_STORAGE_KEY = 'gridkeeper-theme'

// Same color tokens as index.css's --gk-* CSS variables, fed into antd's
// algorithm so its own components (Button, Card, Select, Tabs, ...) match
// rather than clashing with this app's custom CSS (App.css) and hand-
// rolled chart SVGs (LineChart.jsx), which read those same variables.
// Kept in two places (JS object here, CSS variables in index.css)
// because antd's ConfigProvider needs real token values, not var()
// references -- if the palette changes, update both.
const THEME_TOKENS = {
  dark: {
    algorithm: theme.darkAlgorithm,
    colorBgBase: '#0f1115',
    colorBgContainer: '#171a21',
    colorBorder: '#2a2e38',
    colorText: '#e6e8eb',
    colorTextSecondary: '#8a8f98',
  },
  light: {
    algorithm: theme.defaultAlgorithm,
    colorBgBase: '#f4f5f7',
    colorBgContainer: '#ffffff',
    colorBorder: '#e0e2e8',
    colorText: '#1b1e25',
    colorTextSecondary: '#666d7a',
  },
}

function Root() {
  const [themeMode, setThemeMode] = useState(() => {
    if (typeof window === 'undefined') return 'dark'
    return window.localStorage.getItem(THEME_STORAGE_KEY) === 'light' ? 'light' : 'dark'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = themeMode
    window.localStorage.setItem(THEME_STORAGE_KEY, themeMode)
  }, [themeMode])

  const toggleTheme = () => setThemeMode((m) => (m === 'dark' ? 'light' : 'dark'))
  const tokens = THEME_TOKENS[themeMode]

  const gridKeeperTheme = {
    algorithm: tokens.algorithm,
    token: {
      colorBgBase: tokens.colorBgBase,
      colorBgContainer: tokens.colorBgContainer,
      colorBorder: tokens.colorBorder,
      colorText: tokens.colorText,
      colorTextSecondary: tokens.colorTextSecondary,
      colorPrimary: '#4f8cff',
      colorSuccess: '#3ecf8e',
      colorWarning: '#f2a93c',
      colorError: '#f2545b',
      borderRadius: 8,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    },
  }

  return (
    <ConfigProvider theme={gridKeeperTheme}>
      <App themeMode={themeMode} onToggleTheme={toggleTheme} />
    </ConfigProvider>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
