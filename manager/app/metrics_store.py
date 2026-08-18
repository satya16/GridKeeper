"""In-memory rolling window of system metrics (CPU%, RAM%, temperature) per
worker, for the dashboard's live graphs. Deliberately not persisted to
SQLite -- this is "recent live state," the same spirit as the rest of the
dashboard, not the long-term historical analytics the requirements doc
explicitly puts out of scope for v1. A manager restart just starts the
graphs over.
"""

import collections
import time
from typing import Any

MAX_POINTS_PER_WORKER = 360  # ~1 hour at the default 10s worker poll interval


class MetricsStore:
    def __init__(self) -> None:
        self._series: dict[str, collections.deque] = {}

    def record(self, worker_id: str, metrics: dict[str, Any]) -> None:
        if not metrics:
            return
        series = self._series.setdefault(worker_id, collections.deque(maxlen=MAX_POINTS_PER_WORKER))
        series.append(
            {
                "t": time.time(),
                "cpu_percent": metrics.get("cpu_percent"),
                "ram_percent": metrics.get("ram_percent"),
                "temperature_c": metrics.get("temperature_c"),
            }
        )

    def history(self, worker_id: str) -> list[dict]:
        return list(self._series.get(worker_id, []))

    def all_history(self) -> dict[str, list[dict]]:
        return {worker_id: list(points) for worker_id, points in self._series.items()}


store = MetricsStore()
