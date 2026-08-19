import { Tabs } from 'antd'
import { DiscoverySection } from '../components/DiscoverySection.jsx'
import { FleetScheduleSection } from '../components/FleetScheduleSection.jsx'
import { NodeListSection } from '../components/NodeListSection.jsx'

export function FleetPage({ nodes, groups, onChanged, tabBarExtraContent }) {
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

  // Puts the sider toggle, theme toggle, and logout button directly in
  // the tab bar row itself (antd's own primitive for this -- Tabs'
  // tabBarExtraContent, {left, right} -- rather than a separate header
  // bar above the tabs).
  return <Tabs items={items} tabBarExtraContent={tabBarExtraContent} />
}
