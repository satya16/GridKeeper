"""Optional read-only local status page for a single node machine --
off by default (Config.local_ui_enabled), since nodes are meant to run
unobtrusively on bulk-enrolled lab machines (see _docs/REQUIREMENTS.md's
school use case). Whoever's sitting at the machine can opt it on with
'grid-node local-ui enable' to see what's running/paused right now.

Deliberately minimal: stdlib http.server only, no new dependency, since
this runs on every enrolled machine. Read-only by design -- no controls
here; pausing/resuming stays a hub-dashboard action. Binds to
127.0.0.1 only, never the LAN, so enabling it never exposes anything to
other machines.

Reuses dashboard.css's color tokens (hub/app/static/dashboard.css)
for a consistent look, inlined here since the node has no static-file
serving of its own.
"""

import html
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger("grid_node.local_ui")

_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #0f1115; --card: #171a21; --border: #2a2e38; --text: #e6e8eb;
  --muted: #8a8f98; --accent: #4f8cff; --ok: #3ecf8e; --warn: #f2a93c; --err: #f2545b;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
header { padding: 1rem 1.5rem; border-bottom: 1px solid var(--border); }
header h1 { font-size: 1.15rem; margin: 0; }
.muted { color: var(--muted); font-size: 0.85rem; }
main { padding: 1rem 1.5rem; max-width: 640px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 1rem; margin-bottom: 1rem; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.4rem; }
.dot.online { background: var(--ok); } .dot.offline { background: var(--muted); }
.dot.warn { background: var(--warn); }
.backend-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--muted); margin-bottom: 0.35rem; }
.task-row { display: flex; justify-content: space-between; font-size: 0.85rem; padding: 0.15rem 0; }
.progress { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; margin-top: 2px; }
.progress > div { height: 100%; background: var(--accent); }
.metric-row { display: flex; justify-content: space-between; font-size: 0.9rem; padding: 0.2rem 0; }
"""


class StateBox:
    """The asyncio side only ever replaces `snapshot` wholesale (never
    mutates it in place); the HTTP handler thread only ever reads it.
    A single reference reassignment is atomic under the GIL, so this
    needs no lock -- just the "replace, don't mutate" discipline."""

    def __init__(self, node_name: str, hub_url: str) -> None:
        self.snapshot: dict = {
            "node_name": node_name,
            "hub_url": hub_url,
            "connected": False,
            "backends": {},
            "metrics": {},
            "schedule_enabled": False,
            "schedule_running": True,
        }

    def update(self, **changes) -> None:
        self.snapshot = {**self.snapshot, **changes}


def _pct(fraction) -> str:
    try:
        return f"{round((fraction or 0) * 100)}%"
    except TypeError:
        return "0%"


def _render_backend(name: str, status: dict) -> str:
    title = html.escape(name.upper())
    if "error" in status:
        return (
            f'<div class="backend-title">{title}</div>'
            f'<div class="task-row muted">error: {html.escape(str(status["error"]))}</div>'
        )

    slots = status.get("slots", [])
    if not slots:
        rows = '<div class="task-row muted">no tasks reported</div>'
    else:
        parts = []
        for s in slots:
            label = html.escape(str(s.get("id", "")))
            state = html.escape(str(s.get("status", "unknown")))
            project = s.get("project")
            project_html = f" ({html.escape(str(project))})" if project else ""
            progress = _pct(s.get("progress"))
            parts.append(
                f'<div class="task-row"><span>{label} — {state}{project_html}</span>'
                f"<span>{progress}</span></div>"
                f'<div class="progress"><div style="width:{progress}"></div></div>'
            )
        rows = "".join(parts)

    return f'<div class="backend-title">{title}</div>{rows}'


def render_page(state: dict) -> str:
    node_name = html.escape(str(state.get("node_name", "")))
    hub_url = html.escape(str(state.get("hub_url", "")))
    connected = bool(state.get("connected"))
    conn_dot = "online" if connected else "offline"
    conn_label = "connected" if connected else "disconnected"

    backends = state.get("backends", {})
    if backends:
        backend_html = "".join(f'<div class="card">{_render_backend(n, s)}</div>' for n, s in backends.items())
    else:
        backend_html = '<div class="card muted">no backends detected on this machine</div>'

    metrics = state.get("metrics", {})
    metric_rows = "".join(
        f'<div class="metric-row"><span>{html.escape(label)}</span><span>{value}</span></div>'
        for label, value in (
            ("CPU", _pct((metrics.get("cpu_percent") or 0) / 100)),
            ("RAM", _pct((metrics.get("ram_percent") or 0) / 100)),
            (
                "Temperature",
                f"{metrics['temperature_c']:.0f}°C" if metrics.get("temperature_c") is not None else "n/a",
            ),
        )
    )

    if state.get("schedule_enabled"):
        schedule_dot = "online" if state.get("schedule_running", True) else "warn"
        schedule_label = "folding on schedule" if state.get("schedule_running", True) else "paused by schedule"
    else:
        schedule_dot, schedule_label = "online", "no schedule restriction"

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{node_name or "Grid Node"} — status</title>
<meta http-equiv="refresh" content="10">
<style>{_STYLE}</style>
</head><body>
<header>
  <h1>{node_name or "Grid Node"}</h1>
  <div class="muted"><span class="dot {conn_dot}"></span>{conn_label} to {hub_url}</div>
</header>
<main>
  <div class="card">
    <div class="backend-title">Schedule</div>
    <div class="task-row"><span><span class="dot {schedule_dot}"></span>{schedule_label}</span></div>
  </div>
  <div class="card">
    <div class="backend-title">System</div>
    {metric_rows}
  </div>
  {backend_html}
</main>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    state_box: StateBox

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] not in ("/", ""):
            self.send_response(404)
            self.end_headers()
            return
        body = render_page(self.state_box.snapshot).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        logger.debug(format, *args)


def start(port: int, state_box: StateBox) -> ThreadingHTTPServer:
    """Binds to 127.0.0.1 only -- never the LAN. Runs the server on a
    daemon thread so it never blocks process exit."""
    handler_cls = type("BoundLocalUIHandler", (_Handler,), {"state_box": state_box})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, name="grid-node-local-ui", daemon=True)
    thread.start()
    logger.info("local status page: http://127.0.0.1:%d/", port)
    return server
