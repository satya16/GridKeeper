import { useCallback, useEffect, useRef, useState } from 'react'

// Matches dashboard.js's original pattern: fetch immediately, then again
// every `intervalMs`, tracking a human-readable "last updated"/"failed"
// status string alongside the data itself. A falsy `intervalMs` (e.g.
// App.jsx passing null while logged out) skips polling entirely --
// `setInterval(fn, null)` would otherwise coerce to a 0ms interval and
// fire rapidly rather than not fire at all.
export function usePolling(fetcher, intervalMs) {
  const [data, setData] = useState(null)
  const [status, setStatus] = useState('')
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const runOnce = useCallback(async () => {
    try {
      const result = await fetcherRef.current()
      setData(result)
      setStatus(`updated ${new Date().toLocaleTimeString()}`)
    } catch (err) {
      setStatus(`refresh failed: ${err.message}`)
    }
  }, [])

  useEffect(() => {
    if (!intervalMs) return
    runOnce()
    const id = setInterval(runOnce, intervalMs)
    return () => clearInterval(id)
  }, [runOnce, intervalMs])

  return { data, status, refresh: runOnce }
}
