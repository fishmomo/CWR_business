import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water_figures import (
    _draw_map_panel,
    _tidy_colorbar_label,
    _tidy_colorbar_levels,
)


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
