import { Card, Collapse, Divider, Typography, message } from 'antd'
import { api } from '../api.js'
import { BoincBlock } from './BoincBlock.jsx'
import { FahBlock } from './FahBlock.jsx'
import { SchedulePolicyForm, scheduleSummary } from './SchedulePolicyForm.jsx'

export function WorkerCard({ worker, onChanged }) {
  const status = worker.status || {}

  const handleSetGroup = async () => {
    const next = window.prompt('Group for this machine (e.g. "Lab 1", "Library"; blank to ungroup):', worker.group)
    if (next === null || next === worker.group) return
    try {
      await api.setWorkerGroup(worker.id, next)
      onChanged()
    } catch (err) {
      message.error(`Failed to set group: ${err.message}`)
    }
  }

  const handleSaveSchedule = async (policy) => {
    try {
      await api.setWorkerSchedule(worker.id, policy)
      onChanged()
    } catch (err) {
      message.error(`Failed to save schedule: ${err.message}`)
    }
  }

  return (
    <Card
      size="small"
      title={
        <span title={worker.name}>
          <span className={`dot ${worker.online ? 'online' : 'offline'}`} />
          {worker.name}
        </span>
      }
      styles={{ header: { display: 'flex' }, title: { minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' } }}
      extra={<span className="muted">{worker.os_name}</span>}
    >
      <button
        type="button"
        onClick={handleSetGroup}
        style={{
          background: 'transparent',
          border: '1px dashed #2a2e38',
          color: '#8a8f98',
          borderRadius: 999,
          padding: '2px 10px',
          fontSize: '0.75rem',
          cursor: 'pointer',
          marginBottom: 8,
        }}
      >
        {worker.group || 'Set group…'}
      </button>

      <BoincBlock workerId={worker.id} boinc={status.boinc} onChanged={onChanged} />
      {status.boinc && status.fah && <Divider style={{ margin: '8px 0' }} />}
      <FahBlock workerId={worker.id} fah={status.fah} onChanged={onChanged} />
      {!status.boinc && !status.fah && <Typography.Text type="secondary">No status reported yet.</Typography.Text>}

      <Collapse
        ghost
        size="small"
        style={{ marginTop: 8 }}
        items={[
          {
            key: 'schedule',
            label: `Schedule: ${scheduleSummary(worker.schedule)}`,
            children: <SchedulePolicyForm initialPolicy={worker.schedule} submitLabel="Save schedule" onSubmit={handleSaveSchedule} />,
          },
        ]}
      />
    </Card>
  )
}
