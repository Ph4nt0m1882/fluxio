import itertools
import pytest
import fluxio as fx


def test_figure_grid_and_auto_placement():
    fig = fx.Figure(rows=1, cols=2, title="System Metrics", theme="dark")
    c1 = fig.number(42.5, unit="°C", label="CPU Temp", precision=1)
    c2 = fig.number(88, unit="%", label="Memory")

    assert (c1.row, c1.col) == (0, 0)
    assert (c2.row, c2.col) == (0, 1)

    spec = fig.to_spec()
    assert spec["rows"] == 1
    assert spec["cols"] == 2
    assert spec["title"] == "System Metrics"
    assert len(spec["cells"]) == 2
    assert spec["cells"][0]["formatted"] == "42.5"
    assert spec["cells"][0]["unit"] == "°C"


def test_figure_subplot_indexing_and_bounds_validation():
    fig = fx.Figure(rows=2, cols=2)
    fig[1, 1].number(99, label="Corner")
    spec = fig.to_spec()
    assert spec["cells"][0]["row"] == 1
    assert spec["cells"][0]["col"] == 1

    with pytest.raises(ValueError, match="out of bounds"):
        fig.number(10, row=2, col=0)

    with pytest.raises(ValueError, match="already occupied"):
        fig.number(20, row=1, col=1)


def test_theme_and_powerpoint_style_customization():
    fig = fx.Figure(
        title="Quarterly KPI",
        theme="presentation",
        style={
            "accent": "#dc2626",
            "background": "#fef2f2",
            "font": "Noto Sans",
            "transparent": True,
        },
    )
    fig.number(128.4, prefix="€", unit="M", precision=1, label="Revenus")
    spec = fig.to_spec()

    assert spec["theme"]["name"] == "presentation"
    assert spec["theme"]["accent"] == "#dc2626"
    assert spec["theme"]["background"] == "#fef2f2"
    assert spec["theme"]["transparent"] is True
    assert spec["cells"][0]["formatted"] == "€128.4"


def test_dynamic_callable_and_generator_number():
    gen = (float(i * 10) for i in itertools.count(1))
    fig = fx.Figure(rows=1, cols=2)
    fig.number(lambda t: 100.0 + 5.0 * t, label="Time Fn", precision=1)
    fig.number(gen, label="Generator Stream", precision=0)

    assert fig.is_dynamic is True

    # Evaluate at t=0 and t=2.0
    frame0 = fig.evaluate_frame(0.0)
    assert frame0[0]["value"] == pytest.approx(100.0)
    assert frame0[1]["value"] == pytest.approx(10.0)

    frame1 = fig.evaluate_frame(2.0)
    assert frame1[0]["value"] == pytest.approx(110.0)
    assert frame1[1]["value"] == pytest.approx(20.0)
