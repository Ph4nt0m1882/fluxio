"""Lightweight asyncio HTTP + WebSocket live server for real-time Fluxio figures."""

from __future__ import annotations
import asyncio
import base64
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from websockets.asyncio.server import ServerConnection, serve as ws_serve
from .html_export import render_standalone_html

if TYPE_CHECKING:
    from .figure import Figure


class FluxioLiveServer:
    """Serves the interactive HTML viewer over HTTP and streams real-time updates over WebSocket."""

    def __init__(
        self,
        fig: Figure,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        capture_dir: Path | None = None,
    ) -> None:
        self.fig = fig
        self.host = host
        self._requested_port = port
        self.port: int = 0
        self.ws_port: int = 0
        self.playing: bool = True
        self.capture_dir = capture_dir or Path.cwd()

        self._http_server: asyncio.Server | None = None
        self._ws_server: Any = None
        self._clients: set[ServerConnection] = set()
        self._ticker_task: asyncio.Task[None] | None = None
        self._start_time: float = 0.0
        self._paused_elapsed: float = 0.0
        self._step_index: int = 0

    @property
    def http_url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.ws_port}"

    def current_elapsed(self) -> float:
        if self.playing:
            return self._paused_elapsed + (time.monotonic() - self._start_time)
        return self._paused_elapsed

    async def __aenter__(self) -> FluxioLiveServer:
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.stop()

    async def start(self) -> None:
        self._start_time = time.monotonic()
        self._ws_server = await ws_serve(self._handle_ws, self.host, 0)
        ws_sock = next(iter(self._ws_server.sockets))
        self.ws_port = int(ws_sock.getsockname()[1])

        self._http_server = await asyncio.start_server(
            self._handle_http, self.host, self._requested_port
        )
        http_sock = next(iter(self._http_server.sockets))
        self.port = int(http_sock.getsockname()[1])

        if self.fig.is_dynamic:
            self._ticker_task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._ticker_task is not None:
            self._ticker_task.cancel()
            try:
                await self._ticker_task
            except asyncio.CancelledError:
                pass
            self._ticker_task = None

        if self._ws_server is not None:
            self._ws_server.close()
            await self._ws_server.wait_closed()
            self._ws_server = None

        if self._http_server is not None:
            self._http_server.close()
            await self._http_server.wait_closed()
            self._http_server = None

    async def _handle_http(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            await reader.readuntil(b"\r\n\r\n")
            spec = self.fig.to_spec(t=self.current_elapsed(), step_index=None)
            html_body = render_standalone_html(spec, ws_url=self.ws_url, full_viewport=True)
            payload = html_body.encode("utf-8")
            headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "Cache-Control: no-store\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            writer.write(headers + payload)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_ws(self, ws: ServerConnection) -> None:
        self._clients.add(ws)
        try:
            spec = self.fig.to_spec(t=self.current_elapsed(), step_index=None)
            await ws.send(json.dumps({"type": "snapshot", "spec": spec}))

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                msg_type = msg.get("type")
                if msg_type == "control":
                    await self._handle_control(str(msg.get("action", "")))
                elif msg_type == "capture":
                    await self._handle_capture(ws, str(msg.get("data_url", "")))
        finally:
            self._clients.discard(ws)

    async def _handle_control(self, action: str) -> None:
        if action == "pause" and self.playing:
            self._paused_elapsed += time.monotonic() - self._start_time
            self.playing = False
            await self._broadcast({"type": "state", "playing": False})
        elif action == "play" and not self.playing:
            self._start_time = time.monotonic()
            self.playing = True
            await self._broadcast({"type": "state", "playing": True})
        elif action == "reset":
            self._paused_elapsed = 0.0
            self._start_time = time.monotonic()
            self._step_index = 0
            for cell in self.fig.cells:
                cell.reset_cursor()
            updates = self.fig.evaluate_frame(0.0, step_index=0)
            await self._broadcast({"type": "tick", "t": 0.0, "updates": updates})

    async def _handle_capture(self, ws: ServerConnection, data_url: str) -> None:
        prefix = "data:image/png;base64,"
        if not data_url.startswith(prefix):
            return
        raw_png = base64.b64decode(data_url[len(prefix) :])
        ts = int(time.time())
        out_path = self.capture_dir / f"fluxio_capture_{ts}.png"
        out_path.write_bytes(raw_png)
        await ws.send(json.dumps({"type": "capture_saved", "path": str(out_path)}))

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        if not self._clients:
            return
        encoded = json.dumps(payload)
        stale: list[ServerConnection] = []
        for client in list(self._clients):
            try:
                await client.send(encoded)
            except Exception:
                stale.append(client)
        for s in stale:
            self._clients.discard(s)

    async def _tick_loop(self) -> None:
        interval = 1.0 / max(1, self.fig.fps)
        while True:
            await asyncio.sleep(interval)
            if not self.playing or not self._clients:
                continue
            t = self.current_elapsed()
            self._step_index += 1
            updates = self.fig.evaluate_frame(t, step_index=self._step_index)
            if updates:
                await self._broadcast({"type": "tick", "t": t, "updates": updates})
