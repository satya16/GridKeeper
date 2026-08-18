"""Schedule policy: hour restrictions + best-effort idle detection.

BOINC has its own mature idle/hours engine (global_prefs_override.xml),
so a BOINC-active worker pushes the policy there once and lets BOINC's own
daemon enforce it -- see backends/boinc.py's apply_schedule(). Folding@home
has no equivalent, so *this* module's should_run() is polled by worker.py
in a loop that pauses/unpauses FAH directly.

Idle detection here (used only for the FAH enforcement loop) shells out to
`loginctl` for systemd-logind's IdleHint across all sessions. This is the
common case on Ubuntu desktop, but not guaranteed: headless machines,
non-systemd distros, or no active login session at all will all fail to
produce a hint. Unverified in this sandbox (no live logind session to test
against) -- it fails open (treats "can't tell" as idle) rather than
silently blocking FAH from ever running just because idle detection isn't
available on a given machine.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import subprocess
from dataclasses import asdict, dataclass

logger = logging.getLogger("grid_worker.schedule")

_LOGINCTL_TIMEOUT_SECONDS = 5.0
_idle_warning_logged = False


@dataclass
class SchedulePolicy:
    enabled: bool = False
    restrict_hours: bool = False
    active_start_hour: int = 22
    active_end_hour: int = 6
    only_when_idle: bool = False
    idle_threshold_minutes: int = 3

    @classmethod
    def from_dict(cls, data: dict) -> "SchedulePolicy":
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            restrict_hours=bool(data.get("restrict_hours", defaults.restrict_hours)),
            active_start_hour=int(data.get("active_start_hour", defaults.active_start_hour)),
            active_end_hour=int(data.get("active_end_hour", defaults.active_end_hour)),
            only_when_idle=bool(data.get("only_when_idle", defaults.only_when_idle)),
            idle_threshold_minutes=int(data.get("idle_threshold_minutes", defaults.idle_threshold_minutes)),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def _within_active_hours(start_hour: int, end_hour: int) -> bool:
    if start_hour == end_hour:
        return True  # no restriction
    now_hour = datetime.datetime.now().hour
    if start_hour < end_hour:
        return start_hour <= now_hour < end_hour
    return now_hour >= start_hour or now_hour < end_hour  # wraps past midnight


def _is_idle() -> bool | None:
    """Best-effort: True/False if systemd-logind can tell us, None if not."""
    global _idle_warning_logged
    try:
        sessions_out = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True,
            text=True,
            timeout=_LOGINCTL_TIMEOUT_SECONDS,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        if not _idle_warning_logged:
            logger.warning("idle detection unavailable (%s) -- treating as idle by default", e)
            _idle_warning_logged = True
        return None

    session_ids = [line.split()[0] for line in sessions_out.splitlines() if line.strip()]
    if not session_ids:
        return True  # nobody logged in

    for session_id in session_ids:
        try:
            hint = subprocess.run(
                ["loginctl", "show-session", session_id, "-p", "IdleHint", "--value"],
                capture_output=True,
                text=True,
                timeout=_LOGINCTL_TIMEOUT_SECONDS,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        if hint == "no":
            return False  # at least one session is actively in use
    return True


def should_run(policy: SchedulePolicy) -> bool:
    if not policy.enabled:
        return True
    if policy.restrict_hours and not _within_active_hours(policy.active_start_hour, policy.active_end_hour):
        return False
    if policy.only_when_idle and _is_idle() is False:
        return False
    return True


class PolicyHolder:
    """Asyncio-only (not thread-safe) holder for the worker's current
    schedule policy: the WebSocket frame handler calls set(), the FAH
    enforcement loop calls get()/wait_for_change()."""

    def __init__(self) -> None:
        self._policy = SchedulePolicy()
        self._changed = asyncio.Event()

    def set(self, policy: SchedulePolicy) -> None:
        self._policy = policy
        self._changed.set()

    def get(self) -> SchedulePolicy:
        return self._policy

    async def wait_for_change(self, timeout: float) -> None:
        try:
            await asyncio.wait_for(self._changed.wait(), timeout=timeout)
        except TimeoutError:
            pass
        finally:
            self._changed.clear()
