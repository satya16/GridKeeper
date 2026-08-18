import argparse
import asyncio
import json
import logging
import platform
import sys
import urllib.error
import urllib.request

from . import worker, pairing
from .config import Config, config_path


def _http_post_json(url: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"enroll failed: HTTP {e.code} - {detail}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"enroll failed: could not reach {url}: {e.reason}") from e


def cmd_enroll(args: argparse.Namespace) -> None:
    active_backends = worker.detect_backends()
    resp = _http_post_json(
        f"{args.manager.rstrip('/')}/api/enroll",
        {
            "pairing_token": args.token,
            "name": args.name,
            "os_name": platform.system().lower(),
            "backends": active_backends,
        },
    )
    cfg = Config(
        manager_url=args.manager,
        worker_id=resp["worker_id"],
        token=resp["bearer_token"],
        name=args.name,
    )
    cfg.save()
    print(f"Enrolled as '{args.name}' (worker id {resp['worker_id']}).")
    print(f"Config written to {config_path()}.")
    print(f"Detected backends: {', '.join(active_backends) or '(none)'}")
    print("Start the worker with: grid-worker run")


def cmd_run(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger("grid_worker")
    try:
        cfg = Config.load()
    except FileNotFoundError:
        logger.info("no config found -- entering pairing mode (LAN discovery + 6-digit code)")
        cfg = pairing.wait_for_pairing(worker.detect_backends())
        logger.info("paired as '%s' -- starting normally", cfg.name)
    asyncio.run(worker.run(cfg))


def cmd_local_ui(args: argparse.Namespace) -> None:
    try:
        cfg = Config.load()
    except FileNotFoundError:
        raise SystemExit("not yet paired -- run 'grid-worker enroll' or 'grid-worker run' first") from None

    if args.local_ui_action == "enable":
        cfg.local_ui_enabled = True
        if args.port is not None:
            cfg.local_ui_port = args.port
        cfg.save()
        print(f"Local status page enabled on port {cfg.local_ui_port}.")
        print("Takes effect next time 'grid-worker run' starts (or restart it now).")
        print(f"Will be reachable at: http://127.0.0.1:{cfg.local_ui_port}/")
    elif args.local_ui_action == "disable":
        cfg.local_ui_enabled = False
        cfg.save()
        print("Local status page disabled.")
    else:  # status
        state = "enabled" if cfg.local_ui_enabled else "disabled"
        print(f"Local status page: {state} (port {cfg.local_ui_port}).")


def cmd_status(args: argparse.Namespace) -> None:
    try:
        cfg = Config.load()
        print(f"Paired as '{cfg.name}' (worker id {cfg.worker_id}) with manager {cfg.manager_url}.")
        print(f"Config: {config_path()}")
        return
    except FileNotFoundError:
        pass

    code = pairing.read_pending_code()
    if code:
        print(f"Not yet paired. Current pairing code: {code}")
        print("(only valid while 'grid-worker run' is active and waiting to be paired)")
    else:
        print("Not yet paired, and no worker is currently waiting for pairing.")
        print("Run 'grid-worker run' to enter pairing mode, or use 'grid-worker enroll' for manual/token pairing.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="grid-worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enroll_parser = subparsers.add_parser("enroll", help="Register this machine with a grid-manager using a pairing token")
    enroll_parser.add_argument("--manager", required=True, help="Manager base URL, e.g. http://grid-manager:8000")
    enroll_parser.add_argument("--token", required=True, help="One-time pairing token from the dashboard")
    enroll_parser.add_argument("--name", required=True, help="Display name for this machine")
    enroll_parser.set_defaults(func=cmd_enroll)

    run_parser = subparsers.add_parser(
        "run", help="Run the worker; auto-enters LAN pairing mode first if not yet paired"
    )
    run_parser.set_defaults(func=cmd_run)

    status_parser = subparsers.add_parser("status", help="Show pairing state / current pairing code")
    status_parser.set_defaults(func=cmd_status)

    local_ui_parser = subparsers.add_parser(
        "local-ui", help="Enable/disable this machine's local read-only status page (off by default)"
    )
    local_ui_parser.add_argument("local_ui_action", choices=["enable", "disable", "status"])
    local_ui_parser.add_argument("--port", type=int, default=None, help="Port for 'enable' (default: 8420)")
    local_ui_parser.set_defaults(func=cmd_local_ui)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
