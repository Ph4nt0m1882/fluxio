"""Native desktop window launcher (`pywebview`) with automatic `--app` browser fallback."""

from __future__ import annotations
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from typing import TYPE_CHECKING
from .server import FluxioLiveServer

if TYPE_CHECKING:
    from .charts.base import Visual
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

    def wait_for_browser_session(
        self,
        proc: subprocess.Popen[bytes] | None,
        close_after: float | None = None,
    ) -> None:
        """Keep the server alive until the `--app` browser window closes its WebSocket."""
        if close_after is not None:
            time.sleep(close_after)
            if proc is not None and proc.poll() is None:
                proc.terminate()
            return

        # Note: When Chrome/Chromium is already running on the desktop, `google-chrome --app=...`
        # delegates the new window to the existing browser process and `proc` exits in ~15ms!
        # So we track the actual WebSocket session lifetime instead of relying solely on `proc.wait()`.
        connected = self._server.ever_connected.wait(timeout=10.0)
        if connected:
            while True:
                time.sleep(0.15)
                if (
                    self._server.active_client_count == 0
                    and self._server.last_disconnect_time > 0.0
                    and (time.monotonic() - self._server.last_disconnect_time) >= 0.75
                ):
                    break
        elif proc is not None and proc.poll() is None:
            proc.wait()


_CHROMIUM_APP_BROWSERS = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "brave-browser",
    "microsoft-edge",
    "vivaldi",
)


def _find_chromium_app_browser() -> str | None:
    for candidate in _CHROMIUM_APP_BROWSERS:
        exe = shutil.which(candidate)
        if exe:
            return exe
    return None


def _is_linux_wayland_nvidia() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    is_wayland = bool(
        os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )
    has_nvidia = Path("/proc/driver/nvidia/version").exists()
    return bool(is_wayland and has_nvidia)


def _should_prefer_app_browser_auto() -> bool:
    """On Linux Wayland + NVIDIA, GTK3 WebKit2GTK falls back to CPU `wl_shm`.
    Prefer a frameless GPU-accelerated Chromium `--app` window when available."""
    return _is_linux_wayland_nvidia() and (_find_chromium_app_browser() is not None)


def _configure_linux_webkit_env() -> None:
    """Prevent WebKit2GTK 2.44+ DMA-BUF Wayland fence stalls on Linux NVIDIA / hybrid laptops."""
    if not sys.platform.startswith("linux"):
        return
    is_wayland = bool(
        os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )
    has_nvidia = Path("/proc/driver/nvidia/version").exists()
    if is_wayland or has_nvidia:
        os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")


def _has_gui_display() -> bool:
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def _open_browser_fallback(
    url: str, width: int, height: int
) -> subprocess.Popen[bytes] | None:
    exe = _find_chromium_app_browser()
    if exe:
        return subprocess.Popen(
            [exe, f"--app={url}", f"--window-size={width},{height}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    webbrowser.open(url)
    return None


def show(
    fig: Figure | Visual,
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
    from .charts.base import Visual

    if isinstance(fig, Visual):
        return fig.show(
            backend=backend,
            block=block,
            host=host,
            port=port,
            close_after=close_after,
        )

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

    use_pywebview = backend == "pywebview" or (
        backend == "auto" and not _should_prefer_app_browser_auto()
    )
    if use_pywebview:
        try:
            _configure_linux_webkit_env()
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

    # Browser fallback (`--app` frameless Chrome/Edge/Chromium window or system browser)
    proc = _open_browser_fallback(url, width, height)
    if block:
        try:
            handle.wait_for_browser_session(proc, close_after=close_after)
        except KeyboardInterrupt:
            pass
        finally:
            handle.stop()
    return url
