import { api } from './api.js'
import { usePolling } from './usePolling.js'
import { Header } from './components/Header.jsx'
import { DiscoverySection } from './components/DiscoverySection.jsx'
import { FleetScheduleSection } from './components/FleetScheduleSection.jsx'
import { CredentialsSection } from './components/CredentialsSection.jsx'
import { NodeListSection } from './components/NodeListSection.jsx'
import { MetricsSection } from './components/MetricsSection.jsx'
import './App.css'

const NODES_REFRESH_INTERVAL_MS = 5000
const GROUPS_REFRESH_INTERVAL_MS = 5000

export default function App() {
  const { data: nodes, refresh: refreshNodes } = usePolling(api.listNodes, NODES_REFRESH_INTERVAL_MS)
  const { data: groups, refresh: refreshGroups } = usePolling(api.listGroups, GROUPS_REFRESH_INTERVAL_MS)

  const onChanged = () => {
    refreshNodes()
    refreshGroups()
  }

  return (
    <div className="app-shell">
      <Header />
      <DiscoverySection onPaired={onChanged} />
      <FleetScheduleSection groups={groups || []} onApplied={onChanged} />
      <CredentialsSection nodes={nodes || []} groups={groups || []} onNodeChanged={refreshNodes} />
      <NodeListSection nodes={nodes || []} groups={groups || []} onChanged={onChanged} />
      <MetricsSection />
    </div>
  )
}
