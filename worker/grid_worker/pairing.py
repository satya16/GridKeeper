"""Unpaired-state handling: generates a 6-digit pairing code, advertises
this machine on the LAN via mDNS so the grid-manager dashboard can discover
it, and runs a tiny local HTTP listener the manager dials directly to
verify the code and hand over a bearer token.

This has not been exercised against a live network/zeroconf install in
the environment this was written in (no working Python venv was
available) -- the mDNS registration fields and async browsing counterpart
in manager/app/discovery.py match python-zeroconf's documented API, but
double check service registration actually shows up in `avahi-browse` (or
equivalent) the first time you run this for real.
"""

import http.server
import json
import logging
import platform
import secrets
import socket
import threading
import time

from zeroconf import ServiceInfo, Zeroconf

from .config import Config, config_path

logger = logging.getLogger("grid_worker.pairing")

SERVICE_TYPE = "_grid-worker._tcp.local."
CODE_TTL_SECONDS = 600
MAX_ATTEMPTS = 5
ATTEMPT_THROTTLE_SECONDS = 1.0
STILL_WAITING_LOG_INTERVAL_SECONDS = 60

PAIRING_CODE_FILE = config_path().parent / "pairing_code.txt"


def read_pending_code() -> str | None:
    try:
        return PAIRING_CODE_FILE.read_text().strip()
    except FileNotFoundError:
        return None


def _local_ip() -> str:
    """Best-effort LAN IP: opens a UDP 'connection' to a public address
    (sends nothing) purely to see which local interface the OS would
    route through, then reads that interface's address back."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class PairingSession:
    def __init__(self, name: str, os_name: str, backends: list[str]):
        self.name = name
        self.os_name = os_name
        self.backends = backends
        self.done = threading.Event()
        self.result: Config | None = None

        self._lock = threading.Lock()
        self._code = ""
        self._code_generated_at = 0.0
        self._attempts = 0
        self._verified = False
        self._regenerate_code()

    def _regenerate_code(self) -> None:
        self._code = f"{secrets.randbelow(1_000_000):06d}"
        self._code_generated_at = time.monotonic()
        self._attempts = 0
        self._verified = False
        self._write_code_file()
        banner = (
            f"=== Pairing code: {self._code} "
            f"(valid {CODE_TTL_SECONDS // 60} min) "
            "-- enter this in the Grid Manager dashboard ==="
        )
        logger.info(banner)
        print(f"\n{banner}\n", flush=True)

    def _write_code_file(self) -> None:
        try:
            PAIRING_CODE_FILE.parent.mkdir(parents=True, exist_ok=True)
            PAIRING_CODE_FILE.write_text(f"{self._code}\n")
        except OSError as e:
            logger.warning("could not write pairing code file: %s", e)

    def _expired(self) -> bool:
        return time.monotonic() - self._code_generated_at > CODE_TTL_SECONDS

    def verify(self, submitted_code: str) -> bool:
        with self._lock:
            if self._expired() or self._attempts >= MAX_ATTEMPTS:
                self._regenerate_code()
                return False
            if submitted_code == self._code:
                self._verified = True
                return True
            self._attempts += 1
            time.sleep(ATTEMPT_THROTTLE_SECONDS)
            return False

    def complete(self, worker_id: str, bearer_token: str, manager_url: str, name: str | None = None) -> bool:
        with self._lock:
            if not self._verified:
                return False
            cfg = Config(manager_url=manager_url, worker_id=worker_id, token=bearer_token, name=name or self.name)
            cfg.save()
            try:
                PAIRING_CODE_FILE.unlink()
            except OSError:
                pass
            self.result = cfg
            self.done.set()
            return True


class _PairingHTTPServer(http.server.ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], handler_cls: type, session: PairingSession):
        super().__init__(address, handler_cls)
        self.session = session


class _PairingHandler(http.server.BaseHTTPRequestHandler):
    server: _PairingHTTPServer

    def log_message(self, fmt: str, *args) -> None:
        logger.debug("pairing http: " + fmt, *args)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _respond(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        session = self.server.session
        body = self._read_json()

        if self.path == "/pair":
            if session.verify(str(body.get("code", ""))):
                self._respond(
                    200,
                    {
                        "accepted": True,
                        "name": session.name,
                        "os_name": session.os_name,
                        "backends": session.backends,
                    },
                )
            else:
                self._respond(403, {"accepted": False})
            return

        if self.path == "/pair-complete":
            ok = session.complete(
                worker_id=body.get("worker_id", ""),
                bearer_token=body.get("bearer_token", ""),
                manager_url=body.get("manager_url", ""),
                name=body.get("name") or None,
            )
            self._respond(200 if ok else 409, {"ok": ok})
            return

        self._respond(404, {"error": "not found"})


def wait_for_pairing(active_backends: list[str]) -> Config:
    """Blocks (in the calling thread) until an admin pairs this machine
    from the grid-manager dashboard, then returns the resulting Config."""
    hostname = socket.gethostname()
    session = PairingSession(name=hostname, os_name=platform.system().lower(), backends=active_backends)

    httpd = _PairingHTTPServer(("0.0.0.0", 0), _PairingHandler, session)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    zc = Zeroconf()
    local_ip = _local_ip()
    instance_name = f"{hostname}-{secrets.token_hex(2)}"
    info = ServiceInfo(
        SERVICE_TYPE,
        f"{instance_name}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        properties={"hostname": hostname, "backends": ",".join(active_backends)},
        server=f"{hostname}.local.",
    )
    zc.register_service(info)
    logger.info("advertising as '%s' on %s:%d for pairing", instance_name, local_ip, port)

    try:
        while not session.done.wait(timeout=STILL_WAITING_LOG_INTERVAL_SECONDS):
            logger.info("still unpaired -- run 'grid-worker status' on this machine to see the current code")
    finally:
        zc.unregister_service(info)
        zc.close()
        httpd.shutdown()
        httpd.server_close()

    assert session.result is not None
    return session.result
