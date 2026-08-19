import { useEffect, useState } from 'react'
import { api, setUnauthorizedHandler } from './api.js'
import { usePolling } from './usePolling.js'
import { Header } from './components/Header.jsx'
import { LoginForm } from './components/LoginForm.jsx'
import { DiscoverySection } from './components/DiscoverySection.jsx'
import { FleetScheduleSection } from './components/FleetScheduleSection.jsx'
import { CredentialsSection } from './components/CredentialsSection.jsx'
import { NodeListSection } from './components/NodeListSection.jsx'
import { MetricsSection } from './components/MetricsSection.jsx'
import './App.css'

const NODES_REFRESH_INTERVAL_MS = 5000
const GROUPS_REFRESH_INTERVAL_MS = 5000

export default function App() {
  // null = still checking on load, so the login form doesn't flash
  // before the session check comes back.
  const [authenticated, setAuthenticated] = useState(null)

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

  return (
    <div className="app-shell">
      <Header onLogout={handleLogout} />
      <DiscoverySection onPaired={onChanged} />
      <FleetScheduleSection groups={groups || []} onApplied={onChanged} />
      <CredentialsSection nodes={nodes || []} groups={groups || []} onNodeChanged={refreshNodes} />
      <NodeListSection nodes={nodes || []} groups={groups || []} onChanged={onChanged} />
      <MetricsSection />
    </div>
  )
}
