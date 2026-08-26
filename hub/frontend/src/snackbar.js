import { useEffect } from 'react'
import { useSnackbar } from 'notistack'

// notistack's documented pattern for calling enqueueSnackbar from outside a
// component (replaces antd's static message.success/error/... API, used
// throughout this app's action handlers) -- stash the hook's function in a
// module-level ref from one component rendered once inside <SnackbarProvider>
// (see main.jsx), then have notify.* call through it.
let enqueueRef = null

export function SnackbarUtilsConfigurator() {
  const { enqueueSnackbar } = useSnackbar()
  useEffect(() => {
    enqueueRef = enqueueSnackbar
    return () => {
      enqueueRef = null
    }
  }, [enqueueSnackbar])
  return null
}

function show(message, variant) {
  if (!enqueueRef) return
  enqueueRef(message, { variant })
}

export const notify = {
  success: (message) => show(message, 'success'),
  error: (message) => show(message, 'error'),
  warning: (message) => show(message, 'warning'),
  info: (message) => show(message, 'info'),
}
