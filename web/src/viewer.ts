import {
  createInitialViewport,
  hitTestCell,
  panViewport,
  zoomViewportAt,
  type GridRect,
  type Viewport,
} from "./layout";
import {
  applyTickMessage,
  formatNumberValue,
  parseFigureSpec,
  type FigureSpec,
  type ServerMessage,
} from "./protocol";
import { renderFigureToCanvas, TOOLBAR_ICONS } from "./renderer";
import { stepHoverMap } from "./themes";

export interface MountOptions {
  wsUrl?: string;
}

const VIEWER_CSS = `
.fx-root {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 220px;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
  touch-action: none;
  box-sizing: border-box;
  border-radius: 12px;
}
.fx-canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
}
.fx-canvas.fx-dragging {
  cursor: grabbing;
}
.fx-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.78);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.22);
  opacity: 0.86;
  transition: opacity 0.15s ease;
  z-index: 10;
  font-family: Inter, system-ui, -apple-system, sans-serif;
}
.fx-toolbar:hover {
  opacity: 1;
}
.fx-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: #f8fafc;
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1;
  min-height: 26px;
  padding: 5px 7px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.12s ease, color 0.12s ease;
}
.fx-btn:hover {
  background: rgba(255, 255, 255, 0.14);
}
.fx-sep {
  width: 1px;
  height: 16px;
  background: rgba(148, 163, 184, 0.3);
  margin: 0 2px;
}
.fx-toast {
  position: absolute;
  bottom: 14px;
  right: 14px;
  padding: 7px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.9);
  color: #f8fafc;
  font-family: Inter, system-ui, sans-serif;
  font-size: 12px;
  border: 1px solid rgba(56, 189, 248, 0.45);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s ease;
  z-index: 12;
}
.fx-toast.fx-visible {
  opacity: 1;
}
`;

let stylesInjected = false;
function ensureStyles(): void {
  if (stylesInjected || typeof document === "undefined") return;
  const styleEl = document.createElement("style");
  styleEl.setAttribute("data-fluxio-styles", "true");
  styleEl.textContent = VIEWER_CSS;
  document.head.appendChild(styleEl);
  stylesInjected = true;
}

export class FluxioViewer {
  private container: HTMLElement;
  private root: HTMLDivElement;
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private toastEl: HTMLDivElement;
  private playBtn: HTMLButtonElement | null = null;
  private zoomResetBtn: HTMLButtonElement | null = null;

  private spec: FigureSpec;
  private viewport: Viewport = createInitialViewport();
  private rects: GridRect[] = [];
  private hoveredCellId: string | null = null;
  private hoverProgress = new Map<string, number>();
  private hoverAnimating = false;
  private bgImage: HTMLImageElement | null = null;

  private playing = true;
  private ws: WebSocket | null = null;
  private wsConnected = false;
  private rafId: number | null = null;
  private startPerfTime = 0;
  private lastFramePerfTime = 0;
  private pausedElapsed = 0;
  private resizeObserver: ResizeObserver | null = null;

  constructor(container: HTMLElement, rawSpec: unknown, options?: MountOptions) {
    ensureStyles();
    this.container = container;
    this.spec = parseFigureSpec(rawSpec);

    this.root = document.createElement("div");
    this.root.className = "fx-root";

    this.canvas = document.createElement("canvas");
    this.canvas.className = "fx-canvas";
    const ctx = this.canvas.getContext("2d");
    if (!ctx) {
      throw new Error("Canvas 2D context unavailable");
    }
    this.ctx = ctx;
    this.root.appendChild(this.canvas);

    this.toastEl = document.createElement("div");
    this.toastEl.className = "fx-toast";
    this.root.appendChild(this.toastEl);

    if (this.spec.toolbar.enabled) {
      this.buildToolbar();
    }

    this.container.innerHTML = "";
    this.container.appendChild(this.root);

    this.prepareBackgroundImage();
    this.bindInteractions();
    const now = performance.now();
    this.startPerfTime = now;
    this.lastFramePerfTime = now;

    if (options?.wsUrl) {
      this.connectWebSocket(options.wsUrl);
    }

    if (this.spec.dynamic) {
      this.ensureLoopRunning();
    } else {
      this.draw();
    }
  }

  private prepareBackgroundImage(): void {
    const bg = this.spec.theme.background_spec;
    if (bg.type === "image" && bg.data_url && typeof Image !== "undefined") {
      const img = new Image();
      img.onload = () => {
        this.bgImage = img;
        this.draw();
      };
      img.src = bg.data_url;
      this.bgImage = img;
    } else {
      this.bgImage = null;
    }
  }

  private buildToolbar(): void {
    const bar = document.createElement("div");
    bar.className = "fx-toolbar";
    const tb = this.spec.toolbar;

    const addBtn = (
      contentHtml: string,
      title: string,
      onClick: () => void,
      isText = false,
    ): HTMLButtonElement => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fx-btn";
      if (isText) {
        btn.textContent = contentHtml;
      } else {
        btn.innerHTML = contentHtml;
      }
      btn.title = title;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        onClick();
      });
      bar.appendChild(btn);
      return btn;
    };

    const addSep = (): void => {
      const sep = document.createElement("div");
      sep.className = "fx-sep";
      bar.appendChild(sep);
    };

    if (tb.playback && this.spec.dynamic) {
      this.playBtn = addBtn(TOOLBAR_ICONS.pause, "Pause / Lecture", () =>
        this.togglePlay(),
      );
      addBtn(TOOLBAR_ICONS.replay, "Réinitialiser l'animation", () =>
        this.resetPlayback(),
      );
      addSep();
    }

    if (tb.zoom) {
      addBtn(TOOLBAR_ICONS.zoomOut, "Dézoomer", () =>
        this.zoomCenter(1 / 1.25),
      );
      this.zoomResetBtn = addBtn(
        "100%",
        "Réinitialiser le zoom (double-clic)",
        () => this.resetViewport(),
        true,
      );
      addBtn(TOOLBAR_ICONS.zoomIn, "Zoomer", () => this.zoomCenter(1.25));
      addSep();
    }

    if (tb.capture) {
      addBtn(TOOLBAR_ICONS.camera, "Capturer en PNG", () =>
        this.captureScreenshot(),
      );
    }

    if (tb.fullscreen) {
      addBtn(TOOLBAR_ICONS.fullscreen, "Plein écran", () =>
        this.toggleFullscreen(),
      );
    }

    this.root.appendChild(bar);
  }

  private setHoveredCell(nextId: string | null): void {
    if (nextId === this.hoveredCellId) return;
    this.hoveredCellId = nextId;
    this.hoverAnimating = true;
    this.ensureLoopRunning();
  }

  private bindInteractions(): void {
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    this.canvas.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      this.canvas.classList.add("fx-dragging");
      this.canvas.setPointerCapture(e.pointerId);
    });

    this.canvas.addEventListener("pointermove", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;

      if (dragging) {
        const dx = e.clientX - lastX;
        const dy = e.clientY - lastY;
        lastX = e.clientX;
        lastY = e.clientY;
        this.viewport = panViewport(this.viewport, dx, dy);
        this.draw();
      } else {
        const hit = hitTestCell(this.rects, this.viewport, sx, sy);
        this.setHoveredCell(hit);
      }
    });

    this.canvas.addEventListener("pointerleave", () => {
      this.setHoveredCell(null);
    });

    const endDrag = (e: PointerEvent): void => {
      if (!dragging) return;
      dragging = false;
      this.canvas.classList.remove("fx-dragging");
      try {
        this.canvas.releasePointerCapture(e.pointerId);
      } catch {
        // Ignore if not captured
      }
    };

    this.canvas.addEventListener("pointerup", endDrag);
    this.canvas.addEventListener("pointercancel", endDrag);

    this.canvas.addEventListener("dblclick", () => {
      this.resetViewport();
    });

    this.canvas.addEventListener(
      "wheel",
      (e) => {
        if (!this.spec.toolbar.zoom) return;
        e.preventDefault();
        const rect = this.canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
        this.viewport = zoomViewportAt(this.viewport, factor, sx, sy);
        this.updateZoomLabel();
        this.draw();
      },
      { passive: false },
    );

    if (typeof ResizeObserver !== "undefined") {
      this.resizeObserver = new ResizeObserver(() => this.draw());
      this.resizeObserver.observe(this.root);
    } else {
      window.addEventListener("resize", () => this.draw());
    }
  }

  private zoomCenter(factor: number): void {
    const rect = this.canvas.getBoundingClientRect();
    this.viewport = zoomViewportAt(
      this.viewport,
      factor,
      rect.width / 2,
      rect.height / 2,
    );
    this.updateZoomLabel();
    this.draw();
  }

  private resetViewport(): void {
    this.viewport = createInitialViewport();
    this.updateZoomLabel();
    this.draw();
  }

  private updateZoomLabel(): void {
    if (this.zoomResetBtn) {
      this.zoomResetBtn.textContent = `${Math.round(this.viewport.scale * 100)}%`;
    }
  }

  private togglePlay(): void {
    this.setPlaying(!this.playing, true);
  }

  private setPlaying(next: boolean, notifyServer: boolean): void {
    if (this.playing === next) return;
    if (!next) {
      this.pausedElapsed += (performance.now() - this.startPerfTime) / 1000;
    } else {
      this.startPerfTime = performance.now();
    }
    this.playing = next;
    if (this.playBtn) {
      this.playBtn.innerHTML = this.playing
        ? TOOLBAR_ICONS.pause
        : TOOLBAR_ICONS.play;
    }
    if (notifyServer && this.ws && this.wsConnected) {
      this.ws.send(
        JSON.stringify({
          type: "control",
          action: this.playing ? "play" : "pause",
        }),
      );
    }
    if (this.playing && this.spec.dynamic) {
      this.ensureLoopRunning();
    } else {
      this.draw();
    }
  }

  private resetPlayback(): void {
    this.pausedElapsed = 0;
    this.startPerfTime = performance.now();
    if (this.ws && this.wsConnected) {
      this.ws.send(JSON.stringify({ type: "control", action: "reset" }));
    }
    this.updateOfflineFrames(0);
    this.draw();
  }

  private captureScreenshot(): void {
    this.draw();
    const dataUrl = this.canvas.toDataURL("image/png");

    if (this.ws && this.wsConnected) {
      this.ws.send(JSON.stringify({ type: "capture", data_url: dataUrl }));
    }

    const a = document.createElement("a");
    const slug = (this.spec.title || "fluxio-capture")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    a.download = `${slug || "fluxio-capture"}.png`;
    a.href = dataUrl;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    this.showToast("Capture PNG enregistrée");
  }

  private toggleFullscreen(): void {
    if (!document.fullscreenElement) {
      this.root.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  }

  private showToast(text: string): void {
    this.toastEl.textContent = text;
    this.toastEl.classList.add("fx-visible");
    window.setTimeout(() => {
      this.toastEl.classList.remove("fx-visible");
    }, 2200);
  }

  private connectWebSocket(wsUrl: string): void {
    try {
      const ws = new WebSocket(wsUrl);
      this.ws = ws;

      ws.addEventListener("open", () => {
        this.wsConnected = true;
      });

      ws.addEventListener("message", (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as ServerMessage;
          if (msg.type === "snapshot") {
            this.spec = parseFigureSpec(msg.spec);
            this.prepareBackgroundImage();
            this.draw();
          } else if (msg.type === "tick") {
            applyTickMessage(this.spec, msg);
            this.draw();
          } else if (msg.type === "state") {
            this.setPlaying(msg.playing, false);
          } else if (msg.type === "capture_saved") {
            this.showToast(`Enregistré : ${msg.path}`);
          }
        } catch {
          // Ignore malformed message
        }
      });

      ws.addEventListener("close", () => {
        this.wsConnected = false;
      });
    } catch {
      this.wsConnected = false;
    }
  }

  private updateOfflineFrames(elapsedSec: number): void {
    if (this.wsConnected) return;
    for (const cell of this.spec.cells) {
      if (cell.dynamic && cell.frames && cell.frames.length > 0) {
        const idx =
          Math.floor(elapsedSec * this.spec.fps) % cell.frames.length;
        const val = cell.frames[idx]!;
        cell.value = val;
        cell.formatted = formatNumberValue(val, cell.precision, cell.prefix);
      }
    }
  }

  private ensureLoopRunning(): void {
    if (this.rafId !== null) return;
    this.lastFramePerfTime = performance.now();

    const step = (now: number): void => {
      this.rafId = null;
      const dt = Math.min(0.05, Math.max(0.001, (now - this.lastFramePerfTime) / 1000));
      this.lastFramePerfTime = now;

      const elapsed = this.playing
        ? this.pausedElapsed + (now - this.startPerfTime) / 1000
        : this.pausedElapsed;

      if (this.hoverAnimating) {
        const ids = this.spec.cells.map((c) => c.id);
        this.hoverAnimating = stepHoverMap(
          this.hoverProgress,
          ids,
          this.hoveredCellId,
          dt,
          this.spec.theme.hover_ms,
        );
      }

      const offlineAnimating =
        this.spec.dynamic && this.playing && !this.wsConnected;
      if (offlineAnimating) {
        this.updateOfflineFrames(elapsed);
      }

      this.draw(elapsed);

      if (this.hoverAnimating || offlineAnimating) {
        this.rafId = window.requestAnimationFrame(step);
      }
    };

    this.rafId = window.requestAnimationFrame(step);
  }

  public draw(elapsed = 0): void {
    const rect = this.root.getBoundingClientRect();
    const logicalW = Math.max(160, rect.width || this.spec.size[0]);
    const logicalH = Math.max(120, rect.height || this.spec.size[1]);
    const dpr = Math.min(3, window.devicePixelRatio || 1);

    const targetW = Math.round(logicalW * dpr);
    const targetH = Math.round(logicalH * dpr);
    if (this.canvas.width !== targetW || this.canvas.height !== targetH) {
      this.canvas.width = targetW;
      this.canvas.height = targetH;
    }

    this.rects = renderFigureToCanvas(this.ctx, logicalW, logicalH, dpr, {
      spec: this.spec,
      viewport: this.viewport,
      hoverProgress: this.hoverProgress,
      playing: this.playing,
      elapsedSeconds: elapsed,
      bgImage: this.bgImage,
    });
  }

  public destroy(): void {
    if (this.rafId !== null) {
      window.cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.resizeObserver?.disconnect();
    this.ws?.close();
  }
}
