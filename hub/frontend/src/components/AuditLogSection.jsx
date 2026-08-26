import { useState } from 'react'
import {
  Card,
  CardContent,
  CardHeader,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableFooter,
  TablePagination,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { api } from '../api.js'
import { usePolling } from '../usePolling.js'

const AUDIT_LOG_REFRESH_INTERVAL_MS = 10000
const PAGE_SIZE = 25

export function AuditLogSection() {
  const { data: entries, status } = usePolling(api.listAuditLog, AUDIT_LOG_REFRESH_INTERVAL_MS)
  const [page, setPage] = useState(0)
  const rows = entries || []
  const pageRows = rows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)

  return (
    <Card>
      <CardHeader title="Audit log" action={<span className="muted">{status}</span>} />
      <CardContent sx={{ pt: 0 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          The most recent actions taken by any user, newest first.
        </Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 190 }}>When</TableCell>
                <TableCell sx={{ width: 140 }}>User</TableCell>
                <TableCell sx={{ width: 200 }}>Action</TableCell>
                <TableCell>Target</TableCell>
                <TableCell>Detail</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {pageRows.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell>{new Date(entry.created_at).toLocaleString()}</TableCell>
                  <TableCell>{entry.username}</TableCell>
                  <TableCell>{entry.action}</TableCell>
                  <TableCell>{entry.target || <span className="muted">—</span>}</TableCell>
                  <TableCell>
                    {entry.detail ? <code style={{ fontSize: 12 }}>{JSON.stringify(entry.detail)}</code> : <span className="muted">—</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TablePagination
                  count={rows.length}
                  rowsPerPage={PAGE_SIZE}
                  rowsPerPageOptions={[PAGE_SIZE]}
                  page={page}
                  onPageChange={(_, newPage) => setPage(newPage)}
                />
              </TableRow>
            </TableFooter>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  )
}
