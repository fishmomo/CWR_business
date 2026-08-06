from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water_figures import (
    _region_geometry,
    _render_annual_maps,
    _render_monthly_sequence,
    _render_region_preview,
    _render_season_maps,
    _save,
)


IMAGE_SLOTS = [f"target_image{index}" for index in range(1, 7)]


def render_cloud_water_multi_year_figures(
    metrics: dict[str, Any],
    spatial: xr.Dataset,
    region_spec: dict[str, Any],
    targets: dict[str, Path],
) -> None:
    if set(targets) != set(IMAGE_SLOTS):
        raise ValueError("Multi-year figure targets must contain six images")
    mask = spatial["ind_area_bool"].values.astype(bool)
    if not mask.any():
        raise ValueError("Multi-year figure mask contains no grid cells")
    geometry = _region_geometry(region_spec)
    _render_region_preview(
        spatial,
        mask,
        geometry,
        targets["target_image1"],
    )
    _render_monthly_sequence(
        {"monthly": metrics["monthly_climatology"]},
        targets["target_image2"],
    )
    _render_interannual_sequence(
        metrics["annual_series"],
        targets["target_image3"],
    )
    annual = _annual_map_aliases(spatial)
    _render_annual_maps(
        annual,
        mask,
        geometry,
        targets["target_image4"],
    )
    seasonal = _season_map_aliases(spatial)
    _render_season_maps(
        seasonal,
        mask,
        geometry,
        [f"pic4_{suffix}" for suffix in "abcd"],
        targets["target_image5"],
        zero_based=True,
    )
    _render_season_maps(
        seasonal,
        mask,
        geometry,
        [f"pic5_{suffix}" for suffix in "abcd"],
        targets["target_image6"],
        zero_based=False,
    )


def _render_interannual_sequence(
    annual_series: list[dict[str, Any]],
    target: Path,
) -> None:
    if len(annual_series) < 5:
        raise ValueError("Interannual figure requires at least five years")
    years = [int(row["year"]) for row in annual_series]
    if years != list(range(years[0], years[-1] + 1)):
        raise ValueError("Interannual figure years must be contiguous")
    panels = [
        (
            lambda row: row["equivalent_depth_mm"]["GMv"],
            lambda row: row["values"]["CEv"],
            "GMv (mm)",
            "CEv (%)",
        ),
        (
            lambda row: row["equivalent_depth_mm"]["GMh"],
            lambda row: row["equivalent_depth_mm"]["MC"],
            "GMh (mm)",
            "MC (mm)",
        ),
        (
            lambda row: row["equivalent_depth_mm"]["CWR"],
            lambda row: row["equivalent_depth_mm"]["SP"],
            "CWR (mm)",
            "SP (mm)",
        ),
        (
            lambda row: row["values"]["RCh"],
            lambda row: row["values"]["PEh"],
            "RCh (hour)",
            "PEh (%)",
        ),
    ]
    positions = np.arange(len(years))
    fig, axes = plt.subplots(4, 1, figsize=(8.0, 10.6), sharex=True)
    try:
        for index, (bar_value, line_value, bar_label, line_label) in enumerate(
            panels
        ):
            ax = axes[index]
            twin = ax.twinx()
            bars = np.asarray([bar_value(row) for row in annual_series], dtype=float)
            line = np.asarray([line_value(row) for row in annual_series], dtype=float)
            if not np.all(np.isfinite(bars)) or not np.all(np.isfinite(line)):
                raise ValueError("Interannual figure contains non-finite data")
            ax.bar(positions, bars, width=0.52, color="#1454d8", zorder=2)
            twin.plot(
                positions,
                line,
                color="#111111",
                marker="o",
                linewidth=1.7,
                markersize=4.8,
                zorder=3,
            )
            _pad_axis(ax, bars)
            _pad_axis(twin, line)
            ax.set_ylabel(bar_label, color="#1454d8")
            twin.set_ylabel(line_label, color="#111111")
            ax.tick_params(axis="y", colors="#1454d8", direction="in")
            twin.tick_params(axis="y", colors="#111111", direction="in")
            ax.text(
                0.02,
                0.88,
                f"({chr(ord('a') + index)})",
                transform=ax.transAxes,
                fontsize=12,
            )
            ax.grid(axis="y", color="#d8d8d8", linewidth=0.6, alpha=0.7)
        axes[-1].set_xticks(positions)
        axes[-1].set_xticklabels(years, rotation=45 if len(years) > 12 else 0)
        axes[-1].set_xlabel("Year")
        fig.subplots_adjust(hspace=0.2, left=0.14, right=0.86)
        _save(fig, target, dpi=180)
    finally:
        plt.close(fig)


def _pad_axis(ax, values: np.ndarray) -> None:
    lower = float(values.min())
    upper = float(values.max())
    spread = upper - lower
    padding = spread * 0.2 if spread else max(abs(upper) * 0.05, 1.0)
    ax.set_ylim(lower - padding, upper + padding)


def _annual_map_aliases(spatial: xr.Dataset) -> xr.Dataset:
    names = {
        "pic3_a": "annual_mean_gmv_mm",
        "pic3_b": "annual_mean_cev_percent",
        "pic3_c": "annual_mean_cwr_mm",
        "pic3_d": "annual_mean_gmh_mm",
        "pic3_e": "annual_mean_sp_mm",
        "pic3_f": "annual_mean_peh_percent",
    }
    return xr.Dataset(
        {alias: spatial[source] for alias, source in names.items()},
        coords={"lat": spatial["lat"], "lon": spatial["lon"]},
    )


def _season_map_aliases(spatial: xr.Dataset) -> xr.Dataset:
    values = {}
    for index, season in enumerate(["spring", "summer", "autumn", "winter"]):
        suffix = chr(ord("a") + index)
        values[f"pic4_{suffix}"] = spatial["seasonal_mean_sp_mm"].sel(
            season=season,
            drop=True,
        )
        values[f"pic5_{suffix}"] = spatial["seasonal_mean_cwr_mm"].sel(
            season=season,
            drop=True,
        )
    return xr.Dataset(
        values,
        coords={"lat": spatial["lat"], "lon": spatial["lon"]},
    )
