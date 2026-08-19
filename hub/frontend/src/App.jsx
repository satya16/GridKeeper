import { useEffect, useState } from 'react'
import { ClusterOutlined, KeyOutlined, LineChartOutlined, SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons'
import { Layout, Menu, Space, Tabs, Typography } from 'antd'
import { api, setUnauthorizedHandler } from './api.js'
import { usePolling } from './usePolling.js'
import { SiderToggle } from './components/SiderToggle.jsx'
import { ThemeToggle } from './components/ThemeToggle.jsx'
import { LogoutButton } from './components/LogoutButton.jsx'
import { LoginForm } from './components/LoginForm.jsx'
import { CredentialsSection } from './components/CredentialsSection.jsx'
import { MetricsSection } from './components/MetricsSection.jsx'
import { FleetPage } from './pages/FleetPage.jsx'
import { AdminConsolePage } from './pages/AdminConsolePage.jsx'
import { ProfilePage } from './pages/ProfilePage.jsx'
import { getPermissions } from './permissions.js'
import './App.css'

const NODES_REFRESH_INTERVAL_MS = 5000
const GROUPS_REFRESH_INTERVAL_MS = 5000
// Matches the media query in App.css that turns the sider into a fixed
// overlay -- antd's Layout.Sider only auto-*shrinks* at its `breakpoint`
// prop, it doesn't become an overlay on its own (confirmed by reading
// node_modules/antd/es/layout/style/sider.js: it's `position: relative`
// unconditionally), so opening it on a narrow screen without this would
// just push page content off-screen instead of floating over it.
const MOBILE_BREAKPOINT_PX = 767
// antd's own default icon-rail width when a Sider is collapsed but not
// hidden -- used on desktop; mobile still collapses to 0 (fully hidden,
// replaced by the overlay+backdrop) since a permanent icon rail eating
// screen width makes less sense on a phone.
const SIDER_ICON_RAIL_WIDTH = 80

const BASE_PAGES = [
  { key: 'fleet', label: 'Fleet', icon: <ClusterOutlined /> },
  { key: 'credentials', label: 'Credentials', icon: <KeyOutlined /> },
  { key: 'metrics', label: 'Metrics', icon: <LineChartOutlined /> },
]
// Admin-only nav item -- everyone gets Fleet/Credentials/Metrics/Profile,
// but only an admin can manage the user list or see who did what. Users
// and Audit Log are both admin-only on the backend, so they're one nav
// entry with two sub-tabs rather than two separate top-level items.
const ADMIN_CONSOLE_PAGE = { key: 'admin-console', label: 'Admin Console', icon: <SafetyCertificateOutlined /> }
const PROFILE_PAGE = { key: 'profile', label: 'Profile', icon: <UserOutlined /> }

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
    // that for the "close on navigate" case) -- collapsedWidth needs to be
    // correct immediately if the window is resized across the breakpoint
    // while the sider's already open, not just on the next interaction.
    const onResize = () => setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT_PX)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const { data: nodes, refresh: refreshNodes } = usePolling(api.listNodes, authenticated ? NODES_REFRESH_INTERVAL_MS : null)
  const { data: groups, refresh: refreshGroups } = usePolling(api.listGroups, authenticated ? GROUPS_REFRESH_INTERVAL_MS : null)
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
    // On a narrow screen the sider is a full-height overlay (see App.css) --
    // picking a page should close it, same as any mobile nav drawer. On
    // desktop this is a no-op since the sider isn't covering content there.
    if (window.innerWidth <= MOBILE_BREAKPOINT_PX) setSiderCollapsed(true)
  }

  const toggleSider = () => setSiderCollapsed((c) => !c)

  // Every page is a Tabs component (even Credentials/Metrics, which only
  // have one tab each) so the theme toggle and logout button always live
  // in the same place via tabBarExtraContent -- one consistent topmost
  // bar per page, not a separate app-wide header stacked above whatever
  // the page itself shows. The sider toggle itself, though, now lives
  // *inside* the sider (its own brand row) on desktop, since the sider is
  // always visible there (icon rail, never fully hidden) -- no need for
  // an external trigger. On mobile the sider can still fully disappear
  // (collapsedWidth 0, see below), so it still needs one outside itself
  // to be reopened; kept in the tab bar there, same as before.
  const tabBarExtraContent = {
    left: isMobile ? <SiderToggle collapsed={siderCollapsed} onClick={toggleSider} /> : null,
    right: (
      <Space size="small">
        <ThemeToggle themeMode={themeMode} onToggle={onToggleTheme} />
        <LogoutButton onClick={handleLogout} />
      </Space>
    ),
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {!siderCollapsed && <div className="sider-backdrop" onClick={() => setSiderCollapsed(true)} />}
      <Layout.Sider
        theme={themeMode}
        collapsible
        collapsed={siderCollapsed}
        onCollapse={setSiderCollapsed}
        trigger={null}
        breakpoint="lg"
        collapsedWidth={isMobile ? 0 : SIDER_ICON_RAIL_WIDTH}
      >
        {/* "Logo" block, same height as a standard antd header (64px) so it
            aligns with each page's own tab bar -- the standard admin-layout
            pattern (Ant Design Pro's own reference layout does exactly
            this): brand in the sider's own top-left corner, above the nav.
            Collapses to a "GK" monogram on desktop's icon rail rather than
            disappearing, matching the nav items below it (full label -> icon
            + hover tooltip, not label -> nothing). The toggle itself lives
            here too (not the tab bar) on desktop -- see toggleSider's
            definition above for why. */}
        <div className={`sider-brand${siderCollapsed && !isMobile ? ' sider-brand-collapsed' : ''}`}>
          <Typography.Title level={4} style={{ margin: 0, color: 'inherit', whiteSpace: 'nowrap' }}>
            {siderCollapsed && !isMobile ? 'GK' : 'GridKeeper'}
          </Typography.Title>
          {!isMobile && <SiderToggle collapsed={siderCollapsed} onClick={toggleSider} />}
        </div>
        <Menu
          mode="inline"
          theme={themeMode}
          inlineCollapsed={siderCollapsed && !isMobile}
          style={{ height: '100%' }}
          selectedKeys={[page]}
          items={pages}
          onClick={({ key }) => selectPage(key)}
        />
      </Layout.Sider>
      <Layout.Content className="app-content">
        {page === 'fleet' && (
          <FleetPage nodes={nodes || []} groups={groups || []} perms={perms} onChanged={onChanged} tabBarExtraContent={tabBarExtraContent} />
        )}
        {page === 'credentials' && (
          <Tabs
            tabBarExtraContent={tabBarExtraContent}
            items={[
              {
                key: 'credentials',
                label: 'Credentials',
                children: (
                  <CredentialsSection nodes={nodes || []} groups={groups || []} perms={perms} onNodeChanged={refreshNodes} />
                ),
              },
            ]}
          />
        )}
        {page === 'metrics' && (
          <Tabs
            tabBarExtraContent={tabBarExtraContent}
            items={[{ key: 'metrics', label: 'Metrics', children: <MetricsSection /> }]}
          />
        )}
        {page === 'admin-console' && role === 'admin' && (
          <AdminConsolePage nodes={nodes || []} groups={groups || []} tabBarExtraContent={tabBarExtraContent} />
        )}
        {page === 'profile' && <ProfilePage tabBarExtraContent={tabBarExtraContent} />}
      </Layout.Content>
    </Layout>
  )
}
