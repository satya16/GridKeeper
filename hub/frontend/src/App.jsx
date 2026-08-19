import { useEffect, useState } from 'react'
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

const PAGES = [
  { key: 'fleet', label: 'Fleet' },
  { key: 'credentials', label: 'Credentials' },
  { key: 'metrics', label: 'Metrics' },
]

export default function App({ themeMode, onToggleTheme }) {
  // null = still checking on load, so the login form doesn't flash
  // before the session check comes back.
  const [authenticated, setAuthenticated] = useState(null)
  const [page, setPage] = useState('fleet')
  const [siderCollapsed, setSiderCollapsed] = useState(false)

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthenticated(false))
    api
      .checkSession()
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false))
  }, [])

  const { data: nodes, refresh: refreshNodes } = usePolling(api.listNodes, authenticated ? NODES_REFRESH_INTERVAL_MS : null)
  const { data: groups, refresh: refreshGroups } = usePolling(api.listGroups, authenticated ? GROUPS_REFRESH_INTERVAL_MS : null)

  const onChanged = () => {
    refreshNodes()
    refreshGroups()
  }

  const handleLogout = async () => {
    try {
      await api.logout()
    } finally {
      setAuthenticated(false)
    }
  }

  if (authenticated === null) return null
  if (!authenticated) return <LoginForm onLoggedIn={() => setAuthenticated(true)} />

  const selectPage = (key) => {
    setPage(key)
    // On a narrow screen the sider is a full-height overlay (see App.css) --
    // picking a page should close it, same as any mobile nav drawer. On
    // desktop this is a no-op since the sider isn't covering content there.
    if (window.innerWidth <= MOBILE_BREAKPOINT_PX) setSiderCollapsed(true)
  }

  // Every page is a Tabs component (even Credentials/Metrics, which only
  // have one tab each) so the sider toggle, theme toggle, and logout
  // button always live in the same place via tabBarExtraContent -- one
  // consistent topmost bar per page, not a separate app-wide header
  // stacked above whatever the page itself shows.
  const tabBarExtraContent = {
    left: <SiderToggle collapsed={siderCollapsed} onClick={() => setSiderCollapsed((c) => !c)} />,
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
        collapsedWidth={0}
      >
        {/* "Logo" block, same height as a standard antd header (64px) so it
            aligns with each page's own tab bar -- the standard admin-layout
            pattern (Ant Design Pro's own reference layout does exactly
            this): brand in the sider's own top-left corner, above the nav. */}
        <div className="sider-brand">
          <Typography.Title level={4} style={{ margin: 0, color: 'inherit', whiteSpace: 'nowrap' }}>
            GridKeeper
          </Typography.Title>
        </div>
        <Menu
          mode="inline"
          theme={themeMode}
          style={{ height: '100%' }}
          selectedKeys={[page]}
          items={PAGES}
          onClick={({ key }) => selectPage(key)}
        />
      </Layout.Sider>
      <Layout.Content className="app-content">
        {page === 'fleet' && (
          <FleetPage nodes={nodes || []} groups={groups || []} onChanged={onChanged} tabBarExtraContent={tabBarExtraContent} />
        )}
        {page === 'credentials' && (
          <Tabs
            tabBarExtraContent={tabBarExtraContent}
            items={[
              {
                key: 'credentials',
                label: 'Credentials',
                children: <CredentialsSection nodes={nodes || []} groups={groups || []} onNodeChanged={refreshNodes} />,
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
      </Layout.Content>
    </Layout>
  )
}
