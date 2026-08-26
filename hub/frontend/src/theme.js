import { createTheme } from '@mui/material/styles'

// Corporate palette tokens -- also mirrored as --gk-* CSS custom
// properties in index.css for the app's own custom CSS/SVGs (LineChart.jsx,
// App.css's dots/progress-bars/chart-tooltip) that this theme has no reach
// into. Kept in two places for the same reason antd's ConfigProvider tokens
// used to be: MUI needs real values, not var() references.
export const PALETTE_TOKENS = {
  dark: {
    primary: '#6C93D6',
    background: '#0B0F19',
    paper: '#141A26',
    border: '#232B3D',
    text: '#E8EAED',
    textSecondary: '#94A0B3',
  },
  light: {
    primary: '#2F5DA6',
    background: '#F5F7FA',
    paper: '#FFFFFF',
    border: '#E2E5EA',
    text: '#111827',
    textSecondary: '#5B6472',
  },
}

const SEMANTIC = {
  success: '#2FA876',
  warning: '#C87F0A',
  error: '#D64550',
}

const FONT_FAMILY = '"Roboto", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'

export function createAppTheme(mode) {
  const tokens = PALETTE_TOKENS[mode]

  return createTheme({
    palette: {
      mode,
      primary: { main: tokens.primary },
      success: { main: SEMANTIC.success },
      warning: { main: SEMANTIC.warning },
      error: { main: SEMANTIC.error },
      background: { default: tokens.background, paper: tokens.paper },
      text: { primary: tokens.text, secondary: tokens.textSecondary },
      divider: tokens.border,
    },
    shape: { borderRadius: 8 },
    typography: {
      fontFamily: FONT_FAMILY,
      button: { textTransform: 'none', fontWeight: 500 },
    },
    components: {
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: { root: { textTransform: 'none' } },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            border: `1px solid ${tokens.border}`,
            backgroundImage: 'none',
            boxShadow: mode === 'dark' ? '0 1px 2px rgba(0,0,0,0.4)' : '0 1px 2px rgba(16,24,40,0.06)',
          },
        },
      },
      MuiPaper: {
        styleOverrides: { root: { backgroundImage: 'none' } },
      },
      MuiTableCell: {
        styleOverrides: { root: { borderColor: tokens.border } },
      },
      MuiChip: {
        styleOverrides: { root: { fontWeight: 500 } },
      },
    },
  })
}
