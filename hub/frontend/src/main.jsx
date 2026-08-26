import { StrictMode, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { SnackbarProvider } from 'notistack'
import '@fontsource/roboto/300.css'
import '@fontsource/roboto/400.css'
import '@fontsource/roboto/500.css'
import '@fontsource/roboto/700.css'
import App from './App.jsx'
import { createAppTheme } from './theme.js'
import { SnackbarUtilsConfigurator } from './snackbar.js'
import './index.css'

const THEME_STORAGE_KEY = 'gridkeeper-theme'

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
  const muiTheme = useMemo(() => createAppTheme(themeMode), [themeMode])

  return (
    <ThemeProvider theme={muiTheme}>
      <CssBaseline />
      <SnackbarProvider maxSnack={4} anchorOrigin={{ vertical: 'top', horizontal: 'right' }}>
        <SnackbarUtilsConfigurator />
        <App themeMode={themeMode} onToggleTheme={toggleTheme} />
      </SnackbarProvider>
    </ThemeProvider>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
