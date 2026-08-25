"""Backend discovery: any package registered under the `grid_node.backends`
entry-point group is loaded as a backend, including boinc/fah themselves
(registered the same way in this package's own pyproject.toml) -- there is
no special-cased "built-in" path, so a third-party plugin package exercises
exactly the same mechanism.
"""

import logging
from importlib.metadata import entry_points

from . import base

logger = logging.getLogger("grid_node.backends")


def discover_backends() -> dict[str, object]:
    backends: dict[str, object] = {}
    for ep in entry_points(group="grid_node.backends"):
        try:
            module = ep.load()
        except Exception:
            logger.exception("failed to load backend plugin '%s' (%s); skipping", ep.name, ep.value)
            continue
        try:
            base.validate_backend(module)
        except base.InvalidBackend as e:
            logger.error("backend plugin '%s' failed validation, skipping: %s", ep.name, e)
            continue
        if ep.name != module.NAME:
            logger.warning(
                "backend plugin entry-point name '%s' doesn't match module.NAME '%s'; using module.NAME",
                ep.name,
                module.NAME,
            )
        backends[module.NAME] = module
    return backends
