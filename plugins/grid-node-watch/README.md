# grid-node-watch

A generic process-watcher [grid-node](https://pypi.org/project/grid-node/)
backend plugin -- point it at *any* program by name via a config file,
instead of writing a dedicated plugin (like
[grid-node-gimps](../grid-node-gimps)) for each one. See
`grid_node_watch/backend.py` for the implementation and an honest note on
what's been verified so far vs. left untested.

## Install

```bash
pip install grid-node grid-node-watch
```

`grid-node` discovers this package automatically via its
`grid_node.backends` entry point -- no config-file edit or code change in
`grid-node` itself.

## Configure

Write `~/.local/share/grid-node-watch/targets.json` (override the path
with `GRIDKEEPER_WATCH_CONFIG`):

```json
{
  "targets": [
    {
      "name": "blender-render",
      "match": "blender",
      "start_cmd": ["/usr/bin/blender", "-b", "render.blend"],
      "stop_signal": "SIGTERM"
    },
    {
      "name": "matlab",
      "match": "MATLAB"
    }
  ]
}
```

- `name` -- id used in the hub's start/stop payloads and in `get_status()`.
- `match` -- case-insensitive substring matched against each running
  process's name *and* its full command line, so a program invoked
  through a wrapper script or an absolute path is still found.
- `start_cmd` -- optional. Omit it for a **watch-only** target (e.g.
  MATLAB above): grid-node will report whether it's running but refuse to
  start it. With it, grid-node can launch the program itself.
- `stop_signal` -- optional, defaults to `SIGTERM`.

## What this backend can and can't do

- Reports `running`, `pid`, `cpu_percent`, `mem_percent`, `uptime_seconds`,
  and the matched `cmdline` for each configured target, once per status
  poll -- shows up in the hub dashboard the same as any backend, via the
  generic fallback UI (`GenericBackendBlock.jsx`) since it's not a
  built-in like BOINC/FAH.
- Detects a target whether grid-node started it or a human did -- it's a
  process-list scan (`psutil.process_iter`), not a pidfile grid-node
  itself wrote. That's the point: it works on a program you're already
  running by hand.
- `start`/`stop` are the only remote controls (like GIMPS, no live
  pause/resume) -- and only for targets with `start_cmd` configured.
- No per-program insight (no log tailing, no work-unit status) -- that's
  the tradeoff for not needing a bespoke plugin per program. `cpu_percent`
  on the very first poll after a process is (re)matched reads `0.0`; it's
  psutil comparing against no prior baseline yet, not a bug -- it becomes
  meaningful from the next poll onward.

## What's actually verified

`tests/test_backend.py` (12 tests) exercises real `psutil` process
discovery against real background processes the tests spawn independently
of this plugin, plus a regression test for a real bug found below.

Beyond unit tests, this was live-verified end-to-end on 2026-08-24 against
a real hub+node pair (a scratch hub instance and a scratch-enrolled node,
so the real dev machine's own hub/node setup was untouched): a real
ffmpeg process (1080p libx264 encode, genuinely CPU-bound, not a toy sleep
loop) was started via a hub-issued command, tracked across several live
status polls -- `cpu_percent` reflected real multi-core load (~650%,
cross-checked against `ps` directly) and `uptime_seconds` increased
correctly between polls -- then stopped cleanly via a second hub command,
confirmed both through the hub's status view and by checking the OS
process directly. `GET /api/backends` was confirmed to report this
backend's label and actions correctly, which is what the dashboard's
`GenericBackendBlock.jsx` fallback UI renders from -- the actual browser
rendering itself wasn't screenshotted, but the data contract it consumes
was.

**A real bug was found and fixed in that session**: the first version of
`_find_process()` matched the target string against the *entire* command
line, which produced a genuine false positive -- it matched this very
plugin's own test harness, because a shell one-liner being used to test
it happened to contain the word "ffmpeg" as data inside a quoted argument,
not as the actual program. Matching is now restricted to the process's
name, argv[0]'s basename, and (for scripts launched through a known
interpreter) argv[1]'s basename -- see `_find_process()`'s docstring for
the exact reasoning and its own remaining known gap (a target launched as
`python3 -m mymodule`, where the identifying name is past argv[1], won't
be found).

Still not tried: a real-world long-running desktop program like an actual
MATLAB/Blender install, or two configured targets running concurrently.
