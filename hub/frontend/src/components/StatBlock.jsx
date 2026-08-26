import { Box, Typography } from '@mui/material'

// MUI has no built-in equivalent to antd's <Statistic> -- a small
// title/value pair (used by PowerSection's current-draw and per-
// projection cost figures).
export function StatBlock({ title, value, prefix, suffix, precision = 0 }) {
  const formatted = typeof value === 'number' ? value.toFixed(precision) : value
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
        {title}
      </Typography>
      <Typography variant="h5" sx={{ fontWeight: 600, mt: 0.25 }}>
        {prefix}
        {formatted}
        {suffix}
      </Typography>
    </Box>
  )
}
