"""In-memory rolling window of system metrics (CPU%, RAM%, temperature,
estimated power draw) per node, for the dashboard's live graphs. Deliberately not persisted to
SQLite -- this is "recent live state," the same spirit as the rest of the
dashboard, not the long-term historical analytics the requirements doc
explicitly puts out of scope for v1. A hub restart just starts the
graphs over.
"""

import collections
import time
from typing import Any

MAX_POINTS_PER_NODE = 360  # ~1 hour at the default 10s node poll interval


class MetricsStore:
    def __init__(self) -> None:
        self._series: dict[str, collections.deque] = {}

    def record(self, node_id: str, metrics: dict[str, Any]) -> None:
        if not metrics:
            return
        series = self._series.setdefault(node_id, collections.deque(maxlen=MAX_POINTS_PER_NODE))
        series.append(
            {
                "t": time.time(),
                "cpu_percent": metrics.get("cpu_percent"),
                "ram_percent": metrics.get("ram_percent"),
                "temperature_c": metrics.get("temperature_c"),
                "estimated_watts": metrics.get("estimated_watts"),
            }
        )

    def history(self, node_id: str) -> list[dict]:
        return list(self._series.get(node_id, []))

    def all_history(self) -> dict[str, list[dict]]:
        return {node_id: list(points) for node_id, points in self._series.items()}


store = MetricsStore()
