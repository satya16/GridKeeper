import { useEffect, useState } from 'react'
import { Button, Card, Checkbox, Input, InputNumber, Select, Space, Statistic, Table, Typography } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'

const POWER_REFRESH_INTERVAL_MS = 7000
const COST_STORAGE_KEY = 'gridkeeper.costPerKwh'
const DEFAULT_COST_PER_KWH = 0.15
const WHATIF_ROWS_KEY = 'gridkeeper.whatIfRows'
const WHATIF_EXCLUDED_KEY = 'gridkeeper.whatIfExcludedNodeIds'
const DEFAULT_HYPOTHETICAL_WATTS = 100
const CURRENCY_CODE_KEY = 'gridkeeper.currencyCode'
const CUSTOM_CURRENCY_SYMBOL_KEY = 'gridkeeper.customCurrencySymbol'
const DEFAULT_CURRENCY_CODE = 'USD'
const OTHER_CURRENCY = 'OTHER'

// Top 5 by how widely they'd apply to this app's actual deployments, not
// the full ~180-code ISO-4217 list -- this app has no other i18n
// infrastructure, and a long list is exactly the "cumbersome to find
// yours" problem a dropdown is supposed to solve. Anything else goes
// through the free-text "Other" escape hatch below.
const CURRENCIES = [
  { code: 'USD', symbol: '$', label: 'US Dollar' },
  { code: 'EUR', symbol: '€', label: 'Euro' },
  { code: 'GBP', symbol: '£', label: 'British Pound' },
  { code: 'INR', symbol: '₹', label: 'Indian Rupee' },
  { code: 'JPY', symbol: '¥', label: 'Japanese Yen' },
]

const CURRENCY_OPTIONS = [
  ...CURRENCIES.map((c) => ({ value: c.code, label: `${c.symbol} ${c.code} -- ${c.label}` })),
  { value: OTHER_CURRENCY, label: 'Other (custom symbol)' },
]

function loadStoredCurrencyCode() {
  const raw = localStorage.getItem(CURRENCY_CODE_KEY)
  if (raw === OTHER_CURRENCY || CURRENCIES.some((c) => c.code === raw)) return raw
  return DEFAULT_CURRENCY_CODE
}

function loadStoredCustomSymbol() {
  return localStorage.getItem(CUSTOM_CURRENCY_SYMBOL_KEY) || ''
}

// No backend user-preferences mechanism exists in this codebase (see
// hub/app/api/users.py) -- localStorage is the proportionate choice for
// one numeric per-browser preference like this, not worth a new
// table+endpoint for.
function loadStoredCost() {
  const raw = localStorage.getItem(COST_STORAGE_KEY)
  const parsed = raw === null ? NaN : Number(raw)
  return Number.isFinite(parsed) ? parsed : DEFAULT_COST_PER_KWH
}

function loadStoredRows() {
  try {
    const parsed = JSON.parse(localStorage.getItem(WHATIF_ROWS_KEY))
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function loadStoredExcluded() {
  try {
    const parsed = JSON.parse(localStorage.getItem(WHATIF_EXCLUDED_KEY))
    return new Set(Array.isArray(parsed) ? parsed : [])
  } catch {
    return new Set()
  }
}

function projectFrom(totalWatts, costPerKwh) {
  const totalKw = totalWatts / 1000
  return PROJECTIONS.map((p) => {
    const kwh = totalKw * p.hours
    return { ...p, kwh, cost: kwh * costPerKwh }
  })
}

const PROJECTIONS = [
  { key: 'daily', label: 'Daily', hours: 24 },
  { key: 'weekly', label: 'Weekly', hours: 24 * 7 },
  { key: 'monthly', label: 'Monthly (~30d)', hours: 24 * 30 },
]

export function PowerSection({ nodes }) {
  const { data, status } = usePolling(api.getMetrics, POWER_REFRESH_INTERVAL_MS)
  const metricsData = data || {}
  const [costPerKwh, setCostPerKwh] = useState(loadStoredCost)
  const [currencyCode, setCurrencyCode] = useState(loadStoredCurrencyCode)
  const [customSymbol, setCustomSymbol] = useState(loadStoredCustomSymbol)
  const [whatIfRows, setWhatIfRows] = useState(loadStoredRows)
  const [excludedNodeIds, setExcludedNodeIds] = useState(loadStoredExcluded)

  const currencySymbol =
    currencyCode === OTHER_CURRENCY
      ? customSymbol || '?'
      : CURRENCIES.find((c) => c.code === currencyCode)?.symbol || '$'

  useEffect(() => {
    localStorage.setItem(COST_STORAGE_KEY, String(costPerKwh))
  }, [costPerKwh])

  useEffect(() => {
    localStorage.setItem(CURRENCY_CODE_KEY, currencyCode)
  }, [currencyCode])

  useEffect(() => {
    localStorage.setItem(CUSTOM_CURRENCY_SYMBOL_KEY, customSymbol)
  }, [customSymbol])

  useEffect(() => {
    localStorage.setItem(WHATIF_ROWS_KEY, JSON.stringify(whatIfRows))
  }, [whatIfRows])

  useEffect(() => {
    localStorage.setItem(WHATIF_EXCLUDED_KEY, JSON.stringify([...excludedNodeIds]))
  }, [excludedNodeIds])

  // Only online nodes with a recent estimated_watts point count towards
  // "current usage" -- an offline node's series just stops updating, so
  // its last-known point would otherwise linger and overstate the total.
  const rows = (nodes || [])
    .filter((n) => n.online)
    .map((n) => {
      const points = metricsData[n.id]?.points || []
      const latest = points[points.length - 1]
      const watts = latest?.estimated_watts
      return { key: n.id, name: n.name, watts: typeof watts === 'number' ? watts : null }
    })
    .filter((r) => r.watts !== null)

  const totalWatts = rows.reduce((sum, r) => sum + r.watts, 0)
  const projections = projectFrom(totalWatts, costPerKwh)

  function toggleNodeExcluded(nodeId) {
    setExcludedNodeIds((prev) => {
      const next = new Set(prev)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }

  function addWhatIfRow() {
    const id = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : String(Date.now())
    setWhatIfRows((prev) => [...prev, { id, name: `Machine ${prev.length + 1}`, watts: DEFAULT_HYPOTHETICAL_WATTS }])
  }

  function updateWhatIfRow(id, patch) {
    setWhatIfRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  function removeWhatIfRow(id) {
    setWhatIfRows((prev) => prev.filter((r) => r.id !== id))
  }

  // A node dropped from the fleet since these ids were stored just falls
  // out of `rows` on its own -- nothing to reconcile here.
  const whatIfRealWatts = rows
    .filter((r) => !excludedNodeIds.has(r.key))
    .reduce((sum, r) => sum + r.watts, 0)
  const whatIfHypotheticalWatts = whatIfRows.reduce((sum, r) => sum + (Number(r.watts) || 0), 0)
  const whatIfTotalWatts = whatIfRealWatts + whatIfHypotheticalWatts
  const whatIfProjections = projectFrom(whatIfTotalWatts, costPerKwh)

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="Power calculator" extra={<span className="muted">{status}</span>}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space align="center" wrap>
            <span>Cost per kWh</span>
            <Select value={currencyCode} onChange={setCurrencyCode} options={CURRENCY_OPTIONS} style={{ width: 220 }} />
            {currencyCode === OTHER_CURRENCY && (
              <Input
                value={customSymbol}
                onChange={(e) => setCustomSymbol(e.target.value)}
                placeholder="Symbol, e.g. kr"
                style={{ width: 100 }}
              />
            )}
            <InputNumber
              min={0}
              step={0.01}
              precision={2}
              prefix={currencySymbol}
              value={costPerKwh}
              onChange={(v) => setCostPerKwh(typeof v === 'number' ? v : 0)}
            />
          </Space>

          <Statistic
            title={`Current estimated draw (${rows.length} online node${rows.length === 1 ? '' : 's'} reporting)`}
            value={totalWatts}
            suffix="W"
            precision={1}
          />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
            {projections.map((p) => (
              <Card key={p.key} size="small" type="inner" title={p.label}>
                <Statistic value={p.cost} prefix={currencySymbol} precision={2} />
                <div className="muted">{p.kwh.toFixed(2)} kWh</div>
              </Card>
            ))}
          </div>

          <Typography.Paragraph className="muted" style={{ marginBottom: 0 }}>
            Rough whole-system estimate from CPU load only (each node's configured idle/max wattage, linearly scaled
            by cpu_percent) -- not a measured reading. Real draw (GPU, disk, PSU losses) will differ; tune a node's{' '}
            <code>idle_watts</code>/<code>max_watts</code> in its config for a better fit.
          </Typography.Paragraph>
        </Space>
      </Card>

      <Card title="Per-node breakdown" size="small">
        {rows.length ? (
          <Table
            size="small"
            pagination={false}
            dataSource={rows}
            columns={[
              { title: 'Node', dataIndex: 'name', key: 'name' },
              { title: 'Estimated draw', dataIndex: 'watts', key: 'watts', render: (w) => `${w.toFixed(1)} W` },
            ]}
          />
        ) : (
          <p className="muted">No online nodes reporting power estimates yet.</p>
        )}
      </Card>

      <Card title="What-if scenario">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Paragraph className="muted" style={{ marginBottom: 0 }}>
            Uncheck a real node to see the projection without it, or add a hypothetical machine with a flat wattage
            guess -- it has no live CPU usage to scale from, so unlike real nodes above this is just a number you
            supply (e.g. from the machine's PSU rating).
          </Typography.Paragraph>

          {rows.length > 0 && (
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <Typography.Text strong>Real nodes</Typography.Text>
              {rows.map((r) => (
                <div key={r.key}>
                  <Checkbox checked={!excludedNodeIds.has(r.key)} onChange={() => toggleNodeExcluded(r.key)}>
                    {r.name} <span className="muted">({r.watts.toFixed(1)} W)</span>
                  </Checkbox>
                </div>
              ))}
            </Space>
          )}

          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Typography.Text strong>Hypothetical machines</Typography.Text>
            {whatIfRows.map((r) => (
              <Space key={r.id} align="center">
                <Input
                  value={r.name}
                  onChange={(e) => updateWhatIfRow(r.id, { name: e.target.value })}
                  style={{ width: 200 }}
                  placeholder="Machine name"
                />
                <InputNumber
                  min={0}
                  step={5}
                  suffix="W"
                  value={r.watts}
                  onChange={(v) => updateWhatIfRow(r.id, { watts: typeof v === 'number' ? v : 0 })}
                />
                <Button icon={<DeleteOutlined />} onClick={() => removeWhatIfRow(r.id)} aria-label="Remove machine" />
              </Space>
            ))}
            <Button icon={<PlusOutlined />} onClick={addWhatIfRow}>
              Add machine
            </Button>
          </Space>

          <Statistic title="What-if total draw" value={whatIfTotalWatts} suffix="W" precision={1} />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
            {whatIfProjections.map((p) => (
              <Card key={p.key} size="small" type="inner" title={p.label}>
                <Statistic value={p.cost} prefix={currencySymbol} precision={2} />
                <div className="muted">{p.kwh.toFixed(2)} kWh</div>
              </Card>
            ))}
          </div>
        </Space>
      </Card>
    </Space>
  )
}
