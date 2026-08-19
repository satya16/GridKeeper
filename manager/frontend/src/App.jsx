import { api } from './api.js'
import { usePolling } from './usePolling.js'
import { Header } from './components/Header.jsx'
import { DiscoverySection } from './components/DiscoverySection.jsx'
import { FleetScheduleSection } from './components/FleetScheduleSection.jsx'
import { CredentialsSection } from './components/CredentialsSection.jsx'
import { WorkerListSection } from './components/WorkerListSection.jsx'
import { MetricsSection } from './components/MetricsSection.jsx'
import './App.css'

const WORKERS_REFRESH_INTERVAL_MS = 5000
const GROUPS_REFRESH_INTERVAL_MS = 5000

export default function App() {
  const { data: workers, refresh: refreshWorkers } = usePolling(api.listWorkers, WORKERS_REFRESH_INTERVAL_MS)
  const { data: groups, refresh: refreshGroups } = usePolling(api.listGroups, GROUPS_REFRESH_INTERVAL_MS)

  const onChanged = () => {
    refreshWorkers()
    refreshGroups()
  }

  return (
    <div className="app-shell">
      <Header />
      <DiscoverySection onPaired={onChanged} />
      <FleetScheduleSection groups={groups || []} onApplied={onChanged} />
      <CredentialsSection workers={workers || []} groups={groups || []} onWorkerChanged={refreshWorkers} />
      <WorkerListSection workers={workers || []} groups={groups || []} onChanged={onChanged} />
      <MetricsSection />
    </div>
  )
}
