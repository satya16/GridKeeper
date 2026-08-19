"""System metrics (CPU%, RAM%, temperature) for the dashboard's live graphs.
Uses psutil, which does the actual OS-specific work.

Temperature is Linux-only in practice: psutil.sensors_temperatures() isn't
implemented on macOS/Windows, so it reports None there rather than raising
-- consistent with the rest of this codebase's "degrade gracefully, log
once" approach to platform-specific integrations.
"""

import logging

import psutil

logger = logging.getLogger("grid_node.metrics")

_PREFERRED_TEMP_SENSOR_LABELS = ("coretemp", "k10temp", "cpu_thermal", "acpitz")
_temp_warning_logged = False


def _cpu_temperature_c() -> float | None:
    global _temp_warning_logged
    get_temps = getattr(psutil, "sensors_temperatures", None)
    if get_temps is None:
        return None
    try:
        temps = get_temps()
    except OSError as e:
        if not _temp_warning_logged:
            logger.warning("could not read temperature sensors: %s", e)
            _temp_warning_logged = True
        return None
    if not temps:
        return None

    for label in _PREFERRED_TEMP_SENSOR_LABELS:
        entries = temps.get(label)
        if entries:
            return entries[0].current

    for entries in temps.values():
        if entries:
            return entries[0].current
    return None


def collect() -> dict:
    """cpu_percent is measured against the interval since the last call
    (non-blocking) -- psutil keeps that baseline internally, which lines up
    naturally with this being polled on a fixed interval by _status_loop."""
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": psutil.virtual_memory().percent,
        "temperature_c": _cpu_temperature_c(),
    }
