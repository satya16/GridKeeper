"""Rough whole-system power draw estimate for the hub's Power tab.

This is deliberately not a real power reading (no RAPL/hardware sensor
support -- too inconsistent across the mixed lab hardware this project
targets). It's a linear interpolation between a configured idle wattage
and max wattage, scaled by the `cpu_percent` metric already collected in
metrics.py. Good enough for a rough electricity-cost projection, not a
wall-meter replacement.
"""


def estimate_watts(cpu_percent: float | None, idle_watts: float, max_watts: float) -> float | None:
    if cpu_percent is None:
        return None
    clamped = max(0.0, min(100.0, cpu_percent))
    return idle_watts + (clamped / 100.0) * (max_watts - idle_watts)
