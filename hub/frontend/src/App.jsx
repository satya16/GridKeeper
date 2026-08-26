import { useEffect, useState } from 'react'
import HubIcon from '@mui/icons-material/Hub'
import ShowChartIcon from '@mui/icons-material/ShowChart'
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser'
import VpnKeyIcon from '@mui/icons-material/VpnKey'
import BoltIcon from '@mui/icons-material/Bolt'
import PersonIcon from '@mui/icons-material/Person'
import { Box, Drawer, List, ListItemButton, ListItemIcon, ListItemText, Stack, Tooltip, Typography } from '@mui/material'
import { api, setUnauthorizedHandler } from './api.js'
import { usePolling } from './usePolling.js'
import { SiderToggle } from './components/SiderToggle.jsx'
import { ThemeToggle } from './components/ThemeToggle.jsx'
import { LogoutButton } from './components/LogoutButton.jsx'
import { LoginForm } from './components/LoginForm.jsx'
import { CredentialsSection } from './components/CredentialsSection.jsx'
import { MetricsSection } from './components/MetricsSection.jsx'
import { PowerSection } from './components/PowerSection.jsx'
import { PageTabBar } from './components/PageTabBar.jsx'
import { FleetPage } from './pages/FleetPage.jsx'
import { AdminConsolePage } from './pages/AdminConsolePage.jsx'
import { ProfilePage } from './pages/ProfilePage.jsx'
import { getPermissions } from './permissions.js'
import './App.css'

const NODES_REFRESH_INTERVAL_MS = 5000
const GROUPS_REFRESH_INTERVAL_MS = 5000
const BACKENDS_REFRESH_INTERVAL_MS = 15000
// Matches the media query in App.css that turns the sider into a fixed
// overlay -- MUI's Drawer only becomes a `temporary` (overlay+backdrop)
// variant when we ask for one, so this decides which variant to render.
const MOBILE_BREAKPOINT_PX = 767
// Desktop icon-rail width when the sider is collapsed but not hidden --
// mobile still collapses to fully hidden (a temporary Drawer) instead.
const SIDER_ICON_RAIL_WIDTH = 80
const SIDER_EXPANDED_WIDTH = 220

const BASE_PAGES = [
  { key: 'fleet', label: 'Fleet', icon: <HubIcon /> },
  { key: 'credentials', label: 'Credentials', icon: <VpnKeyIcon /> },
  { key: 'metrics', label: 'Metrics', icon: <ShowChartIcon /> },
  { key: 'power', label: 'Power', icon: <BoltIcon /> },
]
// Admin-only nav item -- everyone gets Fleet/Credentials/Metrics/Profile,
// but only an admin can manage the user list or see who did what. Users
// and Audit Log are both admin-only on the backend, so they're one nav
// entry with two sub-tabs rather than two separate top-level items.
const ADMIN_CONSOLE_PAGE = { key: 'admin-console', label: 'Admin Console', icon: <VerifiedUserIcon /> }
const PROFILE_PAGE = { key: 'profile', label: 'Profile', icon: <PersonIcon /> }

export default function App({ themeMode, onToggleTheme }) {
  // null = still checking on load, so the login form doesn't flash
  // before the session check comes back.
  const [authenticated, setAuthenticated] = useState(null)
  const [role, setRole] = useState(null)
  const [page, setPage] = useState('fleet')
  const [siderCollapsed, setSiderCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= MOBILE_BREAKPOINT_PX)

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthenticated(false))
    api
      .checkSession()
      .then(({ role }) => {
        setRole(role)
        setAuthenticated(true)
      })
      .catch(() => setAuthenticated(false))
  }, [])

  const pages = [...BASE_PAGES, ...(role === 'admin' ? [ADMIN_CONSOLE_PAGE] : []), PROFILE_PAGE]

  useEffect(() => {
    // Reactive, not just checked at click-time (selectPage below still does
    // that for the "close on navigate" case) -- the drawer variant needs to
    // be correct immediately if the window is resized across the breakpoint
    // while it's already open, not just on the next interaction.
    const onResize = () => setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT_PX)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const { data: nodes, refresh: refreshNodes } = usePolling(api.listNodes, authenticated ? NODES_REFRESH_INTERVAL_MS : null)
  const { data: groups, refresh: refreshGroups } = usePolling(api.listGroups, authenticated ? GROUPS_REFRESH_INTERVAL_MS : null)
  // Backend capability registry (see hub/app/api/backends.py) -- lets the
  // Fleet/Credentials pages build generic UI for a third-party backend
  // plugin without any per-backend frontend code. Polled less aggressively
  // than nodes/groups since it only changes on a node restart/upgrade.
  const { data: backends } = usePolling(api.listBackends, authenticated ? BACKENDS_REFRESH_INTERVAL_MS : null)
  const perms = getPermissions(role)

  const onChanged = () => {
    refreshNodes()
    refreshGroups()
  }

  const handleLogout = async () => {
    try {
      await api.logout()
    } finally {
      setAuthenticated(false)
      setRole(null)
    }
  }

  if (authenticated === null) return null
  if (!authenticated)
    return (
      <LoginForm
        onLoggedIn={(loggedInRole) => {
          setRole(loggedInRole)
          setAuthenticated(true)
        }}
      />
    )

  const selectPage = (key) => {
    setPage(key)
    // On a narrow screen the sider is a temporary (overlay) Drawer -- picking
    // a page should close it, same as any mobile nav drawer. On desktop
    // this is a no-op since the permanent Drawer isn't covering content.
    if (window.innerWidth <= MOBILE_BREAKPOINT_PX) setSiderCollapsed(true)
  }

  const toggleSider = () => setSiderCollapsed((c) => !c)
  const railCollapsed = siderCollapsed && !isMobile

  // Every page is a PageTabBar (even Credentials/Metrics/Power, which only
  // have one tab each) so the theme toggle and logout button always live
  // in the same place via tabBarExtraContent -- one consistent topmost
  // bar per page, not a separate app-wide header stacked above whatever
  // the page itself shows. The sider toggle itself, though, now lives
  // *inside* the sider (its own brand row) on desktop, since the sider is
  // always visible there (icon rail, never fully hidden) -- no need for
  // an external trigger. On mobile the sider can still fully disappear (a
  // temporary Drawer), so it still needs one outside itself to be
  // reopened; kept in the tab bar there, same as before.
  const tabBarExtraContent = {
    left: isMobile ? <SiderToggle collapsed={siderCollapsed} onClick={toggleSider} /> : null,
    right: (
      <Stack direction="row" spacing={0.5}>
        <ThemeToggle themeMode={themeMode} onToggle={onToggleTheme} />
        <LogoutButton onClick={handleLogout} />
      </Stack>
    ),
  }

  const drawerWidth = isMobile ? SIDER_EXPANDED_WIDTH : railCollapsed ? SIDER_ICON_RAIL_WIDTH : SIDER_EXPANDED_WIDTH

  const drawerContent = (
    <>
      {/* "Logo" block, same height as the page tab bar (64px) so it aligns
          across the sider/content boundary -- the standard admin-layout
          pattern (Ant Design Pro's own reference layout does exactly this):
          brand in the sider's own top-left corner, above the nav. Collapses
          to a "GK" monogram on desktop's icon rail rather than disappearing,
          matching the nav items below it. The toggle itself lives here too
          (not the tab bar) on desktop -- see toggleSider's definition above
          for why. */}
      <Box className={`sider-brand${railCollapsed ? ' sider-brand-collapsed' : ''}`}>
        <Typography variant="h6" sx={{ m: 0, color: 'inherit', whiteSpace: 'nowrap', fontWeight: 600 }}>
          {railCollapsed ? 'GK' : 'GridKeeper'}
        </Typography>
        {!isMobile && <SiderToggle collapsed={siderCollapsed} onClick={toggleSider} />}
      </Box>
      <List sx={{ py: 1 }}>
        {pages.map((item) => {
          const button = (
            <ListItemButton
              key={item.key}
              selected={page === item.key}
              onClick={() => selectPage(item.key)}
              sx={{
                mx: 1,
                borderRadius: 1,
                justifyContent: railCollapsed ? 'center' : 'flex-start',
                minHeight: 44,
              }}
            >
              <ListItemIcon sx={{ minWidth: railCollapsed ? 0 : 40, justifyContent: 'center' }}>{item.icon}</ListItemIcon>
              {!railCollapsed && <ListItemText primary={item.label} />}
            </ListItemButton>
          )
          return railCollapsed ? (
            <Tooltip key={item.key} title={item.label} placement="right">
              {button}
            </Tooltip>
          ) : (
            button
          )
        })}
      </List>
    </>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Drawer
        variant={isMobile ? 'temporary' : 'permanent'}
        open={isMobile ? !siderCollapsed : true}
        onClose={() => setSiderCollapsed(true)}
        ModalProps={{ keepMounted: true }}
        sx={{
          width: isMobile ? 0 : drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: isMobile ? SIDER_EXPANDED_WIDTH : drawerWidth,
            boxSizing: 'border-box',
            transition: 'width 0.2s',
            overflowX: 'hidden',
            borderRight: '1px solid var(--gk-border)',
          },
        }}
      >
        {drawerContent}
      </Drawer>
      <Box component="main" className="app-content" sx={{ flexGrow: 1, minWidth: 0 }}>
        {page === 'fleet' && (
          <FleetPage
            nodes={nodes || []}
            groups={groups || []}
            backends={backends || []}
            perms={perms}
            onChanged={onChanged}
            tabBarExtraContent={tabBarExtraContent}
          />
        )}
        {page === 'credentials' && (
          <PageTabBar
            tabBarExtraContent={tabBarExtraContent}
            items={[
              {
                key: 'credentials',
                label: 'Credentials',
                children: (
                  <CredentialsSection
                    nodes={nodes || []}
                    groups={groups || []}
                    backends={backends || []}
                    perms={perms}
                    onNodeChanged={refreshNodes}
                  />
                ),
              },
            ]}
          />
        )}
        {page === 'metrics' && (
          <PageTabBar
            tabBarExtraContent={tabBarExtraContent}
            items={[{ key: 'metrics', label: 'Metrics', children: <MetricsSection /> }]}
          />
        )}
        {page === 'power' && (
          <PageTabBar
            tabBarExtraContent={tabBarExtraContent}
            items={[{ key: 'calculator', label: 'Calculator', children: <PowerSection nodes={nodes || []} /> }]}
          />
        )}
        {page === 'admin-console' && role === 'admin' && (
          <AdminConsolePage nodes={nodes || []} groups={groups || []} tabBarExtraContent={tabBarExtraContent} />
        )}
        {page === 'profile' && <ProfilePage tabBarExtraContent={tabBarExtraContent} />}
      </Box>
    </Box>
  )
}
