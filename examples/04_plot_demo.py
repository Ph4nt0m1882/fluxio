"""Démo de `Plot(Axis2D)` : multi-courbes, combinaison avec `Number`, Braille terminal et fenêtre interactive.

Exemples :
    uv run python examples/04_plot_demo.py
    uv run python examples/04_plot_demo.py --no-window
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import fluxio as fx


def build_plot_showcase() -> fx.Figure:
    fig = fx.Figure(
        rows=2,
        cols=2,
        title="Fluxio — Oscilloscope & Télémétrie (Axis2D + Indicator)",
        subtitle="Survolez les courbes pour inspecter les points (tooltip magnétique fluide sans popping)",
        size=(1020, 600),
        fps=60,
    )
    fig.style(
        background=fx.Gradient(["#090d16", "#0f172a", "#1e1b4b"], angle=135),
        radius=20,
        accent="#38bdf8",
        accent_side="left",
    )

    # Haut (occupe 2 colonnes) : superposition de 2 courbes statiques/analytiques
    xs = [round(i * 0.2, 2) for i in range(42)]
    y_model = [850.0 * math.exp(-0.18 * x) + 250.0 for x in xs]
    y_meas = [
        850.0 * math.exp(-0.18 * x) + 250.0 + 38.0 * math.sin(x * 2.1) for x in xs
    ]

    fig.plot(
        xs,
        y_model,
        label="Modèle Théorique",
        card_title="Refroidissement Thermique",
        xlabel="Temps (s)",
        ylabel="Température (°C)",
        row=0,
        col=0,
        col_span=2,
    )
    fig[0, 0].plot(
        xs,
        y_meas,
        label="Capteur Réel",
        color="#f97316",
        linestyle="dashed",
        marker="circle",
        fill_alpha=0.06,
    )

    # Bas gauche : KPI Number en style Reverse
    fig[1, 0].style(variant="reverse", accent="#059669", accent_side="left").number(
        lambda t: 250.0 + 38.0 * math.sin(t * 2.5),
        unit="°C",
        precision=1,
        label="Température Finale Stabilisée",
        description="Asymptote mesurée en continu",
    )

    # Bas droite : Onde dynamique animée à 60 FPS
    w_xs = [round(i * 0.15, 2) for i in range(45)]
    fig[1, 1].style(accent="#a78bfa", accent_side="right").plot(
        lambda t: (
            w_xs,
            [math.sin(x * 1.4 - t * 3.5) * math.cos(x * 0.35) for x in w_xs],
        ),
        label="Onde Sismique",
        card_title="Signal Temps Réel",
        xlabel="Distance (km)",
        ylabel="Amplitude",
        ylim=(-1.1, 1.1),
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description="Démo Fluxio Plot")
    parser.add_argument(
        "--no-window", action="store_true", help="N'ouvre pas la fenêtre interactive"
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "pywebview", "browser", "terminal"],
        default="auto",
        help="Backend d'affichage (auto, pywebview, browser, terminal)",
    )
    args = parser.parse_args()

    fig = build_plot_showcase()
    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = fig.save(out_dir / "plot_showcase.png", scale=2.0)
    html_path = fig.save(out_dir / "plot_showcase.html", duration=3.0, fps=24)

    print(fig)
    print(f"\nExports générés : {png_path} | {html_path}")

    if not args.no_window:
        fx.show(fig, backend=args.backend)


if __name__ == "__main__":
    main()
