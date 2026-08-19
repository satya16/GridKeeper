---
id: boinc-backend
type: component
status: implemented-verified
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

## RESOLVED 2026-08-18: swapped Ubuntu's package for BOINC's own official build

The daemon-hang bug above is fixed — the fix was option (b)'s spirit
("less stale build") but via a different, better source than a PPA:
**BOINC's own GitHub Releases** publish official pre-built `.deb`
packages per Ubuntu codename, including one built for this exact release
("resolute") — `client_release/8.2/8.2.15` on
[github.com/BOINC/boinc/releases](https://github.com/BOINC/boinc/releases),
i.e. `boinc-client_8.2.15-4612_amd64_resolute.deb`. Same package name as
the broken apt package, so `sudo dpkg -i` cleanly replaced it in place —
same package name, own systemd unit (self-consistent, points at its own
`/usr/local/bin/boinc` and `/var/lib/boinc`, adds some sandboxing
Ubuntu's older unit lacked), no source compilation needed. This was
deliberately chosen over building from source or a random PPA — "use
what BOINC's own project already builds and ships," matching how the FAH
blocker was solved by installing `fah-client` from foldingathome.org's
own release server instead of Ubuntu's package.

Verified thoroughly, same day: `boinccmd --get_cc_status` /
`--get_simple_gui_info` now return real output instantly and reliably
(confirmed across many repeated calls, in both a normal user terminal —
independently, not just through automation — and this project's usual
tooling) — the `EINTR`-then-never-retry bug traced via `strace` in the
8.2.9 build genuinely does not reproduce in 8.2.15. `suspend_all()` /
`resume_all()` confirmed to actually change daemon state (`--set_run_mode
never`/`auto`, verified via `--get_cc_status` before/after), round-tripped
through `worker.py`'s real `_execute_command` dispatch path, not just
called directly.

**Found and fixed a real parsing bug along the way**, same pattern as
the FAH `wu`-vs-`assignment` field mistake: `get_status()`'s `run_mode`
was reading a `"task mode:"` line from `--get_cc_status` that doesn't
exist in this client's output at all — the real output has no
single top-level mode line, only per-section `"current mode:"` lines
under `"CPU status"` / `"GPU status"` / `"Network status"` (in that
order; the regex match is CPU's, which is what we want). Was silently
returning `"unknown"` every time, untested because the daemon-hang bug
made this whole code path unreachable until now. Fixed; `run_mode` now
reports BOINC's own real phrasing (e.g. `"according to prefs"` for the
default/auto state, not literally the word `"auto"` — that's the
*command* value you send, not the *status* phrasing BOINC reports back).
Test fixtures in `worker/tests/test_boinc.py` (`SAMPLE_CC_STATUS`)
replaced with the real captured output rather than the invented format
that was there before.

**`apply_schedule()`'s `global_prefs_override.xml` effect on real Activity
behavior is still unverified.**

## RESOLVED 2026-08-19: attach_project verified against a real project, two real parsing bugs found+fixed

Signed up for a real Einstein@Home account and attached it through the
dashboard's "Attach a project…" form (`POST
/api/workers/{id}/commands`, `attach_project`), end to end — real
account key, real WebSocket dispatch, real `boinccmd --project_attach`.
`boinccmd --get_project_status` on the worker machine confirmed the
attach succeeded (real `master URL`, scheduler RPC completed). Also
confirmed live: the manager's redaction — `POST .../commands`'s response
echoed `account_key` as `"***redacted***"` even though the real key
reached the worker.

But the *dashboard's* view of the attached project was wrong — found by
actually looking at the parsed output, not just checking "did attach
return ok":

1. **`get_status()` used the wrong field name.** It read `p.get("manager
   URL", ...)`, but real `boinccmd --get_simple_gui_info` output calls
   the field `"master URL"` — so `projects[].url` was always `""`. The
   test fixture (`SAMPLE_GUI_INFO` in `worker/tests/test_boinc.py`)
   already had the *correct* key, but no test ever asserted
   `status["projects"][0]["url"]`, only `name`/`suspended` — that
   coverage gap is exactly how this shipped unnoticed.
2. **`_parse_blocks()` clobbered project names.** Real project blocks
   contain nested `GUI URL:` sub-entries (links to the project's FAQ,
   account page, etc.) that reuse field names like `"name"` and `"URL"`
   for the link itself. The parser didn't treat those as nested — it
   just kept overwriting `current_block["name"]` line by line, so by the
   end of the block, `name` held the *last* GUI URL's label (observed:
   `"GEO600 project"`) instead of the real project name
   (`"Einstein@Home"`). The old `SAMPLE_GUI_INFO` fixture had no nested
   `GUI URL:` entries at all, so this had no way to surface in tests
   either.

Fixed both: `_parse_blocks()` now uses `setdefault` instead of plain
assignment (first-occurrence wins — project-level fields are always
written before any nested `GUI URL:` sub-entry repeats those key names),
and `get_status()` now reads `"master URL"`. `SAMPLE_GUI_INFO` updated
with real nested `GUI URL:` entries (captured from live Einstein@Home
output), and both `test_parse_blocks_projects` and
`test_get_status_end_to_end` now assert on `url`/`master URL` so a
regression here would fail loudly. Re-verified against the live daemon
after the fix: dashboard now correctly reports
`{"url": "https://einstein.phys.uwm.edu/", "name": "Einstein@Home"}`.

**Still not independently verified:** the dashboard's React rendering of
this data in an actual browser (`BoincBlock.jsx`) — no browser tooling
was available this session, so this was confirmed only via the REST API
response, not by looking at the rendered page. Low risk (it's a direct
prop-to-text render of the same JSON), but unconfirmed. `detach_project`
against this real project also untested — attach only, project left
attached deliberately since a real account now exists for future testing.

## Added 2026-08-19: `cpu_suspend_reason` field

After attaching, the user asked why CPU usage wasn't going up — turned
out BOINC's own default preference is to not crunch on battery power
(`boinccmd --get_cc_status`'s CPU section shows `suspended: on
batteries` in that case), which the dashboard had no way to surface;
`run_mode` alone (`"according to prefs"`) doesn't explain it.
`get_status()` now also returns `cpu_suspend_reason: str | None`, parsed
by a new `_cpu_suspend_reason()` helper that's deliberately scoped to
just the CPU section of `--get_cc_status` output (regex-bounded between
`"CPU status"` and `"GPU status"`) rather than a naive whole-text
`_find_field` search — GPU/Network can carry their own independent
`suspended: <reason>` line, and a naive search would misattribute a
GPU-only suspension as the reason CPU work isn't running. Verified live:
correctly reported `"on batteries"` on this machine while genuinely
running unplugged. `BoincBlock.jsx` shows it as a warning-styled line
under the run-mode text when present. Same "still not independently
verified in an actual browser" caveat as the rest of this component
applies here too.
