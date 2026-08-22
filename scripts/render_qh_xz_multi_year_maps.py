"""Render the Qinghai--Tibet 2000--2025 multi-year mean map with fixed scales."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water_figures import (
    _draw_map_panel,
    _region_geometry,
    _save,
)


ROOT = Path(__file__).resolve().parents[1]
SPATIAL_PATH = ROOT / "artifacts/examples/qh-xz/pic/multi/qh-xz_picdata.nc"
MASK_PATH = ROOT / "artifacts/examples/qh-xz/mask/qh-xz.nc"
OUTPUT_PATH = ROOT / "artifacts/runs/qh-xz-2000-2025/multi_year_mean_distribution.png"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shp", type=Path, required=True)
    parser.add_argument("--spatial", type=Path, default=SPATIAL_PATH)
    parser.add_argument("--mask", type=Path, default=MASK_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    spatial = xr.open_dataset(args.spatial).load()
    mask_dataset = xr.open_dataset(args.mask).load()
    spatial["ind_area_bool"] = mask_dataset["ind_area_bool"]
    mask = spatial["ind_area_bool"].values.astype(bool)
    geometry = _region_geometry(
        {"kind": "shp", "payload": {"path": str(args.shp)}}
    )

    # GMv and Ps use the requested fixed report scales.  The other four panels
    # retain the auto-generated tidy levels used by the project figure style.
    panels = [
        ("pic4_a", "mm", np.arange(6000, 30000 + 3000, 3000), "max"),
        ("pic4_b", "%", None, "neither"),
        ("pic4_c", "mm", None, "neither"),
        ("pic4_d", "mm", None, "neither"),
        ("pic4_e", "mm", np.arange(300, 1500 + 150, 150), "both"),
        ("pic4_f", "%", None, "neither"),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(11.0, 7.4))
    try:
        for index, (field, unit, levels, extend) in enumerate(panels):
            row, column = divmod(index, 2)
            _draw_map_panel(
                fig,
                axes.flat[index],
                spatial,
                mask,
                geometry,
                field,
                f"({chr(ord('a') + index)})",
                unit,
                levels=levels,
                extend=extend,
                colorbar_tick_labelsize=16,
                colorbar_labelsize=16,
                colorbar_max_ticks=5,
                show_x_labels=row == 2,
                show_y_labels=column == 0,
            )
        fig.subplots_adjust(hspace=0.48, wspace=0.35)
        _save(fig, args.output, dpi=180)
    finally:
        plt.close(fig)


if __name__ == "__main__":
    main()
