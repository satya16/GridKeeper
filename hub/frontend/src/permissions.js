// Mirrors hub/app/auth.py's role rules, so the dashboard hides/disables
// actions a role can't actually perform instead of letting the user hit
// a 403 after clicking. Single source of truth for this, referenced by
// every actionable component -- see _docs/knowledge-graph/users-and-roles.md.
//
// Node-scoped writes (commands, group, schedule) only ever need to check
// "is this role viewer" -- the API already returns only in-scope nodes to
// a group_manager/machine_manager, so anything they can see, they can
// write; viewer is the only role that sees everything read-only.
export function getPermissions(role) {
  const isAdmin = role === 'admin'
  const isGroupManager = role === 'group_manager'
  const isViewer = role === 'viewer'
  return {
    canWriteNodes: !isViewer,
    canManageCredentials: isAdmin,
    canApplyCredential: !isViewer,
    canApplyCredentialToGroup: isAdmin || isGroupManager,
    canApplyCredentialToAll: isAdmin,
    canAccessDiscovery: isAdmin || isGroupManager,
    canApplyScheduleToAll: isAdmin,
    canApplyScheduleToGroup: isAdmin || isGroupManager,
  }
}
