import { Tabs } from 'antd'
import { DiscoverySection } from '../components/DiscoverySection.jsx'
import { FleetScheduleSection } from '../components/FleetScheduleSection.jsx'
import { NodeListSection } from '../components/NodeListSection.jsx'

export function FleetPage({ nodes, groups, onChanged }) {
  const items = [
    {
      key: 'discovery',
      label: 'Discovery',
      children: <DiscoverySection onPaired={onChanged} />,
    },
    {
      key: 'machines',
      label: 'Machines',
      children: <NodeListSection nodes={nodes} groups={groups} onChanged={onChanged} />,
    },
    {
      key: 'schedule',
      label: 'Schedule',
      children: <FleetScheduleSection groups={groups} onApplied={onChanged} />,
    },
  ]

  return <Tabs items={items} />
}
