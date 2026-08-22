---
id: dashboard-ui
type: component
status: implemented-verified
files:
  - hub/frontend/src
  - hub/app/main.py
relates_to: [hub, pairing, scheduling, metrics, boinc-backend, fah-backend, credentials, users-and-roles, power-estimate]
---

The admin-facing web UI — **React + Ant Design, built with Vite**
(`hub/frontend/`). `npm run build` outputs into `hub/app/static/dist/`
(gitignored), served by `main.py`'s `/` route. See
`hub/frontend/README.md` for build/dev/verify instructions.

Session-cookie auth: `App.jsx` checks `GET /api/session` on load and
renders `LoginForm` until it succeeds; `api.js`'s shared `request()`
helper flips back to the login screen on any 401, not just the initial
check (so a session expiring mid-use, e.g. after a hub restart, doesn't
just silently fail every poll).

REST-polling architecture, componentized: `usePolling()` drives
independent timers per section (nodes/groups every 5s, discovery every
4s, metrics every 7s). Layout: an antd `Layout.Sider` + `Menu` (Fleet /
Credentials / Metrics / Admin Console / Profile — the last two role-
gated, see [users-and-roles](users-and-roles.md)) that collapses to an
80px icon rail on desktop and fully hides behind an overlay+backdrop on
mobile (breakpoint 767px); `FleetPage` further splits into its own tabs
(Discovery / Machines / Schedule, also role-gated). No router library —
plain `page` React state, no deep-linking needed for a single login-
gated page. Every page's own `Tabs` carries the sider toggle, a light/
dark theme toggle (persisted to `localStorage`, antd `ConfigProvider`
algorithm + `--gk-*` CSS custom properties for the app's own SVG/CSS that
antd's algorithm doesn't reach), and logout via `tabBarExtraContent` —
no separate header bar.

Sections: `DiscoverySection` (pair-by-code, see [pairing](pairing.md)),
`FleetScheduleSection` + each `NodeCard`'s own schedule form (see
[scheduling](scheduling.md)), `NodeListSection` (group filter + `NodeCard`
grid), `BoincBlock`/`FahBlock` (per-backend status + controls, see
[boinc-backend](boinc-backend.md)/[fah-backend](fah-backend.md)), and
`MetricsSection`/`LineChart` (see [metrics](metrics.md)). Node
names/project names are node-reported, untrusted strings — React's JSX
text interpolation escapes them by default, no manual escaping needed.

**Verified**, including in a real browser via Playwright
(`hub/frontend/scripts/verify.mjs`, `npm run verify` — loads the real
built dashboard against a running hub+node, checks for console/page
errors, exercises the collapsible forms, screenshots): real node data
renders correctly, forms work, the metrics chart's hover crosshair/
tooltip fires correctly, mobile layout (375px) has no horizontal
overflow, and role-based nav/control gating (see
[users-and-roles](users-and-roles.md)) behaves correctly including
out-of-scope 403 checks. Not yet covered: automated component tests —
`npm run verify`'s browser smoke test is the only automated frontend
check, no unit-test layer.
