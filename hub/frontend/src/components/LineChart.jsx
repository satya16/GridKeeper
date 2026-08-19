import { useRef, useState } from 'react'

const WIDTH = 600
const HEIGHT = 200
const PAD_LEFT = 34
const PAD_RIGHT = 10
const PAD_TOP = 10
const PAD_BOTTOM = 10
const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM
const GRID_STEPS = 4

function niceMax(value) {
  if (value <= 0) return 1
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)))
  const normalized = value / magnitude
  let niceNormalized
  if (normalized <= 1) niceNormalized = 1
  else if (normalized <= 2) niceNormalized = 2
  else if (normalized <= 5) niceNormalized = 5
  else niceNormalized = 10
  return niceNormalized * magnitude
}

function buildPathD(points, xScale, yScale) {
  let d = ''
  let penDown = false
  for (const p of points) {
    if (p.v === null || p.v === undefined) {
      penDown = false
      continue
    }
    d += `${penDown ? 'L' : 'M'}${xScale(p.t).toFixed(1)},${yScale(p.v).toFixed(1)} `
    penDown = true
  }
  return d.trim()
}

// One chart, one axis, per the dataviz skill's "never dual-axis" rule --
// CPU%, RAM%, and temperature are always three separate <LineChart>s, never
// one chart with two y-scales. Ported 1:1 from dashboard.js's renderChart()/
// attachChartInteraction(), including the fixed-position (not
// cursor-following) tooltip pinned to the card's top-right corner.
export function LineChart({ title, series, windowSeconds, yMin = 0, yMax: yMaxOpt, unit = '', unitShort = '' }) {
  const svgRef = useRef(null)
  const [hover, setHover] = useState(null) // { svgX, hoveredT } | null

  const now = Date.now() / 1000
  const minT = now - windowSeconds
  const maxT = now

  if (!series.length) {
    return (
      <div className="chart-svg-wrap">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="No devices selected" />
        <p className="muted">Select a device above to see its data here.</p>
      </div>
    )
  }

  let yMax = yMaxOpt
  if (yMax === undefined) {
    const vals = series.flatMap((s) => s.points.map((p) => p.v).filter((v) => v !== null && v !== undefined))
    yMax = niceMax(vals.length ? Math.max(...vals) * 1.15 : 1)
  }
  if (yMax <= yMin) yMax = yMin + 1

  const xScale = (t) => PAD_LEFT + ((t - minT) / (maxT - minT)) * PLOT_W
  const yScale = (v) => PAD_TOP + PLOT_H - ((v - yMin) / (yMax - yMin)) * PLOT_H

  const gridLines = []
  const axisLabels = []
  for (let i = 0; i <= GRID_STEPS; i++) {
    const v = yMin + ((yMax - yMin) * i) / GRID_STEPS
    const yPix = yScale(v)
    gridLines.push(
      <line key={i} x1={PAD_LEFT} y1={yPix} x2={WIDTH - PAD_RIGHT} y2={yPix} stroke="var(--gk-border)" strokeWidth={1} />,
    )
    axisLabels.push(
      <text key={i} x={PAD_LEFT - 6} y={yPix + 3} textAnchor="end" fontSize={9} fill="var(--gk-muted)">
        {Math.round(v)}
        {unitShort}
      </text>,
    )
  }

  const paths = []
  const endpoints = []
  for (const s of series) {
    const d = buildPathD(s.points, xScale, yScale)
    if (!d) continue
    paths.push(<path key={s.id} d={d} fill="none" stroke={s.color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />)
    const lastPoint = [...s.points].reverse().find((p) => p.v !== null && p.v !== undefined)
    if (lastPoint) {
      endpoints.push(
        <circle key={s.id} cx={xScale(lastPoint.t)} cy={yScale(lastPoint.v)} r={4} fill={s.color} stroke="var(--gk-chart-point-ring)" strokeWidth={2} />,
      )
    }
  }

  const handleMove = (ev) => {
    const rect = svgRef.current.getBoundingClientRect()
    const svgX = ((ev.clientX - rect.left) / rect.width) * WIDTH
    const frac = Math.min(1, Math.max(0, (svgX - PAD_LEFT) / PLOT_W))
    setHover({ svgX, hoveredT: minT + frac * (maxT - minT) })
  }

  const nearestFor = (s) => {
    let nearest = null
    let nearestDiff = Infinity
    for (const p of s.points) {
      if (p.v === null || p.v === undefined) continue
      const diff = Math.abs(p.t - hover.hoveredT)
      if (diff < nearestDiff) {
        nearestDiff = diff
        nearest = p
      }
    }
    return nearest
  }

  return (
    <div className="chart-svg-wrap">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`${title} over the last ${Math.round(windowSeconds / 60)} minutes`}
      >
        {gridLines}
        {axisLabels}
        {paths}
        {endpoints}
        <rect
          x={PAD_LEFT}
          y={PAD_TOP}
          width={PLOT_W}
          height={PLOT_H}
          fill="transparent"
          onPointerMove={handleMove}
          onPointerLeave={() => setHover(null)}
        />
        {hover && <line x1={hover.svgX} y1={PAD_TOP} x2={hover.svgX} y2={PAD_TOP + PLOT_H} stroke="var(--gk-muted)" strokeWidth={1} />}
      </svg>

      {hover && (
        <div className="chart-tooltip visible">
          <div className="tt-time">{new Date(hover.hoveredT * 1000).toLocaleTimeString()}</div>
          {series.map((s) => {
            const nearest = nearestFor(s)
            return (
              <div className="tt-row" key={s.id}>
                <span className="swatch" style={{ background: s.color }} />
                <span>{s.name}</span>
                <span className="tt-value">{nearest ? `${Math.round(nearest.v * 10) / 10}${unit}` : '--'}</span>
              </div>
            )
          })}
        </div>
      )}

      <div className="chart-legend">
        {series.map((s) => (
          <span className="chart-legend-item" key={s.id}>
            <span className="swatch" style={{ background: s.color }} />
            <span>{s.name}</span>
          </span>
        ))}
      </div>
    </div>
  )
}
