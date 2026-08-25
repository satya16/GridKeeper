# grid-node-gimps

A [GIMPS](https://www.mersenne.org/) (mprime) backend plugin for
[grid-node](https://pypi.org/project/grid-node/) -- proof of concept that
a third party can add a distributed-computing backend to GridKeeper without
touching `grid-node`'s own source. See `grid_node_gimps/backend.py` for the
implementation notes and what was actually live-verified.

## Install

```bash
pip install grid-node grid-node-gimps
```

That's it -- `grid-node` discovers this package automatically via its
`grid_node.backends` entry point (no config file edit, no code change in
`grid-node` itself).

## One-time setup (do this before grid-node tries to start it)

mprime's first run is an interactive wizard (license terms, PrimeNet
account or manual/anonymous mode, resource limits) -- this plugin
deliberately does not try to automate that on your real machine. Run it
once yourself:

```bash
mkdir -p ~/.local/share/grid-node-gimps
cd ~/.local/share/grid-node-gimps
mprime -m
# Choose "Just stress testing" (no PrimeNet account needed) unless you
# want to actually contribute Mersenne-prime search work, in which case
# follow the automatic/manual PrimeNet instructions in mprime's own
# readme.txt.
```

After that, grid-node's `start`/`stop` commands work against this
directory. Override the location with `GRIDKEEPER_GIMPS_DIR`, and the
binary path with `GRIDKEEPER_GIMPS_BIN` if `mprime`/`prime95` isn't on
`PATH`.

## What this backend can and can't do

Unlike BOINC/FAH, mprime has no control socket/RPC for an already-running
process -- so there's no live pause/resume, no per-task status. `start`/
`stop` (process start + graceful `SIGINT`) are the only real remote
primitives. `get_status()` reports whether it's running, its pid, and the
last line of `prime.log`. See the module docstring for exactly what was
live-verified vs. left honestly untested.
