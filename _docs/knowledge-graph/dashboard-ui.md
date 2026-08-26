---
id: dashboard-ui
type: component
status: implemented-verified
files:
  - hub/frontend/src
  - hub/app/main.py
relates_to: [hub, pairing, scheduling, metrics, boinc-backend, fah-backend, credentials, users-and-roles, power-estimate, plugin-registry]
---

The admin-facing web UI — **React + MUI, built with Vite**
(`hub/frontend/`). `npm run build` outputs into `hub/app/static/dist/`
(gitignored), served by `main.py`'s `/` route. See
`hub/frontend/README.md` for build/dev/verify instructions.

Rebuilt from Ant Design to MUI on 2026-08-25 (component-library swap +
a genuine corporate-SaaS visual refresh: new indigo-blue palette,
Roboto typography, card elevation, self-hosted via `@fontsource/roboto`
-- not a mechanical restyle). `src/theme.js` builds the MUI theme per
mode from the same palette tokens `index.css`'s `--gk-*` custom
properties use, same pairing antd's `ConfigProvider` tokens had before.
`notistack` (`src/snackbar.js`) replaced antd's `message.*` toast API.
Layout is now a MUI `Drawer` (permanent+icon-rail on desktop, temporary
overlay on mobile, replacing antd's `Layout.Sider`+hand-rolled backdrop)
+ a new shared `PageTabBar` component (MUI `Tabs` + the
`tabBarExtraContent` left/right slots antd's `Tabs` used to provide
natively). All prior functionality carried over 1:1 -- verified via
`hub/frontend/scripts/verify.mjs` (updated for MUI's class names/roles)
plus a real paired test node and a manual pass through every page in
both themes, light/dark and desktop/375px mobile.

Session-cookie auth: `App.jsx` checks `GET /api/session` on load and
renders `LoginForm` until it succeeds; `api.js`'s shared `request()`
helper flips back to the login screen on any 401, not just the initial
check (so a session expiring mid-use, e.g. after a hub restart, doesn't
just silently fail every poll).

REST-polling architecture, componentized: `usePolling()` drives
independent timers per section (nodes/groups every 5s, discovery every
4s, metrics every 7s). Layout: a MUI `Drawer` + nav `List` (Fleet /
Credentials / Metrics / Admin Console / Profile — the last two role-
gated, see [users-and-roles](users-and-roles.md)) that collapses to an
80px icon rail on desktop and fully hides behind an overlay+backdrop on
mobile (breakpoint 767px, MUI's temporary Drawer provides the
overlay+backdrop itself); `FleetPage` further splits into its own tabs
(Discovery / Machines / Schedule, also role-gated). No router library —
plain `page` React state, no deep-linking needed for a single login-
gated page. Every page's own `PageTabBar` carries the sider toggle, a
light/dark theme toggle (persisted to `localStorage`, MUI theme built
per-mode by `theme.js` + `--gk-*` CSS custom properties for the app's
own SVG/CSS that MUI's theme doesn't reach), and logout via
`tabBarExtraContent` — no separate header bar.

Sections: `DiscoverySection` (pair-by-code plus bulk multi-select pairing,
see [pairing](pairing.md)), `FleetScheduleSection` + `GroupActionsSection`
(group/all command dispatch, see [hub](hub.md)) + each `NodeCard`'s own
schedule form (see [scheduling](scheduling.md)), `NodeListSection` (group
filter + `NodeCard` grid), `BoincBlock`/`FahBlock` (per-backend status +
controls, see [boinc-backend](boinc-backend.md)/[fah-backend](fah-backend.md)),
`GenericBackendBlock` (fallback for any backend that isn't boinc/fah —
raw status JSON + an action picker built from `GET /api/backends`, see
[plugin-registry](plugin-registry.md)), and `MetricsSection`/`LineChart`
(see [metrics](metrics.md)). Node names/project names are node-reported,
untrusted strings — React's JSX text interpolation escapes them by
default, no manual escaping needed.

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

`verify.mjs` itself was found stale 2026-08-24 (its `login()` helper still
targeted the single-admin-password prompt from before
[users-and-roles](users-and-roles.md)'s real per-user login existed, so it
had silently never completed a real run since that change) — fixed, and
extended to cover `GroupActionsSection` and the generic backend-driven
credential form; both confirmed rendering real registry data
(`GET /api/backends`) in a real browser against a real hub+node+GIMPS-plugin
session. Also found and fixed a real, pre-existing (not from this session's
other changes — confirmed by reproducing it with those changes stashed
out first) mobile overflow: `.ant-tabs-nav`'s bleed-then-repad margin
trick wasn't re-scaled for the `@media (max-width: 640px)` breakpoint's
reduced `.app-content` padding (`App.css`). The bulk-pairing dialog itself
was exercised via `hub/tests/test_discovery.py` (backend) but not yet
against a real browser with real discovered machines — no multi-machine
LAN available to this session.
