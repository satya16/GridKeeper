"""Browses the LAN for unpaired grid-worker machines advertising themselves
over mDNS (see worker/grid_worker/pairing.py) and keeps an in-memory list
the dashboard can poll via GET /api/discovery. Nothing here is persisted --
once a worker is paired it stops advertising and simply drops out of this
list on its own.

Like the worker side of this handshake, this has not been run against a
live network in the environment this was written in -- the async
zeroconf API calls (AsyncServiceBrowser / AsyncServiceInfo.async_request)
match the documented python-zeroconf interface, but verify end to end
against a real worker before relying on it.
"""

import asyncio
import logging

from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

logger = logging.getLogger("gridkeeper.discovery")

SERVICE_TYPE = "_grid-worker._tcp.local."
SERVICE_INFO_TIMEOUT_MS = 3000


class DiscoveryRegistry:
    def __init__(self) -> None:
        self._workers: dict[str, dict] = {}
        self._aiozc: AsyncZeroconf | None = None
        self._browser: AsyncServiceBrowser | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._aiozc = AsyncZeroconf()
        self._browser = AsyncServiceBrowser(
            self._aiozc.zeroconf, SERVICE_TYPE, handlers=[self._on_change]
        )
        logger.info("mDNS discovery started, browsing for %s", SERVICE_TYPE)

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.async_cancel()
        if self._aiozc is not None:
            await self._aiozc.async_close()

    def _on_change(self, zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        # zeroconf may invoke this from its own engine thread rather than
        # the FastAPI event loop's thread, so schedule thread-safely
        # instead of assuming asyncio.ensure_future() has a running loop
        # to attach to.
        assert self._loop is not None
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._handle_change(zeroconf, service_type, name, state_change))
        )

    async def _handle_change(self, zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        if state_change is ServiceStateChange.Removed:
            self._workers.pop(name, None)
            return

        info = AsyncServiceInfo(service_type, name)
        found = await info.async_request(zeroconf, SERVICE_INFO_TIMEOUT_MS)
        if not found:
            return

        addresses = info.parsed_addresses()
        if not addresses or info.port is None:
            return

        props = {
            key.decode("utf-8"): value.decode("utf-8")
            for key, value in (info.properties or {}).items()
            if value is not None
        }
        self._workers[name] = {
            "discovery_id": name,
            "hostname": props.get("hostname", name.split(".")[0]),
            "backends": [b for b in props.get("backends", "").split(",") if b],
            "addresses": addresses,
            "port": info.port,
        }

    def list_workers(self) -> list[dict]:
        return list(self._workers.values())

    def get(self, discovery_id: str) -> dict | None:
        return self._workers.get(discovery_id)


registry = DiscoveryRegistry()
