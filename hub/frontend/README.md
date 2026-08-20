# GridKeeper dashboard (frontend)

The hub's admin dashboard -- React + [Ant Design](https://ant.design/),
built with Vite. Replaced an earlier server-rendered Jinja2 + vanilla-JS
version on 2026-08-18; see
[`_docs/knowledge-graph/dashboard-ui.md`](../../_docs/knowledge-graph/dashboard-ui.md)
in the repo root for why and what changed.

Talks to the FastAPI backend (`hub/app/`) purely over REST -- polling,
not a live WebSocket from the browser's side (the hub's own node-facing
WebSocket is unrelated). Auth is a session cookie set by `POST
/api/login`; `LoginForm.jsx` renders until that succeeds, then every
subsequent `fetch()` just carries the cookie automatically.

## Build for the hub to serve

```bash
npm install
npm run build
```

Outputs straight into `../app/static/dist/` (see `vite.config.js`'s
`build.outDir`) -- that's what `hub/app/main.py`'s `/` route serves.
Not committed (`app/static/dist/` is gitignored); run this after
`git pull`ing frontend changes, or it'll 500 with a clear error telling
you to.

## Dev mode (hot reload, no rebuild-per-change)

```bash
npm run dev
```

Proxies `/api/*` to `http://127.0.0.1:8000` (see `vite.config.js`'s
`server.proxy`) -- run the hub separately on port 8000 as usual, then
use the Vite dev server's own URL (it'll print one, typically
`http://localhost:5173`) instead of the hub's port while developing.

## Verify against a real browser

```bash
GRIDKEEPER_ADMIN_PASSWORD=<yours> npm run verify
```

Runs `scripts/verify.mjs`: loads the dashboard in headless Chromium
(Playwright, already a devDependency here), checks for console/page
errors, confirms the BOINC/FAH collapsible forms actually open, and
saves `verify-screenshot.png` (gitignored) for a visual check. It can't
tell you if something *looks* good, only that it *rendered without
breaking*; look at the screenshot for the rest.

Needs Chromium installed once: `npx playwright install chromium` (falls
back to a system install if `--with-deps` isn't usable without sudo, as
in this environment).
