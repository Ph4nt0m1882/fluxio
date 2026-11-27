import json
import pytest
import websockets
import fluxio as fx
from fluxio.server import FluxioLiveServer


@pytest.mark.asyncio
async def test_live_websocket_streaming_and_controls():
    fig = fx.Figure(title="Live Stream", fps=25)
    fig.number(lambda t: 10.0 + t * 100.0, unit="pts", label="Score", precision=1)

    async with FluxioLiveServer(fig, host="127.0.0.1", port=0) as srv:
        assert srv.port > 0
        async with websockets.connect(srv.ws_url) as ws:
            # First message is full snapshot
            first = json.loads(await ws.recv())
            assert first["type"] == "snapshot"
            assert first["spec"]["title"] == "Live Stream"

            # Next message is a live tick update
            tick = json.loads(await ws.recv())
            assert tick["type"] == "tick"
            assert len(tick["updates"]) == 1
            assert tick["updates"][0]["value"] >= 10.0

            # Test real-time pause control from toolbar
            await ws.send(json.dumps({"type": "control", "action": "pause"}))
            state_msg = None
            for _ in range(5):
                msg = json.loads(await ws.recv())
                if msg["type"] == "state":
                    state_msg = msg
                    break
            assert state_msg is not None
            assert state_msg["playing"] is False


def test_browser_session_survives_immediate_launcher_exit():
    import subprocess
    import threading
    import time
    from fluxio.window import _BackgroundServerHandle

    fig = fx.Figure(rows=1, cols=2, title="Browser Session Test")
    fig.plot([1, 2, 3], [10, 20, 15], label="Static")
    fig.number(lambda t: t * 10, label="Dynamic")

    handle = _BackgroundServerHandle(fig).start()
    try:
        # Simulate Chrome singleton launcher exiting immediately with code 0
        already_exited_proc = subprocess.Popen(["true"])
        already_exited_proc.wait()

        def simulate_browser_client() -> None:
            import asyncio

            async def _client() -> None:
                await asyncio.sleep(0.12)
                async with websockets.connect(handle.ws_url) as ws:
                    msg = json.loads(await ws.recv())
                    assert msg["type"] == "snapshot"
                    await asyncio.sleep(0.2)

            asyncio.run(_client())

        t_client = threading.Thread(target=simulate_browser_client, daemon=True)
        t_client.start()

        t0 = time.monotonic()
        handle.wait_for_browser_session(already_exited_proc)
        elapsed = time.monotonic() - t0
        # Stayed alive for client connect + 0.2s session + ~0.75s disconnect grace period!
        assert elapsed >= 0.9
        t_client.join(timeout=2.0)
    finally:
        handle.stop()


def test_auto_backend_prefers_app_browser_on_linux_wayland_nvidia(monkeypatch):
    from fluxio import window as win_mod

    monkeypatch.setattr(win_mod.sys, "platform", "linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(win_mod, "_find_chromium_app_browser", lambda: "/usr/bin/google-chrome")
    monkeypatch.setattr(win_mod, "_is_linux_wayland_nvidia", lambda: True)
    assert win_mod._should_prefer_app_browser_auto() is True

    # On non-NVIDIA / Raspberry Pi / X11, auto still prefers pywebview
    monkeypatch.setattr(win_mod, "_is_linux_wayland_nvidia", lambda: False)
    assert win_mod._should_prefer_app_browser_auto() is False
