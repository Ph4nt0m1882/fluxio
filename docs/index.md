---
hide:
  - navigation
  - toc
---

<div class="fx-hero">
  <img src="assets/banner.webp" alt="Fluxio — Modern Visualization Engine" />
  <p class="fx-hero-subtitle">
    <strong>Fluxio</strong> (<code>import fluxio as fx</code>) is a lightweight, real-time visualization engine in <strong>Python + zero-dependency TypeScript <code>&lt;canvas&gt;</code></strong> (~38 KB) built for desktop windows, Jupyter, ANSI terminals, slides, and AI chatbots.
  </p>
</div>

<div class="fx-grid">
  <a class="fx-card fx-cyan" href="tutorial/">
    <div>
      <div class="fx-card-kicker">01 • Tutorial &amp; Aesthetics</div>
      <h3 class="fx-card-title">Core Concepts &amp; Tutorial</h3>
      <p class="fx-card-desc">
        Progressive walkthrough from a 2-line minimal chart to multi-cell grids, cascading <code>.style()</code>, live <code>.gif</code> animations, and terminal <code>print(fig)</code> outputs.
      </p>
    </div>
    <span class="fx-card-cta">Start the Tutorial →</span>
  </a>

  <a class="fx-card fx-emerald fx-right" href="developer/">
    <div>
      <div class="fx-card-kicker">02 • Engine &amp; Targets</div>
      <h3 class="fx-card-title">Developer &amp; Outputs</h3>
      <p class="fx-card-desc">
        3-level OOP class hierarchy (<code>Visual → Family → Chart</code>), native windows, persistent Jupyter cells, live in-place terminal <code>print(fig)</code>, and Chromium-free <code>PNG/SVG/GIF/MP4/HTML</code> exports.
      </p>
    </div>
    <span class="fx-card-cta">Read Engine &amp; Outputs →</span>
  </a>

  <a class="fx-card fx-orange" href="charts/">
    <div>
      <div class="fx-card-kicker">03 • Visual Catalog</div>
      <h3 class="fx-card-title">Visualizations Gallery</h3>
      <p class="fx-card-desc">
        Browse every available chart and KPI indicator with live Python-generated previews and dedicated one-page API references (<code>Number</code>, <code>Plot</code>, and more).
      </p>
    </div>
    <span class="fx-card-cta">Open Visual Gallery →</span>
  </a>

  <a class="fx-card fx-purple fx-right" href="ai-integration/">
    <div>
      <div class="fx-card-kicker">04 • LLM-First Design</div>
      <h3 class="fx-card-title">AI &amp; Chatbot Integration</h3>
      <p class="fx-card-desc">
        Zero-hallucination code generation for local and frontier LLMs via runtime <code>fx.llm_context()</code>, <code>llms.txt</code>, <code>llms-full.txt</code>, and condensed <code>fluxio.pyi</code> stubs.
      </p>
    </div>
    <span class="fx-card-cta">Configure AI Context →</span>
  </a>
</div>

---

## Quickstart in 10 Lines

```python
import math
import fluxio as fx

fig = fx.Figure(rows=1, cols=2, title="Live Telemetry Overview", size=(960, 420), fps=24)
fig.style(background=fx.Gradient(["#090d16", "#1e1b4b"], angle=135), radius=20)

fig[0, 0].style(variant="reverse", accent="#059669", accent_side="left").number(
    42.5, unit="°C", precision=1, label="SoC Temperature"
)
xs = [i * 0.2 for i in range(35)]
fig[0, 1].style(accent="#38bdf8", accent_side="right").plot(
    xs, [math.sin(x) * 30 + 50 for x in xs], label="Signal", xlabel="t (s)"
)

print(fig)                # ANSI TrueColor + Unicode Braille in terminal!
fx.show(fig)              # Interactive desktop window (zoom/pan, pause, PNG capture)
fig.save("overview.png")  # High-DPI export in milliseconds
```
