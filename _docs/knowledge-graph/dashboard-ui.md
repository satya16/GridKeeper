---
id: dashboard-ui
type: component
status: implemented-verified
files:
  - hub/frontend/src
  - hub/app/main.py
relates_to: [hub, pairing, scheduling, metrics, boinc-backend, fah-backend, credentials]
---

The admin-facing web UI — **React + Ant Design, built with Vite**
(`hub/frontend/`), replacing an earlier server-rendered Jinja2 +
vanilla-JS version on 2026-08-18 (deliberate scope decision: only this
UI moved to React+AntD, not [node-local-ui](node-local-ui.md), which
stays dependency-free by design — see memory). `npm run build` outputs
into `hub/app/static/dist/`, gitignored, served by `main.py`'s `/`
route. See `hub/frontend/README.md` for build/dev/verify instructions.

`LoginForm.jsx` + session-cookie auth added 2026-08-19, replacing HTTP
Basic (see [hub](hub.md) for why) — `App.jsx` checks `GET /api/session`
on load and renders `LoginForm` instead of the dashboard until it
succeeds; `api.js`'s `onUnauthorized` hook (fired by its shared
`request()` helper on any 401, not just that initial check) flips the
app back to the login screen if a session expires mid-use, e.g. after a
hub restart.

Same REST-polling architecture as before, just componentized:
`usePolling()` (a small custom hook) drives independent timers per
section — nodes/groups every 5s (`App.jsx`), discovery every 4s
(`DiscoverySection.jsx`), metrics every 7s (`MetricsSection.jsx`) —
matching the old dashboard.js's separate `setInterval` loops. Sections:
`DiscoverySection` (pair-by-code, see [pairing](pairing.md)),
`FleetScheduleSection` + each `NodeCard`'s own schedule `Collapse`
(both built on the shared `SchedulePolicyForm.jsx`, see
[scheduling](scheduling.md)), `NodeListSection` (group filter +
`NodeCard` grid, group pill → `PUT /api/nodes/{id}/group`),
`BoincBlock.jsx` / `FahBlock.jsx` (per-backend status + controls, see
[boinc-backend](boinc-backend.md) / [fah-backend](fah-backend.md)), and
`MetricsSection.jsx` + `LineChart.jsx` (see [metrics](metrics.md)).

`BoincBlock` has a "Detach" button per project (confirm-gated via
`window.confirm()`) and a collapsed "Attach a project…" `Form` (project
URL + password-masked account key). `FahBlock` shows current
account/cause state and a collapsed "Account & cause…" `Form` (cause
`Select`, options from a static `FAH_CAUSES` list fetched live from
FAH's own API — see [fah-backend](fah-backend.md) — plus fold-anonymously
checkbox and optional username/team/passkey, only non-blank fields
sent). Both credentials (`account_key`, `passkey`) get the same
server-side-only redaction treatment before the hub persists the
command to its audit-log DB — see `hub/app/api/nodes.py`'s
`_SENSITIVE_PAYLOAD_FIELDS`; the dashboard itself always sends the real
value, redaction happens after.

Security-relevant detail carried over unchanged: node names/hostnames
and BOINC project names are node-reported, untrusted strings. React
escapes all of this by default (JSX text interpolation, not
`dangerouslySetInnerHTML`) — the XSS-escaping discipline the old
vanilla-JS version had to do by hand (`escapeHtml()`) is structural here
instead.

**Verified 2026-08-18, including in a real browser** — this closes the
"no display in this sandbox" gap that every previous UI entry in this
knowledge graph (this one, [metrics](metrics.md),
[node-local-ui](node-local-ui.md)) had flagged as its main
unverified risk. `npx playwright install chromium` turned out to work in
this environment (browser binary was already cached from earlier
Playwright-based work) even though `--with-deps` (needs sudo) doesn't;
added `playwright` as a devDependency and `hub/frontend/scripts/
verify.mjs` (`npm run verify`) as a permanent, reusable smoke test —
loads the real built dashboard in headless Chromium against a real
running hub + node, checks for console/page errors, opens both
collapsible forms, saves a screenshot. Confirmed live: real node data
renders correctly (a real FAH work unit's live progress, a real BOINC
error surfaced gracefully), both attach/config forms open and contain
the expected fields, the CPU chart's hover crosshair+tooltip genuinely
fires and renders correct content (chased an apparent flake here for a
while — a stationary synthetic mouse loses hover after ~1.7s due to an
incidental late layout shift unrelated to the chart code; a real user's
continuously-moving mouse would never hit this, confirmed not a logic
bug via direct pointer-event and computed-style inspection). Not yet
covered: automated component tests (no `test/` dir in `frontend/` yet —
`npm run verify`'s browser smoke test is the only automated check right
now, deliberately end-to-end rather than unit-level).

**Mobile layout fixed + verified 2026-08-19**, prompted by a real user
report (overflowing sections, Card titles nearly invisible on a phone).
`verify.mjs` extended with a second, 375px-wide (iPhone SE) browser
context alongside the existing desktop one — checks for horizontal
overflow (`scrollWidth > clientWidth`) and measures every
`.ant-card-head-title`'s rendered width, failing if any non-trivial
title renders under 20px. Two real, distinct bugs found this way, not
guessed from reading CSS alone:
1. `NodeListSection`/`MetricsSection`'s CSS grids used
   `minmax(340px, 1fr)`/`minmax(320px, 1fr)` — a fixed lower bound that
   doesn't shrink below itself, so on a viewport narrower than that the
   grid track (and the whole page) overflowed horizontally. Fixed with
   `minmax(min(340px, 100%), 1fr)`, the standard CSS trick for this.
2. `FleetScheduleSection`'s Card `title` + `extra` genuinely squeezed
   the title down to "Fl…" (measured 33px) on mobile — antd's own head
   layout (`node_modules/antd/es/card/style/index.js`, read directly
   rather than assumed) puts both in one unwrapped flex row where title
   is `flex:1` + ellipsis and extra takes its full natural width via
   `margin-inline-start: auto`; a `flex-wrap` media-query fix on
   `.ant-card-head-wrapper` (added for all cards) helped the other
   cards' *short, dynamic* `extra` (a live "updated HH:MM:SS" string)
   but not this card's unusually long *static* `extra` text, since a
   flex item with `overflow:hidden` gets an automatic min-size of 0 and
   so never gets pushed to a new line on its own. Real fix: that text
   wasn't live status to begin with, so it moved out of `extra` entirely
   into a `Typography.Paragraph` in the card body -- confirmed via
   before/after screenshots, title back to full width (301px).

`verify.mjs`'s auth also had to change with the HTTP-Basic-to-session
switch above: `newContext({ httpCredentials })` no longer applies
anything, since there's no Basic challenge to answer -- it now drives
the real login form (fill password, click "Log in") before running any
checks, on both the desktop and mobile browser contexts.
