import { useEffect, useRef, useState } from 'react'
import { Button, Card, Checkbox, Space } from 'antd'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'
import { LineChart } from './LineChart.jsx'

const METRICS_REFRESH_INTERVAL_MS = 7000
const METRICS_WINDOW_SECONDS = 30 * 60
const MAX_CHART_SERIES = 8

// Validated 2026-08-18 via the dataviz skill's scripts/validate_palette.js
// (dark mode, surface #1a1a19) -- all six checks pass. Do not reorder or
// substitute hues without re-running that validator.
const CATEGORICAL_COLORS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']

function buildSeriesForMetric(metricsData, selection, colors, field, windowStart) {
  const series = []
  for (const id of selection) {
    if (!colors.has(id)) continue
    const entry = metricsData[id]
    if (!entry) continue
    const points = entry.points.filter((p) => p.t >= windowStart).map((p) => ({ t: p.t, v: p[field] }))
    series.push({ id, name: entry.name || id, color: colors.get(id), points })
  }
  return series
}

export function MetricsSection() {
  const { data, status } = usePolling(api.getMetrics, METRICS_REFRESH_INTERVAL_MS)
  const metricsData = data || {}

  // Color assignment: fixed order by sorted id, stable across polls unless
  // the *set* of ids actually changes ("color follows the entity, never
  // its rank" -- see the dataviz skill).
  const colorOrderKeyRef = useRef('')
  const [colors, setColors] = useState(new Map())
  const [selection, setSelection] = useState(null) // null = not yet initialized

  useEffect(() => {
    const sortedIds = Object.keys(metricsData).sort()
    const key = sortedIds.join(',')
    if (key === colorOrderKeyRef.current) return
    colorOrderKeyRef.current = key
    const next = new Map()
    sortedIds.slice(0, CATEGORICAL_COLORS.length).forEach((id, i) => next.set(id, CATEGORICAL_COLORS[i]))
    setColors(next)
    setSelection((prev) => prev ?? new Set(sortedIds.filter((id) => next.has(id)).slice(0, MAX_CHART_SERIES)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const ids = Object.keys(metricsData).sort((a, b) => (metricsData[a].name || '').localeCompare(metricsData[b].name || ''))
  const sel = selection || new Set()

  const toggle = (id) => {
    const next = new Set(sel)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelection(next)
  }

  const windowStart = Date.now() / 1000 - METRICS_WINDOW_SECONDS
  const chartSpecs = [
    { key: 'cpu', title: 'CPU usage', field: 'cpu_percent', yMin: 0, yMax: 100, unit: '%', unitShort: '%' },
    { key: 'ram', title: 'RAM usage', field: 'ram_percent', yMin: 0, yMax: 100, unit: '%', unitShort: '%' },
    { key: 'temp', title: 'Temperature', field: 'temperature_c', yMin: 0, unit: '°C', unitShort: '°' },
  ]

  return (
    <Card title="Live metrics" extra={<span className="muted">{status}</span>}>
      <div className="metrics-filter">
        {ids.length ? (
          <>
            {ids.map((id) => {
              const hasColor = colors.has(id)
              return (
                <label key={id} className={hasColor ? '' : 'disabled'} title={hasColor ? undefined : `Only ${MAX_CHART_SERIES} devices can be graphed at once -- deselect another to add this one`}>
                  <Checkbox disabled={!hasColor} checked={hasColor && sel.has(id)} onChange={() => toggle(id)} />
                  <span className="swatch" style={{ background: hasColor ? colors.get(id) : 'transparent' }} />
                  <span>{metricsData[id].name || id}</span>
                </label>
              )
            })}
            <Space size="small" style={{ marginLeft: 'auto' }}>
              <Button size="small" onClick={() => setSelection(new Set(ids.filter((id) => colors.has(id)).slice(0, MAX_CHART_SERIES)))}>
                All
              </Button>
              <Button size="small" onClick={() => setSelection(new Set())}>
                None
              </Button>
            </Space>
          </>
        ) : (
          <p className="muted">No metrics reported yet.</p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        {chartSpecs.map((spec) => (
          <Card key={spec.key} size="small" type="inner" className="chart-card" title={`${spec.title} (${spec.unit}) — last 30 min`}>
            <LineChart
              title={spec.title}
              series={buildSeriesForMetric(metricsData, sel, colors, spec.field, windowStart)}
              windowSeconds={METRICS_WINDOW_SECONDS}
              yMin={spec.yMin}
              yMax={spec.yMax}
              unit={spec.unit}
              unitShort={spec.unitShort}
            />
          </Card>
        ))}
      </div>
    </Card>
  )
}
