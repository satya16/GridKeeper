import { Tabs } from 'antd'
import { DiscoverySection } from '../components/DiscoverySection.jsx'
import { FleetScheduleSection } from '../components/FleetScheduleSection.jsx'
import { NodeListSection } from '../components/NodeListSection.jsx'

export function FleetPage({ nodes, groups, perms, onChanged, tabBarExtraContent }) {
  const items = [
    // Discovery/pairing is admin-or-group_manager only, same as the
    // backend (see auth.py's _require_discovery_access equivalent) --
    // hidden entirely rather than shown-then-403ing, since even the
    // read (list discovered nodes) is blocked for machine_manager/viewer.
    ...(perms.canAccessDiscovery
      ? [{ key: 'discovery', label: 'Discovery', children: <DiscoverySection onPaired={onChanged} /> }]
      : []),
    {
      key: 'machines',
      label: 'Machines',
      children: <NodeListSection nodes={nodes} groups={groups} canWrite={perms.canWriteNodes} onChanged={onChanged} />,
    },
    // Fleet-wide schedule apply (apply-all/apply-group) has nothing for
    // machine_manager (no group-wide action) or viewer (no writes at
    // all) to do here -- per-node schedule is still editable from their
    // own Machines tab card.
    ...(perms.canApplyScheduleToGroup
      ? [
          {
            key: 'schedule',
            label: 'Schedule',
            children: (
              <FleetScheduleSection groups={groups} canApplyToAll={perms.canApplyScheduleToAll} onApplied={onChanged} />
            ),
          },
        ]
      : []),
  ]

  // Puts the sider toggle, theme toggle, and logout button directly in
  // the tab bar row itself (antd's own primitive for this -- Tabs'
  // tabBarExtraContent, {left, right} -- rather than a separate header
  // bar above the tabs).
  return <Tabs items={items} tabBarExtraContent={tabBarExtraContent} />
}
