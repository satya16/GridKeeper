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

**Multi-page nav added 2026-08-19** (was one long scrolling page — user
request, once there were enough sections to want to jump between them
directly): `App.jsx` now renders an antd `Layout` with a `Layout.Sider`
+ `Menu` (Fleet / Credentials / Metrics, in that order, plain `page`
React state -- no router library, not needed for a single login-gated
page with nothing to deep-link). `pages/FleetPage.jsx` further splits
into its own `Tabs`: Discovery, Machines, Schedule. "New pairing token"
moved from the old global `Header.jsx` into `DiscoverySection.jsx`
itself, since it's pairing-specific, not a global action — `Header.jsx`
is now just the persistent top bar (hamburger toggle, title, logout).

Real bug found via Playwright, not guessed: `Layout.Sider`'s
`breakpoint` prop only auto-*shrinks* its width at that viewport size --
reading `node_modules/antd/es/layout/style/sider.js` confirms it's
`position: relative` unconditionally, so it does NOT become an overlay
on its own. Opening the sider on a narrow screen therefore pushed page
content sideways off-viewport (real horizontal overflow, caught by the
same 375px Playwright pass from the mobile-layout fix below) rather
than floating over it like a normal mobile nav drawer. Fixed with a
media-query override (`App.css`, `max-width: 767px`) making
`.ant-layout-sider` `position: fixed` + a click-to-dismiss backdrop
(`.sider-backdrop`, rendered by `App.jsx`) below that width; picking a
menu item also auto-closes the sider below the same breakpoint
(`MOBILE_BREAKPOINT_PX` in `App.jsx`, kept in sync with the CSS value
by comment, not by a shared constant -- small enough surface that
splitting it into a shared file wasn't worth it). Verified in both
states (collapsed and open-as-overlay) at 375px and at 1400px desktop
via Playwright screenshots -- no horizontal overflow either way, sider
correctly floats over content rather than pushing it, real production
node data (a real attached BOINC project, real FAH slot) renders
correctly on the Machines tab post-restructure.

**Brand moved into the sider 2026-08-19** (same day, follow-up): "GridKeeper"
now sits in the `Sider`'s own top-left corner (`.sider-brand` in
`App.css`, height-matched to `Layout.Header`'s default 64px so the two
rows align), above the nav `Menu`, instead of in the content-side
header -- the standard admin-layout pattern (Ant Design Pro's own
reference layout does exactly this). `Header.jsx` is now just the
hamburger toggle + logout, title removed. Worth remembering: "hub" here
means this component's *role* (vs. node), not a rename of the product
-- the brand shown is still "GridKeeper", not "GridHub".

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

**No separate header bar; every page is a Tabs component 2026-08-19**
(same day, second follow-up): user feedback was that a distinct colored
strip above each page's own tabs read as "one bar too many," and that
Credentials/Metrics (no sub-tabs of their own) should be structurally
consistent with Fleet rather than a special-cased plain row. Landed on
antd's actual primitive for this -- `Tabs`' `tabBarExtraContent` prop
(`{left, right}`, confirmed by reading `@rc-component/tabs`' type defs,
which is what antd's `Tabs` wraps) -- so the sider toggle, theme toggle,
and logout button all live directly in whichever page's own tab bar
row, not a separate `Layout.Header`. Credentials and Metrics each got
wrapped in a single-tab `Tabs` (labelled "Credentials"/"Metrics") purely
so they share this same mechanism -- `App.jsx` builds one
`tabBarExtraContent` object and passes it to all three pages'
`Tabs`/`FleetPage`, so the row is identical everywhere. `.page-topbar`
(the earlier special-case CSS for tab-less pages) removed entirely as
now-dead code.

**Light/dark theme toggle added same day**: `main.jsx`'s `Root`
component now owns `themeMode` state (persisted to
`localStorage['gridkeeper-theme']`), switching antd's `ConfigProvider`
between `theme.darkAlgorithm`/`theme.defaultAlgorithm` plus 5 base
tokens (bg/container/border/text/textSecondary) -- semantic colors
(accent/success/warning/error) are deliberately identical in both,
since they're only ever used as small fills (status dots, progress
bars), not body text, so they don't need a second contrast-validated
set. Critically, this app has real custom CSS beyond what antd's
algorithm reaches (App.css's dots/task-rows/chart SVGs, plus
`LineChart.jsx`'s hand-drawn SVG stroke/fill colors) -- `index.css` now
defines the same palette as CSS variables (`--gk-bg`, `--gk-card-bg`,
`--gk-border`, `--gk-text`, `--gk-muted`, `--gk-tooltip-bg`,
`--gk-chart-point-ring`) under `:root`/`:root[data-theme="light"]`,
toggled by setting `data-theme` on `<html>`; App.css and LineChart.jsx's
inline SVG `stroke`/`fill` attributes were converted from hardcoded hex
to `var(--gk-*)` (confirmed CSS custom properties work fine as SVG
presentation-attribute values for inline SVG in an HTML document).

Real bug found and fixed via screenshot, not assumed: `Layout.Sider`
has its own `siderBg` component token (`node_modules/antd/es/layout/
style/index.js`) that does **not** follow the global algorithm --
defaults to a fixed navy (`#001529`) regardless of light/dark, so
toggling to light mode left the sider still dark while its own text
(via `var(--gk-text)`, which *did* follow the toggle) went
light-mode-dark-on-dark and became nearly unreadable. Fix: antd's
`Layout.Sider` and `Menu` both accept their own `theme` prop
(`"dark"`/`"light"`, conveniently the same strings as this app's
`themeMode` state) independent of `ConfigProvider`'s algorithm --
passing `theme={themeMode}` to both makes the sider genuinely follow
the toggle. Verified via Playwright in both themes, at both viewport
sizes, plus a toggle-then-reload check confirming `localStorage`
persistence actually works.
