import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("gridkeeper.ws")


class ConnectionManager:
    """Tracks one live WebSocket per worker_id and lets the REST layer push
    frames (commands, schedule updates, ...) to a specific worker's socket
    if it's currently online."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        # command_id -> future, resolved when the worker reports a result
        self._pending: dict[str, asyncio.Future] = {}

    async def connect(self, worker_id: str, ws: WebSocket) -> None:
        async with self._lock:
            existing = self._connections.get(worker_id)
            self._connections[worker_id] = ws
        if existing is not None and existing is not ws:
            # Same worker reconnected (e.g. after a network blip); drop the stale socket.
            try:
                await existing.close()
            except Exception:
                pass

    async def disconnect(self, worker_id: str, ws: WebSocket) -> None:
        async with self._lock:
            if self._connections.get(worker_id) is ws:
                del self._connections[worker_id]

    def is_online(self, worker_id: str) -> bool:
        return worker_id in self._connections

    def online_worker_ids(self) -> set[str]:
        return set(self._connections.keys())

    async def send_frame(self, worker_id: str, frame: dict[str, Any]) -> bool:
        ws = self._connections.get(worker_id)
        if ws is None:
            return False
        await ws.send_text(json.dumps(frame))
        return True

    def register_pending(self, command_id: str) -> asyncio.Future:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = fut
        return fut

    def resolve_pending(self, command_id: str, result: dict[str, Any]) -> None:
        fut = self._pending.pop(command_id, None)
        if fut is not None and not fut.done():
            fut.set_result(result)

    def drop_pending(self, command_id: str) -> None:
        self._pending.pop(command_id, None)


manager = ConnectionManager()
