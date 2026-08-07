import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box
import xarray as xr

from cwr_engine.business_metrics.cloud_water_figures import (
    _draw_map_panel,
    _render_monthly_sequence,
    _render_region_preview,
    _tidy_colorbar_label,
    _tidy_colorbar_levels,
)


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
            "300.0",
            "400.0",
            "500.0",
            "600.0",
            "700.0",
            "800.0",
            "900.0",
        ]
    finally:
        plt.close(fig)
