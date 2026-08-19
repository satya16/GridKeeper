import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "grid-node" / "config.toml"


def config_path() -> Path:
    override = os.environ.get("GRID_NODE_CONFIG")
    return Path(override) if override else DEFAULT_CONFIG_PATH


@dataclass
class Config:
    hub_url: str  # e.g. "ws://hub-host:8000" or "wss://grid.example.com"
    node_id: str
    token: str
    name: str
    poll_interval_seconds: float = 10.0  # also doubles as the heartbeat cadence
    # Local read-only status page (http://127.0.0.1:<port>/) for whoever's at
    # this machine -- off by default, since nodes are meant to run
    # unobtrusively on bulk-enrolled lab machines. See 'grid-node local-ui'.
    local_ui_enabled: bool = False
    local_ui_port: int = 8420

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_path()
        if not path.exists():
            raise FileNotFoundError(f"no config at {path} -- run 'grid-node enroll' first")
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(
            hub_url=data["hub_url"],
            node_id=data["node_id"],
            token=data["token"],
            name=data["name"],
            poll_interval_seconds=data.get("poll_interval_seconds", 10.0),
            local_ui_enabled=data.get("local_ui_enabled", False),
            local_ui_port=data.get("local_ui_port", 8420),
        )

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f'hub_url = "{self.hub_url}"',
            f'node_id = "{self.node_id}"',
            f'token = "{self.token}"',
            f'name = "{self.name}"',
            f"poll_interval_seconds = {self.poll_interval_seconds}",
            f"local_ui_enabled = {'true' if self.local_ui_enabled else 'false'}",
            f"local_ui_port = {self.local_ui_port}",
        ]
        path.write_text("\n".join(lines) + "\n")
        path.chmod(0o600)  # contains the bearer token
