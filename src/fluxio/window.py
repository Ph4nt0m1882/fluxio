"""Native desktop window launcher (`pywebview`) with automatic `--app` browser fallback."""

from __future__ import annotations
import asyncio
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from typing import TYPE_CHECKING
from .server import FluxioLiveServer

if TYPE_CHECKING:
    from .figure import Figure


class _BackgroundServerHandle:
    """Runs FluxioLiveServer inside a dedicated background event loop thread."""

    def __init__(self, fig: Figure, host: str = "127.0.0.1", port: int = 0) -> None:
        self.fig = fig
        self.host = host
        self.port = port
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._server = FluxioLiveServer(fig, host=host, port=port)
        self._thread = threading.Thread(target=self._run, daemon=True)

    @property
    def http_url(self) -> str:
        return self._server.http_url

    @property
    def ws_url(self) -> str:
        return self._server.ws_url

    def start(self) -> _BackgroundServerHandle:
        self._thread.start()
        self._ready.wait(timeout=10.0)
        return self

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._server.start())
        self._ready.set()
        self._loop.run_forever()
        self._loop.run_until_complete(self._server.stop())
        self._loop.close()

    def stop(self) -> None:
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)


def _has_gui_display() -> bool:
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def _open_browser_fallback(url: str, width: int, height: int) -> subprocess.Popen[bytes] | None:
    for candidate in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        exe = shutil.which(candidate)
        if exe:
            return subprocess.Popen(
                [exe, f"--app={url}", f"--window-size={width},{height}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    webbrowser.open(url)
    return None


def show(
    fig: Figure,
    *,
    backend: str = "auto",
    block: bool = True,
    host: str = "127.0.0.1",
    port: int = 0,
    close_after: float | None = None,
) -> str:
    """Open an interactive Fluxio window (like `matplotlib.pyplot.show()`).

    Uses `pywebview` native lightweight OS WebView when available, with automatic
    fallback to a frameless `--app` browser window or system browser.
    Pass `backend="terminal"` to animate in-place directly inside the terminal.
    Returns the local HTTP URL of the live server (or `"terminal://"`).
    """
    if backend == "terminal":
        fig.print(duration=close_after)
        return "terminal://"

    handle = _BackgroundServerHandle(fig, host=host, port=port).start()
    url = handle.http_url
    width, height = fig.size
    title = fig.title or "Fluxio"

    if not _has_gui_display() or backend == "server":
        if block and close_after is not None:
            time.sleep(close_after)
            handle.stop()
        return url

    if backend in ("auto", "pywebview"):
        try:
            import webview

            window = webview.create_window(
                title=title,
                url=url,
                width=max(360, width + 20),
                height=max(260, height + 40),
                resizable=True,
            )

            def _auto_close() -> None:
                if close_after is not None:
                    time.sleep(close_after)
                    window.destroy()

            webview.start(_auto_close if close_after is not None else None)
            handle.stop()
            return url
        except Exception:
            if backend == "pywebview":
                handle.stop()
                raise

    # Browser fallback
    proc = _open_browser_fallback(url, width, height)
    if block:
        try:
            if close_after is not None:
                time.sleep(close_after)
                if proc is not None:
                    proc.terminate()
            elif proc is not None:
                proc.wait()
            else:
                while True:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            handle.stop()
    return url
