"""Test 3 : Exports multi-formats + Variantes (`classic`, `reverse`, `text`) + Export `.txt`.

Lancez :
    uv run python examples/03_exports_demo.py
"""

from __future__ import annotations
import math
from pathlib import Path
from PIL import Image, ImageDraw
import fluxio as fx


def _make_sample_corporate_wallpaper(path: Path) -> Path:
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), (241, 245, 249))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.polygon([(0, 0), (540, 0), (260, h), (0, h)], fill=(219, 234, 254, 190))
    draw.polygon([(w - 460, 0), (w, 0), (w, h), (w - 720, h)], fill=(224, 231, 255, 180))
    draw.ellipse([w - 340, -140, w + 120, 320], fill=(199, 210, 254, 140))
    img.save(path)
    return path


def main() -> None:
    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    bg_path = _make_sample_corporate_wallpaper(out_dir / "corporate_wallpaper.png")

    # 1. Diapo Entreprise combinant `classic` (gauche) et `reverse` (droite, mise en avant d'un KPI !)
    ppt_fig = fx.Figure(
        rows=1,
        cols=2,
        title="Indicateurs Clés — Classic & Reverse",
        subtitle="À gauche : carte translucide classique • À droite : style Reverse plein avec texte en opacité",
        theme="presentation",
        size=(960, 480),
    )
    ppt_fig.style(
        background=fx.BackgroundImage(bg_path, fit="cover"),
        radius=24,
        accent_width=8.0,
        border_width=2.0,
        border_opacity=0.65,
        accent_side="left",
        accent="#2563eb",
    )
    ppt_fig[0, 0].number(
        99.95,
        unit="%",
        precision=2,
        label="Disponibilité (Style Classic)",
        description="Voile adaptatif & croissant à gauche",
    )
    ppt_fig[0, 1].style(
        variant="reverse",
        accent_side="right",
        accent="#059669",
    ).number(
        14.2,
        unit="ms",
        precision=1,
        label="Latence Médiane (Style Reverse)",
        description="Fond couleur accent & texte translucide",
    )

    p_png = ppt_fig.save(out_dir / "slide_powerpoint.png", scale=2.0)
    p_svg = ppt_fig.save(out_dir / "slide_vector.svg")
    p_txt = ppt_fig.save(out_dir / "rapport_terminal.txt")

    ppt_fig.style(transparent=True)
    p_trans = ppt_fig.save(out_dir / "slide_transparent.png", scale=2.0)

    # 2. Mode `variant="text"` (rendu graphique façon Terminal / btop avec chiffres en blocs !)
    tui_fig = fx.Figure(
        rows=1,
        cols=2,
        title="Fluxio TUI — Mode Texte Graphique & Terminal",
        subtitle="Même figure affichable via fx.show(fig), export PNG/HTML ou print(fig) dans le terminal",
        size=(960, 440),
    )
    tui_fig.style(variant="text", accent="#38bdf8", accent_side="left")
    tui_fig[0, 0].number(
        43.8,
        unit="°C",
        precision=1,
        label="SoC RasPi",
        description="Capteur thermique nominal",
    )
    tui_fig[0, 1].style(accent="#34d399", accent_side="right").number(
        1280,
        unit="req/s",
        precision=0,
        label="Débit API",
        description="Moyenne glissante 10s",
    )
    p_tui_png = tui_fig.save(out_dir / "slide_tui_text.png", scale=2.0)
    p_tui_html = tui_fig.save(out_dir / "tui_interactive.html")

    # 3. Figure dynamique (GIF + MP4 + HTML autonome)
    dyn_fig = fx.Figure(
        rows=1,
        cols=2,
        title="Simulation Capteurs — Dégradé Sombre",
        subtitle="Voile lumineux automatique (~10 %) et survol progressif sans popping",
        size=(920, 460),
        fps=24,
    )
    dyn_fig.style(
        background=fx.Gradient(["#090d16", "#1e1b4b", "#0f172a"], angle=130),
        radius=24,
        accent_width=8.0,
        hover_ms=220,
    )
    dyn_fig[0, 0].style(accent_side="left", accent="#f97316").number(
        lambda t: 850.0 + 120.0 * math.sin(t * 2.0 * math.pi / 3.0),
        unit="°C",
        precision=1,
        label="Température Magma",
    )
    dyn_fig[0, 1].style(variant="reverse", accent_side="right", accent="#2563eb").number(
        lambda t: 1.0 + t * 4.5,
        unit="MPa",
        precision=2,
        label="Pression Chambre",
    )

    p_dark_png = dyn_fig.save(out_dir / "slide_dark_gradient.png", scale=2.0)
    p_gif = dyn_fig.save(out_dir / "animation.gif", duration=3.0, fps=15, scale=1.0)
    p_mp4 = dyn_fig.save(out_dir / "animation.mp4", duration=3.0, fps=24, scale=1.0)
    p_html = dyn_fig.save(out_dir / "standalone_interactive.html", duration=3.0, fps=24)

    print("\n--- Aperçu direct de `print(tui_fig)` dans le terminal ---")
    print(tui_fig)
    print("----------------------------------------------------------\n")

    for p in (p_png, p_tui_png, p_dark_png, p_trans, p_svg, p_txt, p_gif, p_mp4, p_html, p_tui_html):
        size_kb = p.stat().st_size / 1024
        print(f"OK  {p.name:<30} ({size_kb:6.1f} Ko) -> {p}")


if __name__ == "__main__":
    main()
