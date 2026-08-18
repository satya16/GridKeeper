from grid_worker import local_ui


def _base_state(**overrides) -> dict:
    state = {
        "worker_name": "lab-pc-04",
        "manager_url": "wss://grid.example.com",
        "connected": True,
        "backends": {},
        "metrics": {"cpu_percent": 12.3, "ram_percent": 45.6, "temperature_c": 52.1},
        "schedule_enabled": False,
        "schedule_running": True,
    }
    state.update(overrides)
    return state


def test_render_page_includes_worker_name_and_connection_state():
    page = local_ui.render_page(_base_state())
    assert "lab-pc-04" in page
    assert "connected" in page
    assert "wss://grid.example.com" in page


def test_render_page_shows_disconnected():
    page = local_ui.render_page(_base_state(connected=False))
    assert "disconnected" in page


def test_render_page_escapes_worker_reported_strings():
    """Backend project names / worker names are worker-reported and
    untrusted, same threat model as dashboard.js -- must be escaped."""
    state = _base_state(
        worker_name="<script>alert(1)</script>",
        backends={"boinc": {"slots": [{"id": "0", "status": "running", "project": "<img src=x>", "progress": 0.5}]}},
    )
    page = local_ui.render_page(state)
    assert "<script>alert(1)</script>" not in page
    assert "<img src=x>" not in page
    assert "&lt;script&gt;" in page


def test_render_page_no_backends_detected():
    page = local_ui.render_page(_base_state(backends={}))
    assert "no backends detected" in page


def test_render_page_backend_error_shown():
    page = local_ui.render_page(_base_state(backends={"boinc": {"error": "boinccmd timed out"}}))
    assert "boinccmd timed out" in page


def test_render_page_backend_slots_shown_with_progress():
    page = local_ui.render_page(
        _base_state(backends={"fah": {"slots": [{"id": "", "status": "RUN", "project": "17106", "progress": 0.425}]}})
    )
    assert "RUN" in page
    assert "17106" in page
    assert "42%" in page or "43%" in page  # round((0.425)*100)


def test_render_page_schedule_paused_shows_warn():
    page = local_ui.render_page(_base_state(schedule_enabled=True, schedule_running=False))
    assert "paused by schedule" in page


def test_render_page_no_schedule_restriction():
    page = local_ui.render_page(_base_state(schedule_enabled=False))
    assert "no schedule restriction" in page


def test_state_box_update_replaces_wholesale():
    box = local_ui.StateBox("lab-pc-04", "wss://grid.example.com")
    box.update(connected=True, metrics={"cpu_percent": 1.0})
    assert box.snapshot["connected"] is True
    assert box.snapshot["metrics"] == {"cpu_percent": 1.0}
    assert box.snapshot["worker_name"] == "lab-pc-04"  # untouched fields survive


def test_start_serves_rendered_page_over_real_http():
    import urllib.request

    box = local_ui.StateBox("lab-pc-04", "wss://grid.example.com")
    box.update(connected=True)
    server = local_ui.start(0, box)  # port 0 -> OS picks a free port
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
            body = resp.read().decode("utf-8")
        assert "lab-pc-04" in body
        assert "connected" in body
    finally:
        server.shutdown()
        server.server_close()


def test_start_returns_404_for_unknown_path():
    import urllib.error
    import urllib.request

    box = local_ui.StateBox("lab-pc-04", "wss://grid.example.com")
    server = local_ui.start(0, box)
    try:
        port = server.server_address[1]
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
        server.server_close()
