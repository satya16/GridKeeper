import asyncio
import json
import logging

import websockets

from . import local_ui
from . import metrics as metrics_mod
from . import schedule as schedule_mod
from .backends import boinc, fah
from .config import Config

logger = logging.getLogger("grid_node")

BACKENDS = {"boinc": boinc, "fah": fah}

MIN_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0


def _ws_url(hub_url: str, node_id: str, token: str) -> str:
    ws_base = hub_url.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_base.rstrip('/')}/ws/node?node_id={node_id}&token={token}"


def detect_backends() -> list[str]:
    return [name for name, mod in BACKENDS.items() if mod.is_available()]


def collect_status(active_backends: list[str]) -> dict:
    status = {}
    for name in active_backends:
        try:
            status[name] = BACKENDS[name].get_status()
        except Exception as e:
            logger.warning("failed to get %s status: %s", name, e)
            status[name] = {"error": str(e)}
    return status


async def _execute_command(frame: dict) -> dict:
    backend = frame.get("backend")
    action = frame.get("action")
    payload = frame.get("payload", {})

    mod = BACKENDS.get(backend)
    if mod is None:
        return {"status": "error", "result": {"error": f"unknown backend '{backend}'"}}
    handler = mod.ACTIONS.get(action)
    if handler is None:
        return {"status": "error", "result": {"error": f"unknown action '{action}' for backend '{backend}'"}}

    try:
        result = await asyncio.to_thread(handler, payload)
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.warning("command %s.%s failed: %s", backend, action, e)
        return {"status": "error", "result": {"error": str(e)}}


async def _status_loop(
    ws,
    config: Config,
    active_backends: list[str],
    policy_holder: schedule_mod.PolicyHolder,
    state_box: local_ui.StateBox | None,
) -> None:
    while True:
        status = collect_status(active_backends)
        try:
            metrics = metrics_mod.collect()
        except Exception as e:
            logger.warning("failed to collect system metrics: %s", e)
            metrics = {}
        await ws.send(json.dumps({"type": "status", "backends": status, "metrics": metrics}))
        if state_box is not None:
            policy = policy_holder.get()
            state_box.update(
                connected=True,
                backends=status,
                metrics=metrics,
                schedule_enabled=policy.enabled,
                schedule_running=schedule_mod.should_run(policy),
            )
        await asyncio.sleep(config.poll_interval_seconds)


async def _command_loop(ws, policy_holder: schedule_mod.PolicyHolder, active_backends: list[str]) -> None:
    async for raw in ws:
        try:
            frame = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("received non-JSON frame from hub, ignoring")
            continue

        frame_type = frame.get("type")

        if frame_type == "command":
            command_id = frame.get("command_id")
            logger.info("executing command %s: %s.%s", command_id, frame.get("backend"), frame.get("action"))
            result = await _execute_command(frame)
            await ws.send(json.dumps({"type": "command_result", "command_id": command_id, **result}))

        elif frame_type == "schedule":
            policy = schedule_mod.SchedulePolicy.from_dict(frame.get("policy") or {})
            logger.info("received schedule policy: %s", policy.to_dict())
            policy_holder.set(policy)
            if "boinc" in active_backends:
                try:
                    await asyncio.to_thread(boinc.apply_schedule, policy.to_dict())
                except Exception as e:
                    logger.warning("failed to apply BOINC schedule: %s", e)

        else:
            logger.warning("unknown frame type from hub: %r", frame_type)


async def _fah_schedule_loop(policy_holder: schedule_mod.PolicyHolder) -> None:
    """FAH has no native idle/hours scheduling, unlike BOINC (see
    backends/boinc.py apply_schedule), so this loop enforces it directly by
    pausing/unpausing all slots. Re-checks every 60s even without a policy
    change, since the clock and idle state move on their own."""
    last_should_run: bool | None = None
    while True:
        policy = policy_holder.get()
        want_running = schedule_mod.should_run(policy)
        if want_running != last_should_run:
            logger.info("FAH schedule: %s", "resume" if want_running else "pause (outside schedule)")
            try:
                await asyncio.to_thread(fah.unpause_all if want_running else fah.pause_all)
            except Exception as e:
                logger.warning("failed to apply FAH schedule: %s", e)
            last_should_run = want_running
        await policy_holder.wait_for_change(timeout=60)


async def run(config: Config) -> None:
    active_backends = detect_backends()
    if active_backends:
        logger.info("active backends: %s", ", ".join(active_backends))
    else:
        logger.warning("neither BOINC nor FAH detected on this machine -- node will report empty status")

    url = _ws_url(config.hub_url, config.node_id, config.token)
    backoff = MIN_BACKOFF_SECONDS
    # Survives reconnects (created outside the connection loop) so a
    # schedule already received keeps being enforced across drops.
    policy_holder = schedule_mod.PolicyHolder()

    state_box = None
    if config.local_ui_enabled:
        state_box = local_ui.StateBox(config.name, config.hub_url)
        local_ui.start(config.local_ui_port, state_box)

    # Runs independently of the WebSocket connection lifecycle -- a network
    # blip must not stop schedule enforcement, so this is NOT part of the
    # per-connection asyncio.gather() below (which gets torn down on every
    # reconnect).
    background_tasks = []
    if "fah" in active_backends:
        background_tasks.append(asyncio.create_task(_fah_schedule_loop(policy_holder)))

    try:
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    logger.info("connected to %s as '%s'", config.hub_url, config.name)
                    backoff = MIN_BACKOFF_SECONDS
                    await asyncio.gather(
                        _status_loop(ws, config, active_backends, policy_holder, state_box),
                        _command_loop(ws, policy_holder, active_backends),
                    )
            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning("connection lost (%s); reconnecting in %.1fs", e, backoff)
                if state_box is not None:
                    state_box.update(connected=False)
            except Exception:
                logger.exception("unexpected error in node loop; reconnecting in %.1fs", backoff)
                if state_box is not None:
                    state_box.update(connected=False)

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
    finally:
        for task in background_tasks:
            task.cancel()
