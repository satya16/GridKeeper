import { Card, Collapse, Divider, Typography, message } from 'antd'
import { api } from '../api.js'
import { BoincBlock } from './BoincBlock.jsx'
import { FahBlock } from './FahBlock.jsx'
import { GenericBackendBlock } from './GenericBackendBlock.jsx'
import { SchedulePolicyForm, scheduleSummary } from './SchedulePolicyForm.jsx'

const KNOWN_BACKENDS = new Set(['boinc', 'fah'])

export function NodeCard({ node, backends, canWrite, onChanged }) {
  const status = node.status || {}
  // Any status key that isn't boinc/fah is a third-party plugin backend
  // (see node/grid_node/backends/base.py) -- rendered with the generic
  // fallback block instead of a bespoke component.
  const otherBackendNames = Object.keys(status).filter((name) => !KNOWN_BACKENDS.has(name))

  const handleSetGroup = async () => {
    const next = window.prompt('Group for this machine (e.g. "Lab 1", "Library"; blank to ungroup):', node.group)
    if (next === null || next === node.group) return
    try {
      await api.setNodeGroup(node.id, next)
      onChanged()
    } catch (err) {
      message.error(`Failed to set group: ${err.message}`)
    }
  }

  const handleSaveSchedule = async (policy) => {
    try {
      await api.setNodeSchedule(node.id, policy)
      onChanged()
    } catch (err) {
      message.error(`Failed to save schedule: ${err.message}`)
    }
  }

  return (
    <Card
      size="small"
      title={
        <span title={node.name}>
          <span className={`dot ${node.online ? 'online' : 'offline'}`} />
          {node.name}
        </span>
      }
      styles={{ header: { display: 'flex' }, title: { minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' } }}
      extra={<span className="muted">{node.os_name}</span>}
    >
      {canWrite ? (
        <button
          type="button"
          onClick={handleSetGroup}
          style={{
            background: 'transparent',
            border: '1px dashed var(--gk-border)',
            color: 'var(--gk-muted)',
            borderRadius: 999,
            padding: '2px 10px',
            fontSize: '0.75rem',
            cursor: 'pointer',
            marginBottom: 8,
          }}
        >
          {node.group || 'Set group…'}
        </button>
      ) : (
        node.group && (
          <span
            style={{
              display: 'inline-block',
              border: '1px solid var(--gk-border)',
              color: 'var(--gk-muted)',
              borderRadius: 999,
              padding: '2px 10px',
              fontSize: '0.75rem',
              marginBottom: 8,
            }}
          >
            {node.group}
          </span>
        )
      )}

      <BoincBlock nodeId={node.id} boinc={status.boinc} canWrite={canWrite} onChanged={onChanged} />
      {status.boinc && status.fah && <Divider style={{ margin: '8px 0' }} />}
      <FahBlock nodeId={node.id} fah={status.fah} canWrite={canWrite} onChanged={onChanged} />
      {otherBackendNames.map((name) => (
        <div key={name}>
          {(status.boinc || status.fah) && <Divider style={{ margin: '8px 0' }} />}
          <GenericBackendBlock
            nodeId={node.id}
            backendName={name}
            backendStatus={status[name]}
            actions={(backends || []).find((b) => b.name === name)?.actions}
            canWrite={canWrite}
            onChanged={onChanged}
          />
        </div>
      ))}
      {!status.boinc && !status.fah && !otherBackendNames.length && (
        <Typography.Text type="secondary">No status reported yet.</Typography.Text>
      )}

      {canWrite ? (
        <Collapse
          ghost
          size="small"
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'schedule',
              label: `Schedule: ${scheduleSummary(node.schedule)}`,
              children: <SchedulePolicyForm initialPolicy={node.schedule} submitLabel="Save schedule" onSubmit={handleSaveSchedule} />,
            },
          ]}
        />
      ) : (
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Schedule: {scheduleSummary(node.schedule)}
        </Typography.Text>
      )}
    </Card>
  )
}
