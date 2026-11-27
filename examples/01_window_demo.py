"""Test 1 : Fenêtre interactive Fluxio + affichage Terminal `print(fig)` dans le même script !

Exemples d'utilisation :
    uv run python examples/01_window_demo.py
    uv run python examples/01_window_demo.py --variant text
    uv run python examples/01_window_demo.py --variant reverse
    uv run python examples/01_window_demo.py --no-window   # Uniquement print(fig) dans le terminal !
"""

from __future__ import annotations

import argparse
import itertools
import math

import fluxio as fx


def packet_stream():
    """Générateur Python simulant un compteur de paquets réseau."""
    for i in itertools.count(1):
        yield i * 12


def build_demo_figure(global_variant: str = "classic") -> fx.Figure:
    fig = fx.Figure(
        rows=2,
        cols=2,
        title="Fluxio — Monitoring Hybride (Terminal + Fenêtre)",
        subtitle="Même objet `fig` : `print(fig)` dans le terminal ET `fx.show(fig)` interactif",
        size=(940, 560),
        fps=60,
    )

    fig.style(
        variant=global_variant,
        background=fx.Gradient(["#090d16", "#0f172a", "#1e1b4b"], angle=135)
        if global_variant != "text"
        else "#0a0e14",
        accent="#38bdf8",
        accent_side="top",
        radius=20,
        hover_ms=220,
    )

    # Haut (2 colonnes)
    fig.number(
        lambda t: 65.0 + 18.0 * math.sin(t * 1.8),
        label="Charge Système Globale",
        unit="%",
        precision=1,
        description="Évaluée en temps réel côté Python (65 + 18·sin(1.8t))",
        row=0,
        col=0,
        col_span=2,
    )

    # Bas gauche : accent courbé à GAUCHE
    fig[1, 0].style(
        accent_side="left",
        accent="#34d399",
        accent_width=7.5,
    ).number(
        43.2,
        label="Température SoC",
        unit="°C",
        precision=1,
        description="Seuil nominal < 70 °C",
    )

    # Bas droite : style `reverse` si mode par défaut pour montrer le mix dans une même grille !
    cell_variant = "reverse" if global_variant == "classic" else global_variant
    fig[1, 1].style(
        variant=cell_variant,
        accent_side="right",
        accent="#ea580c",
        accent_width=7.5,
    ).number(
        packet_stream(),
        label="Flux Générateur (Reverse)"
        if cell_variant == "reverse"
        else "Flux Générateur",
        unit="pkt",
        precision=0,
        description="Alimenté par un générateur Python (yield)",
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description="Démo fenêtre + terminal Fluxio")
    parser.add_argument(
        "--variant",
        choices=["classic", "reverse", "text"],
        default="classic",
        help="Variante esthétique globale (classic, reverse, text)",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Affiche uniquement `print(fig)` dans le terminal sans ouvrir de fenêtre",
    )
    parser.add_argument(
        "--live-print",
        action="store_true",
        help="Anime `fig.print()` en direct sur place dans le terminal (façon btop)",
    )
    args = parser.parse_args()

    fig = build_demo_figure(args.variant)

    if args.live_print:
        fig.print()
        return

    # Affichage direct dans le terminal (remplace plotext sans changer d'objet !)
    print(fig)

    if not args.no_window:
        fx.show(fig)


if __name__ == "__main__":
    main()
