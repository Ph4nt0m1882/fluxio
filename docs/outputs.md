# Outputs & Exports

A single `fx.Figure` instance supports four output targets without rewriting your code.

## 1. Interactive Desktop Window (`fx.show`)

```python
fx.show(fig)                      # Auto: native pywebview (or GPU --app window on Linux Wayland+NVIDIA)
fx.show(fig, backend="browser")   # Force frameless GPU --app browser window
fx.show(fig, backend="pywebview") # Force pywebview OS WebView
fx.show(fig, backend="terminal")  # Force live in-place terminal mode
```

Interactive toolbar controls (Material SVG icons):

- **Play / Pause & Replay** (for dynamic callable/generator cells, synchronized over local WebSocket)
- **Zoom In / Out / Reset (`100%`)** (buttons, mouse wheel anchored at cursor, double-click reset, touch/mouse drag pan)
- **Capture Screenshot** (instant high-DPI PNG export)
- **Fullscreen**

## 2. Jupyter Notebook Persistence

Place `fig` on the last line of a notebook cell. Fluxio embeds a self-contained, sandboxed HTML viewer (~30 KB, zero CDN links) via `_repr_html_()`:

- Interactive outputs **persist across subsequent cell executions** and remain saved inside the `.ipynb` file offline.
- Mutating `fig` in a later cell (e.g. `fig[0, 1].number(...)`) and evaluating `fig` renders the updated grid cleanly.

## 3. Terminal Rendering (`print(fig)` & `fig.print()`)

No need to switch to `plotext` for console or SSH sessions:

- **Single snapshot or manual loop (`print(fig)`)**:
  ```python
  for _ in range(50):
      print(fig)  # Advances time/generators and overwrites previous lines in-place!
      time.sleep(0.1)
  ```
- **Automatic live TUI loop (`fig.print()` / `fx.print(fig)`)**:
  ```python
  fig.print(duration=5.0, fps=20)  # Omit duration to run until Q or Ctrl+C
  ```
  Supports live keyboard shortcuts in TTY terminals: **`Space`** (Pause/Play), **`R`** (Reset), **`Q` / `Ctrl+C`** (Quit). Also updates in-place inside Jupyter cells via `clear_output(wait=True)`.

## 4. Multi-Format File Exports (`fig.save`)

All exports run headlessly in milliseconds without Chromium:

| Extension | Format | Key Options |
| :--- | :--- | :--- |
| `.png` | High-DPI raster image (RGBA, supports `transparent=True`) | `scale=2.0` |
| `.svg` | Crisp infinite-resolution vector graphic (ideal for PowerPoint) | — |
| `.gif` | Animated GIF evaluated over time | `duration=3.0, fps=20, scale=1.0` |
| `.mp4` / `.webm` | Hardware-compatible H.264 / VP9 video (requires `ffmpeg`) | `duration=3.0, fps=30, scale=1.0` |
| `.html` | 100% self-contained interactive offline web page | `duration=3.0, fps=24` |
| `.txt` / `.ans` | Plain UTF-8 Unicode box-art (`.txt`) or ANSI TrueColor (`.ans`) | — |
| `.term.svg` | Pixel-locked ANSI TrueColor Terminal SVG (zero font misalignment for docs & READMEs) | — |
