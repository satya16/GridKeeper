---
id: boinc-backend
type: component
status: implemented-untested
files:
  - worker/grid_worker/backends/boinc.py
relates_to: [worker, scheduling]
---

Controls a locally-installed BOINC client by shelling out to `boinccmd`
rather than speaking the GUI RPC protocol on port 31416 directly — trades
some parsing fragility (text-output scraping, see the module docstring)
for not needing to implement RPC's auth handshake. `get_status()` parses
`boinccmd --get_simple_gui_info` / `--get_cc_status`; commands
(`suspend_project`, `resume_project`, `suspend_all`, `resume_all`,
`attach_project`, `detach_project`) map to `boinccmd --project ...
suspend/resume/detach`, `--set_run_mode`, and `--project_attach` (flag
names confirmed real against `boinccmd --help` output, 2026-08-18).

`attach_project(url, account_key)` takes the project's account
authenticator (from that project's "your account" web page) — a
long-lived credential, unlike the manager's one-time pairing tokens. The
manager (`manager/app/api/workers.py::_redact_payload`) masks
`account_key` before writing a command to the `commands` table or
returning it from the command-lookup API, since that table is meant to
be a durable audit log (`docs/REQUIREMENTS.md` section 9) — the real key
still reaches the worker over the WebSocket at dispatch time, only what
gets persisted/echoed back is redacted. If another sensitive field is
ever added to any backend's payload, add it to
`_SENSITIVE_PAYLOAD_FIELDS` there rather than assuming a new field is
safe to log by default.

`apply_schedule()` (used by [scheduling](scheduling.md)) is a separate
concern from the status/command path: it writes a temp
`global_prefs_override.xml` and applies it via `boinccmd
--set_global_prefs_override` + `--read_global_prefs_override`, letting
BOINC's own idle/hours engine take over rather than polling from the
worker side.

If `boinccmd`'s text format turns out to vary by version, swap the
parsing internals without touching callers — they only see the dict
shapes `get_status()` returns.

**Partially verified** (2026-08-11, local smoke test — no BOINC installed
in the test environment): confirmed `is_available()` correctly reports
`False` and the worker skips this backend entirely rather than crashing;
issuing a command against it produced a clean `BoincError("boinccmd not
found on PATH")` that propagated correctly as a `command_result` error
frame back through the REST API, so the *failure* path works. The actual
`boinccmd` output parsing and `apply_schedule()` remain unverified against
a real BOINC install — that's the real risk here, not the plumbing
around it.

**Real-install attempt blocked (2026-08-13):** tried to get a real BOINC
daemon running on a genuine (non-VM) Ubuntu 26.04 "resolute" machine
specifically to unblock this. Ubuntu's `boinc-client` package
(`8.2.9+dfsg-1build1`, universe repo) has a reproducible GUI RPC bug: the
daemon accepts TCP connections on port 31416 and receives requests fine
(confirmed via `strace` — correct request framing reaches it), but its
main thread frequently never services them, returning nothing until the
client times out (`Operation failed: read() failed`). Reproduced across
five separate attempts including a full `apt purge` + clean reinstall
(ruling out corrupted local state) and with AppArmor's kernel audit log
checked and clear (ruling that out too) — but the *shape* of the failure
wasn't even consistent (sometimes hung mid-CPU-benchmark, sometimes hung
with no benchmark children at all, once actually worked but rejected its
own just-read password with `Authorization failure: -102`). That
inconsistency is itself informative: this reads as a genuinely flaky
daemon build, not one clean bug with one fix.

Tried the snap build (`aenbleidd`'s `boinc`, version 8.2.13 — newer than
the broken apt package) as an alternative: it installs and runs, but its
snap packaging **doesn't ship `boinccmd` at all** (only `boinc`,
`boinc.client`, `boinc.manager` — the last needs a GUI). So it can't
substitute for what this backend actually shells out to, even if its
daemon turns out to be healthier.

**Not resolved. Options if picked up again:** (a) build the `boinc` daemon
itself from source against the BOINC GitHub repo — note the hang is
server-side (the daemon's RPC thread not servicing requests), so building
just `boinccmd` from source wouldn't help; the daemon binary is what needs
replacing, (b) try a different/older Ubuntu release or a PPA with a less
stale `boinc-client` build, (c) try genuinely different hardware to rule
out a kernel/CPU-specific benchmark-timing bug. Full blow-by-blow (strace
output, exact repro commands) lived in that day's conversation, not
reproduced here — this note is the durable summary. `apply_schedule()`
and real command effects (`suspend_project` etc.) remain completely
unverified as a result; only the failure-path behavior above has ever
been confirmed.

**Re-confirmed 2026-08-18:** same bug reproduces on a fresh daemon start
(`systemctl enable --now boinc-client`, no prior state). `boinccmd
--get_cc_status` / `--get_simple_gui_info` hang until timeout with
`read() failed` every time, despite the daemon logging "GUI RPC password
is empty" (i.e. no auth should even be required). Ubuntu's archive has
no newer `boinc-client` version to upgrade into (`apt-cache madison`
shows only `8.2.9+dfsg-1build1`) — option (b)'s "different Ubuntu
release" would mean a different distro release entirely, not just
`apt upgrade`. Also noted: `/var/lib/boinc-client/` isn't listable by a
non-`boinc`-group user, so `gui_rpc_auth.cfg` can't be read either — a
separate, secondary permissions issue (fixable with
`usermod -aG boinc $USER` + new login session) that doesn't affect the
hang itself since the password is empty anyway.

**Re-verified 2026-08-18 (second pass, same day):** restarted the daemon
completely fresh (`sudo systemctl restart boinc-client`, new PID) and
retested — identical hang, every time. `strace -f -tt` on `boinccmd`
during the hang narrows this further than the original writeup: the
*client* correctly `connect()`s, `sendto()`s the well-formed
`<boinc_gui_rpc_request><get_cc_status/>...` request (67 bytes), then
calls `recvfrom()`, which immediately returns `-1 EINTR` (not a timeout —
this happens within milliseconds, and `SO_RCVTIMEO` is set to 30s so
that's not what's firing). After that `EINTR`, **`boinccmd` makes zero
further syscalls of any kind** until killed — no retry of `recvfrom`, no
`poll`/`select`, no `nanosleep`, nothing. This reframes the bug slightly:
the original note characterized it as the daemon's RPC thread not
servicing requests; this trace shows the request *is* being sent
correctly and something (likely an internal timer/signal whose handler
lacks `SA_RESTART`) interrupts the client's read, which then never
retries — which could be a `boinccmd` client-side bug as much as (or
instead of) a daemon-side one. Doesn't change the practical
conclusion (still not usable, same three unblock options), but matters
if anyone picks option (a) — rebuilding just the daemon might not be
enough if the bug is actually in the client's retry logic.

**`attach_project`/`detach_project` added 2026-08-18** (dashboard form +
per-project "Detach" button in [dashboard-ui](dashboard-ui.md), tests in
`worker/tests/test_boinc.py` and the redaction test in
`manager/tests/test_workers.py`). Same status as the rest of this
backend's command path: the exact `boinccmd` flag names/argument order
were checked against real `boinccmd --help` output, but the daemon-hang
bug above means neither command has been exercised against a real
running BOINC client yet — that verification is blocked on the same
unresolved daemon issue as everything else in this file.
