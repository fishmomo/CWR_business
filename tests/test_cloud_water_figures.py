import matplotlib.pyplot as plt
import numpy as np
import pytest
from shapely.geometry import box
import xarray as xr

from cwr_engine.business_metrics.cloud_water_figures import (
    _draw_map_panel,
    _render_annual_maps,
    _render_monthly_sequence,
    _render_region_preview,
    _render_season_maps,
    _tidy_colorbar_label,
    _tidy_colorbar_levels,
)
from cwr_engine.business_metrics.cloud_water_multi_year_figures import (
    _render_interannual_sequence,
)


def test_interannual_sequence_uses_approved_abbreviations_and_typography(
    tmp_path,
    monkeypatch,
):
    annual_series = [
        {
            "year": year,
            "equivalent_depth_mm": {
                "GMv": 100.0 + index,
                "GMh": 20.0 + index,
                "MC": 10.0 + index,
                "CWR": 5.0 + index,
                "SP": 8.0 + index,
            },
            "values": {
                "CEv": 2.0 + index / 10,
                "RCh": 3.0 + index,
                "PEh": 20.0 + index,
            },
        }
        for index, year in enumerate(range(2021, 2026))
    ]
    captured = {}

    def capture_figure(fig, target, *, dpi):
        captured["figure"] = fig

    monkeypatch.setattr(
        "cwr_engine.business_metrics.cloud_water_multi_year_figures._save",
        capture_figure,
    )

    _render_interannual_sequence(
        annual_series,
        tmp_path / "interannual.png",
    )

    figure = captured["figure"]
    assert {axis.get_ylabel() for axis in figure.axes} == {
        "GMv",
        "CEv",
        "GMh",
        "Cvh",
        "CWR",
        "Ps",
        "RTh",
        "PEh",
    }
    assert all(axis.yaxis.label.get_fontsize() >= 24 for axis in figure.axes)
    year_axis = next(axis for axis in figure.axes if axis.get_xlabel() == "Year")
    assert all(
        label.get_fontsize() >= 21 for label in year_axis.get_xticklabels()
    )


def test_annual_maps_use_panel_labels_and_aligned_colorbars(
    tmp_path,
    monkeypatch,
):
    values = np.arange(9, dtype=float).reshape(3, 3) + 1
    spatial = xr.Dataset(
        {
            name: (("lat", "lon"), values * scale)
            for scale, name in enumerate(
                [f"pic3_{suffix}" for suffix in "abcdef"],
                start=1,
            )
        },
        coords={"lat": [40.0, 41.0, 42.0], "lon": [110.0, 111.0, 112.0]},
    )
    captured = {}

    def capture_figure(fig, target, *, dpi):
        captured["figure"] = fig

    monkeypatch.setattr(
        "cwr_engine.business_metrics.cloud_water_figures._save",
        capture_figure,
    )
    _render_annual_maps(
        spatial,
        np.ones((3, 3), dtype=bool),
        None,
        tmp_path / "annual.png",
    )

    figure = captured["figure"]
    figure.canvas.draw()
    map_axes = figure.axes[:6]
    colorbar_axes = figure.axes[6:]
    assert [axis.texts[0].get_text() for axis in map_axes] == [
        "(a)",
        "(b)",
        "(c)",
        "(d)",
        "(e)",
        "(f)",
    ]
    assert all(axis.get_title() == "" for axis in map_axes)
    assert [axis.get_title() for axis in colorbar_axes] == [
        "GMv",
        "CEv",
        "CWR",
        "GMh",
        "Ps",
        "PEh",
    ]
    assert all(not axis.get_xticklabels() for axis in map_axes[:4])
    assert all(not axis.get_yticklabels() for axis in map_axes[1::2])
    for map_axis, colorbar_axis in zip(map_axes, colorbar_axes):
        assert colorbar_axis.get_position().height == pytest.approx(
            map_axis.get_position().height,
            abs=0.01,
        )


def test_season_maps_use_panel_labels_and_full_height_colorbar(
    tmp_path,
    monkeypatch,
):
    values = np.arange(9, dtype=float).reshape(3, 3) + 1
    spatial = xr.Dataset(
        {
            f"season_{suffix}": (("lat", "lon"), values * scale)
            for scale, suffix in enumerate("abcd", start=1)
        },
        coords={"lat": [40.0, 41.0, 42.0], "lon": [110.0, 111.0, 112.0]},
    )
    captured = {}

    def capture_figure(fig, target, *, dpi):
        captured["figure"] = fig

    monkeypatch.setattr(
        "cwr_engine.business_metrics.cloud_water_figures._save",
        capture_figure,
    )
    _render_season_maps(
        spatial,
        np.ones((3, 3), dtype=bool),
        None,
        [f"season_{suffix}" for suffix in "abcd"],
        "Ps",
        tmp_path / "season.png",
        zero_based=True,
    )

    figure = captured["figure"]
    figure.canvas.draw()
    map_axes = figure.axes[:4]
    colorbar_axis = figure.axes[4]
    assert [axis.texts[0].get_text() for axis in map_axes] == [
        "(a)",
        "(b)",
        "(c)",
        "(d)",
    ]
    assert all(axis.get_title() == "" for axis in map_axes)
    assert colorbar_axis.get_title() == "Ps"
    assert all(not axis.get_xticklabels() for axis in map_axes[:2])
    assert all(not axis.get_yticklabels() for axis in map_axes[1::2])
    panel_bottom = min(axis.get_position().y0 for axis in map_axes)
    panel_top = max(axis.get_position().y1 for axis in map_axes)
    assert colorbar_axis.get_position().y0 == pytest.approx(panel_bottom)
    assert colorbar_axis.get_position().y1 == pytest.approx(panel_top)


def test_monthly_sequence_uses_approved_abbreviations_and_typography(
    tmp_path,
    monkeypatch,
):
    monthly = [
        {
            "month": month,
            "GMv_mm": 100.0 + month,
            "CEv": 2.0 + month / 10,
            "GMh_mm": 20.0 + month,
            "MC_mm": 10.0 + month,
            "CWR_mm": 5.0 + month,
            "SP_mm": 8.0 + month,
            "RCh": 2.0 + month,
            "PEh": 20.0 + month,
        }
        for month in range(1, 13)
    ]
    captured = {}

    def capture_figure(fig, target, *, dpi):
        captured["figure"] = fig

    monkeypatch.setattr(
        "cwr_engine.business_metrics.cloud_water_figures._save",
        capture_figure,
    )

    _render_monthly_sequence(
        {"monthly": monthly},
        tmp_path / "monthly.png",
    )

    figure = captured["figure"]
    labels = {axis.get_ylabel() for axis in figure.axes}
    assert labels == {
        "GMv",
        "CEv",
        "GMh",
        "Cvh",
        "CWR",
        "Ps",
        "RTh",
        "PEh",
    }
    assert all(axis.get_title() == "" for axis in figure.axes)
    assert all(axis.yaxis.label.get_fontsize() >= 24 for axis in figure.axes)
    assert all(
        label.get_fontsize() >= 24
        for axis in figure.axes
        for label in axis.get_yticklabels()
    )
    panel_labels = [
        text.get_text()
        for axis in figure.axes
        for text in axis.texts
        if text.get_text().startswith("(")
    ]
    assert panel_labels == ["(a)", "(b)", "(c)", "(d)"]
    month_axis = next(
        axis for axis in figure.axes if axis.get_xlabel() == "Month"
    )
    assert all(
        label.get_fontsize() >= 21 for label in month_axis.get_xticklabels()
    )
    assert all(
        label.get_rotation() == 45 for label in month_axis.get_xticklabels()
    )
    assert figure._suptitle is None


def test_region_preview_uses_approved_single_figure_typography(
    tmp_path,
    monkeypatch,
):
    spatial = xr.Dataset(
        coords={"lat": [40.0, 41.0], "lon": [110.0, 111.0]},
    )
    mask = np.ones((2, 2), dtype=bool)
    captured = {}

    def capture_figure(fig, target, *, dpi):
        captured["figure"] = fig

    monkeypatch.setattr(
        "cwr_engine.business_metrics.cloud_water_figures._save",
        capture_figure,
    )

    _render_region_preview(
        spatial,
        mask,
        box(109.5, 39.5, 111.5, 41.5),
        tmp_path / "region.png",
    )

    axis = captured["figure"].axes[0]
    assert axis.get_title() == "Cloud-Water Evaluation Region"
    assert axis.title.get_fontsize() >= 22
    assert all(label.get_fontsize() >= 22 for label in axis.get_xticklabels())
    assert all(label.get_fontsize() >= 22 for label in axis.get_yticklabels())
    legend = axis.get_legend()
    assert [text.get_text() for text in legend.get_texts()] == [
        "Grid centers",
        "Region boundary",
        "Mask boundary",
    ]
    assert all(text.get_fontsize() >= 22 for text in legend.get_texts())
    assert legend._ncols == 2


def test_figure_five_colorbar_uses_one_decimal_below_one_thousand():
    levels = _tidy_colorbar_levels(np.array([242.6675, 854.3877]))

    assert np.array_equal(
        levels,
        np.arange(200.0, 901.0, 100.0),
    )
    assert _tidy_colorbar_label(levels[0]) == "200.0"
    assert _tidy_colorbar_label(levels[-1]) == "900.0"


def test_figure_five_colorbar_uses_clean_hundreds_for_large_values():
    four_digit = _tidy_colorbar_levels(np.array([5103.0, 5547.0]))
    five_digit = _tidy_colorbar_levels(np.array([55021.0, 55618.0]))

    assert np.all(four_digit % 100 == 0)
    assert np.all(five_digit % 100 == 0)
    assert four_digit[0] <= 5103.0
    assert four_digit[-1] >= 5547.0
    assert five_digit[0] <= 55021.0
    assert five_digit[-1] >= 55618.0
    assert _tidy_colorbar_label(5331.0) == "5300"
    assert _tidy_colorbar_label(55618.0) == "55600"


def test_annual_map_panel_uses_tidy_colorbar_ticks():
    spatial = xr.Dataset(
        {
            "field": (
                ("lat", "lon"),
                np.array([[242.7, 400.0], [600.0, 854.4]]),
            )
        },
        coords={"lat": [40.0, 41.0], "lon": [110.0, 111.0]},
    )
    mask = np.ones((2, 2), dtype=bool)
    fig, ax = plt.subplots()
    try:
        _draw_map_panel(
            fig,
            ax,
            spatial,
            mask,
            None,
            "field",
            "Field",
            "mm",
        )
        labels = [
            label.get_text()
            for label in fig.axes[-1].get_yticklabels()
        ]
        assert labels == [
            "200.0",
            "600.0",
            "900.0",
        ]
        assert ax.texts[0].get_text() == "Field"
        assert fig.axes[-1].get_title() == "mm"
        assert all(
            label.get_fontsize() >= 23
            for label in fig.axes[-1].get_yticklabels()
        )
    finally:
        plt.close(fig)
