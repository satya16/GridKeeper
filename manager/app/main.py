import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse

from . import auth
from .api import workers as workers_api
from .api import discovery as discovery_api
from .api import pairing as pairing_api
from .api import metrics as metrics_api
from .api import schedule as schedule_api
from .db import SessionLocal, init_db, utcnow
from .discovery import registry as discovery_registry
from .metrics_store import store as metrics_store
from .ws_manager import manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("grid_manager")

_APP_DIR = os.path.dirname(__file__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    await discovery_registry.start()
    yield
    await discovery_registry.stop()


app = FastAPI(title="Grid Manager", lifespan=_lifespan)
app.include_router(workers_api.router)
app.include_router(pairing_api.router)
app.include_router(discovery_api.router)
app.include_router(schedule_api.router)
app.include_router(metrics_api.router)

app.mount("/static", StaticFiles(directory=os.path.join(_APP_DIR, "static")), name="static")

_DASHBOARD_INDEX_HTML = os.path.join(_APP_DIR, "static", "dist", "index.html")


@app.get("/", response_class=HTMLResponse)
def dashboard(_admin: str = Depends(auth.require_admin)) -> HTMLResponse:
    # Served from the React+Ant Design build's output (manager/frontend/,
    # built via `npm run build` into static/dist/) rather than a Jinja2
    # template -- see knowledge-graph/dashboard-ui.md. The auth gate is
    # unchanged: HTTP Basic on this route, same as every /api/* route, so
    # the browser's native Basic-Auth challenge covers both the page load
    # and the SPA's own same-origin fetch() calls with no extra wiring.
    if not os.path.exists(_DASHBOARD_INDEX_HTML):
        raise HTTPException(
            status_code=500,
            detail="Dashboard not built -- run 'npm run build' in manager/frontend/ first.",
        )
    with open(_DASHBOARD_INDEX_HTML) as f:
        return HTMLResponse(f.read())


@app.websocket("/ws/worker")
async def worker_ws(websocket: WebSocket) -> None:
    worker_id = websocket.query_params.get("worker_id")
    token = websocket.query_params.get("token")
    await websocket.accept()

    if not worker_id or not token:
        await websocket.send_text(json.dumps({"type": "error", "detail": "missing worker_id or token"}))
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        worker = db.get(workers_api.Worker, worker_id)
        if worker is None or not auth.verify_token(token, worker.token_hash):
            await websocket.send_text(json.dumps({"type": "error", "detail": "unauthorized"}))
            await websocket.close(code=4401)
            return

        await manager.connect(worker_id, websocket)
        worker.last_seen_at = utcnow()
        db.commit()
        logger.info("worker '%s' (%s) connected", worker.name, worker_id)

        if worker.schedule_json:
            await websocket.send_text(json.dumps({"type": "schedule", "policy": json.loads(worker.schedule_json)}))

        try:
            while True:
                raw = await websocket.receive_text()
                frame = json.loads(raw)
                frame_type = frame.get("type")

                if frame_type == "status":
                    worker.last_seen_at = utcnow()
                    worker.last_status_json = json.dumps(frame.get("backends", {}))
                    db.commit()
                    metrics_store.record(worker_id, frame.get("metrics") or {})
                elif frame_type == "heartbeat":
                    worker.last_seen_at = utcnow()
                    db.commit()
                elif frame_type == "command_result":
                    command_id = frame.get("command_id")
                    if command_id:
                        manager.resolve_pending(
                            command_id,
                            {"status": frame.get("status", "error"), "result": frame.get("result", {})},
                        )
                else:
                    logger.warning("unknown frame type from worker '%s': %r", worker.name, frame_type)
        except WebSocketDisconnect:
            pass
        finally:
            await manager.disconnect(worker_id, websocket)
            logger.info("worker '%s' (%s) disconnected", worker.name, worker_id)
    finally:
        db.close()
