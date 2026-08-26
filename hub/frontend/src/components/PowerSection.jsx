import { useEffect, useState } from 'react'
import DeleteIcon from '@mui/icons-material/Delete'
import AddIcon from '@mui/icons-material/Add'
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'
import { StatBlock } from './StatBlock.jsx'

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
    <Stack spacing={3} sx={{ width: '100%' }}>
      <Card>
        <CardHeader title="Power calculator" action={<span className="muted">{status}</span>} />
        <CardContent sx={{ pt: 0 }}>
          <Stack spacing={2} sx={{ width: '100%' }}>
            <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
              <Typography variant="body2">Cost per kWh</Typography>
              <TextField select size="small" value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)} sx={{ width: 260 }}>
                {CURRENCY_OPTIONS.map((o) => (
                  <MenuItem key={o.value} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </TextField>
              {currencyCode === OTHER_CURRENCY && (
                <TextField
                  size="small"
                  value={customSymbol}
                  onChange={(e) => setCustomSymbol(e.target.value)}
                  placeholder="Symbol, e.g. kr"
                  sx={{ width: 100 }}
                />
              )}
              <TextField
                type="number"
                size="small"
                slotProps={{ htmlInput: { min: 0, step: 0.01 } }}
                value={costPerKwh}
                onChange={(e) => setCostPerKwh(Number(e.target.value) || 0)}
                sx={{ width: 140 }}
              />
            </Stack>

            <StatBlock
              title={`Current estimated draw (${rows.length} online node${rows.length === 1 ? '' : 's'} reporting)`}
              value={totalWatts}
              suffix=" W"
              precision={1}
            />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
              {projections.map((p) => (
                <Card key={p.key} variant="outlined">
                  <CardHeader title={p.label} slotProps={{ title: { variant: 'subtitle2' } }} sx={{ pb: 0.5 }} />
                  <CardContent sx={{ pt: 0 }}>
                    <StatBlock value={p.cost} prefix={currencySymbol} precision={2} />
                    <div className="muted">{p.kwh.toFixed(2)} kWh</div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Typography variant="body2" color="text.secondary">
              Rough whole-system estimate from CPU load only (each node's configured idle/max wattage, linearly scaled
              by cpu_percent) -- not a measured reading. Real draw (GPU, disk, PSU losses) will differ; tune a node's{' '}
              <code>idle_watts</code>/<code>max_watts</code> in its config for a better fit.
            </Typography>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Per-node breakdown" />
        <CardContent sx={{ pt: 0 }}>
          {rows.length ? (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Node</TableCell>
                    <TableCell>Estimated draw</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.key}>
                      <TableCell>{r.name}</TableCell>
                      <TableCell>{r.watts.toFixed(1)} W</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <p className="muted">No online nodes reporting power estimates yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="What-if scenario" />
        <CardContent sx={{ pt: 0 }}>
          <Stack spacing={2} sx={{ width: '100%' }}>
            <Typography variant="body2" color="text.secondary">
              Uncheck a real node to see the projection without it, or add a hypothetical machine with a flat wattage
              guess -- it has no live CPU usage to scale from, so unlike real nodes above this is just a number you
              supply (e.g. from the machine's PSU rating).
            </Typography>

            {rows.length > 0 && (
              <Stack spacing={0.5} sx={{ width: '100%' }}>
                <Typography variant="body2" fontWeight={600}>
                  Real nodes
                </Typography>
                {rows.map((r) => (
                  <FormControlLabel
                    key={r.key}
                    control={<Checkbox checked={!excludedNodeIds.has(r.key)} onChange={() => toggleNodeExcluded(r.key)} size="small" />}
                    label={
                      <>
                        {r.name} <span className="muted">({r.watts.toFixed(1)} W)</span>
                      </>
                    }
                  />
                ))}
              </Stack>
            )}

            <Stack spacing={1} sx={{ width: '100%' }}>
              <Typography variant="body2" fontWeight={600}>
                Hypothetical machines
              </Typography>
              {whatIfRows.map((r) => (
                <Stack key={r.id} direction="row" spacing={1.5} alignItems="center">
                  <TextField
                    size="small"
                    value={r.name}
                    onChange={(e) => updateWhatIfRow(r.id, { name: e.target.value })}
                    sx={{ width: 200 }}
                    placeholder="Machine name"
                  />
                  <TextField
                    type="number"
                    size="small"
                    slotProps={{ htmlInput: { min: 0, step: 5 } }}
                    value={r.watts}
                    onChange={(e) => updateWhatIfRow(r.id, { watts: Number(e.target.value) || 0 })}
                    sx={{ width: 120 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    W
                  </Typography>
                  <IconButton onClick={() => removeWhatIfRow(r.id)} aria-label="Remove machine" size="small">
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Stack>
              ))}
              <Button startIcon={<AddIcon />} variant="outlined" onClick={addWhatIfRow} sx={{ alignSelf: 'flex-start' }}>
                Add machine
              </Button>
            </Stack>

            <StatBlock title="What-if total draw" value={whatIfTotalWatts} suffix=" W" precision={1} />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
              {whatIfProjections.map((p) => (
                <Card key={p.key} variant="outlined">
                  <CardHeader title={p.label} slotProps={{ title: { variant: 'subtitle2' } }} sx={{ pb: 0.5 }} />
                  <CardContent sx={{ pt: 0 }}>
                    <StatBlock value={p.cost} prefix={currencySymbol} precision={2} />
                    <div className="muted">{p.kwh.toFixed(2)} kWh</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  )
}
