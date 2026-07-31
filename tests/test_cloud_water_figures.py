import numpy as np

from cwr_engine.business_metrics.cloud_water_figures import (
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
