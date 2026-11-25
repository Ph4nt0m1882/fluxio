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
