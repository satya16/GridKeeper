import { Tabs } from 'antd'
import { UsersSection } from '../components/UsersSection.jsx'
import { AuditLogSection } from '../components/AuditLogSection.jsx'

// Admin-only -- both User management and the Audit log are gated to the
// admin role on the backend (require_admin_user), so they're grouped
// under one nav entry rather than each eating its own top-level slot,
// same reasoning as Fleet's Discovery/Machines/Schedule sub-tabs.
export function AdminConsolePage({ nodes, groups, tabBarExtraContent }) {
  const items = [
    { key: 'users', label: 'Users', children: <UsersSection groups={groups} nodes={nodes} /> },
    { key: 'audit-log', label: 'Audit Log', children: <AuditLogSection /> },
  ]
  return <Tabs items={items} tabBarExtraContent={tabBarExtraContent} />
}
