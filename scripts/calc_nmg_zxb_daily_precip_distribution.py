"""Map daily precipitation classes and their cumulative CWR for a region.

The NCEP daily files store mass-like fields.  SP and CWR are divided by dxy
before classification, matching the historical notebook implementation.  The
main result is the spatial distribution map; the dual-y-axis line plot is a
regional summary supplement.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# Allow ``python scripts/<script>.py`` from an uninstalled source checkout.
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from cwr_engine.precipitation import (
    DEFAULT_PRECIPITATION_CLASSES,
    classify_precipitation_cwr,
)


DEFAULT_DATA_DIR = Path(r"H:\NCEP_fixed\2025\p2_as_matlab")
DEFAULT_MASK_PATH = BASE / "artifacts" / "examples" / "nmg_zxb" / "mask" / "nmg-zxb.nc"
DEFAULT_OUTPUT_DIR = BASE / "artifacts" / "runs" / "nmg_zxb" / "daily_2025" / "precipitation_classes"


def load_region_mask(mask_path: Path) -> xr.DataArray:
    """Load the project mask, avoiding an extra GIS-library dependency."""

    with xr.open_dataset(mask_path) as dataset:
        if "ind_area_bool" not in dataset:
            raise KeyError(f"Expected variable 'ind_area_bool' in {mask_path}")
        mask = dataset["ind_area_bool"].rename({"lat": "latitude", "lon": "longitude"}).load()
    return mask.astype(bool)


def load_daily_fields(files: list[Path]) -> tuple[xr.DataArray, xr.DataArray]:
    precipitation: list[xr.DataArray] = []
    cwr: list[xr.DataArray] = []
    for path in files:
        with xr.open_dataset(path) as ds:
            date = np.asarray(ds["time"].values).astype("datetime64[ns]").reshape(-1)[0]
            precipitation.append((ds["SP"] / ds["dxy"]).expand_dims(time=[date]).load())
            cwr.append((ds["CWR"] / ds["dxy"]).expand_dims(time=[date]).load())
    return xr.concat(precipitation, dim="time").sortby("time"), xr.concat(cwr, dim="time").sortby("time")


def plot_distributions(data: xr.Dataset, output_path: Path) -> None:
    classes = DEFAULT_PRECIPITATION_CLASSES
    fig, axes = plt.subplots(2, len(classes), figsize=(16, 7), dpi=180, constrained_layout=True)
    first_field = data[f"{classes[0].name}_days"]
    valid_latitudes = first_field.latitude.where(first_field.notnull().any("longitude"), drop=True)
    valid_longitudes = first_field.longitude.where(first_field.notnull().any("latitude"), drop=True)
    x_limits = (float(valid_longitudes.min()) - 0.5, float(valid_longitudes.max()) + 0.5)
    y_limits = (float(valid_latitudes.min()) - 0.5, float(valid_latitudes.max()) + 0.5)
    for index, item in enumerate(classes):
        label = f"{item.lower_mm:g}–{item.upper_mm:g}" if item.upper_mm is not None else f">{item.lower_mm:g}"
        for row, suffix, title, cmap in (
            (0, "days", "Precipitation days", "YlGnBu"),
            (1, "cwr_mm", "Cumulative CWR", "YlOrRd"),
        ):
            ax = axes[row, index]
            field = data[f"{item.name}_{suffix}"]
            if float(field.max(skipna=True)) == 0:
                ax.pcolormesh(field.longitude, field.latitude, field, shading="auto", cmap=cmap, vmin=0, vmax=1)
                ax.text(0.5, 0.5, "No events", transform=ax.transAxes, ha="center", va="center")
            else:
                image = ax.pcolormesh(field.longitude, field.latitude, field, shading="auto", cmap=cmap)
                colorbar = fig.colorbar(image, ax=ax, shrink=0.85)
                colorbar.set_label(field.attrs["units"])
            ax.set_title(f"{label} mm\n{title}")
            ax.set_xlabel("Longitude")
            ax.set_xlim(*x_limits)
            ax.set_ylim(*y_limits)
            if index == 0:
                ax.set_ylabel("Latitude")
    fig.suptitle(f"Daily precipitation classes and cumulative CWR ({data.attrs['sample_days']} available days)")
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def plot_dual_axis_summary(data: xr.Dataset, output_path: Path) -> None:
    """Plot regional mean occurrence days and cumulative CWR by class."""

    labels = []
    mean_days = []
    mean_cwr = []
    for item in DEFAULT_PRECIPITATION_CLASSES:
        upper = f"{item.upper_mm:g}" if item.upper_mm is not None else "∞"
        labels.append(f"({item.lower_mm:g}, {upper}]")
        mean_days.append(float(data[f"{item.name}_days"].mean(skipna=True)))
        mean_cwr.append(float(data[f"{item.name}_cwr_mm"].mean(skipna=True)))

    positions = np.arange(len(labels))
    fig, left_axis = plt.subplots(figsize=(10, 5.5), dpi=200)
    right_axis = left_axis.twinx()
    first_line = left_axis.plot(
        positions, mean_days, color="#2878B5", marker="o", linewidth=2.4,
        markersize=7, label="Mean precipitation days",
    )
    second_line = right_axis.plot(
        positions, mean_cwr, color="#C82423", marker="s", linewidth=2.4,
        markersize=6.5, label="Mean cumulative CWR",
    )
    left_axis.set_xticks(positions, labels)
    left_axis.set_xlabel("Daily precipitation class (mm)")
    left_axis.set_ylabel("Regional grid-cell mean precipitation days", color="#2878B5")
    right_axis.set_ylabel("Regional grid-cell mean cumulative CWR (mm)", color="#C82423")
    left_axis.tick_params(axis="y", labelcolor="#2878B5")
    right_axis.tick_params(axis="y", labelcolor="#C82423")
    left_axis.set_ylim(bottom=0)
    right_axis.set_ylim(bottom=0)
    left_axis.grid(axis="y", alpha=0.25)
    left_axis.set_title(f"Precipitation classes and corresponding cumulative CWR ({data.attrs['sample_days']} days)")
    handles = first_line + second_line
    left_axis.legend(handles, [handle.get_label() for handle in handles], loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def write_summary(data: xr.Dataset, output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["class", "precipitation_range_mm", "mean_precipitation_days", "mean_cumulative_cwr_mm"])
        for item in DEFAULT_PRECIPITATION_CLASSES:
            upper = f"{item.upper_mm:g}" if item.upper_mm is not None else "inf"
            writer.writerow(
                [
                    item.name,
                    f"({item.lower_mm:g}, {upper}]",
                    f"{float(data[f'{item.name}_days'].mean(skipna=True)):.3f}",
                    f"{float(data[f'{item.name}_cwr_mm'].mean(skipna=True)):.3f}",
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--mask-path", type=Path, default=DEFAULT_MASK_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pattern", default="ResultGrid_D_2025-*.nc")
    args = parser.parse_args()
    files = sorted(args.data_dir.glob(args.pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {args.pattern!r} under {args.data_dir}")

    precipitation, cwr = load_daily_fields(files)
    mask = load_region_mask(args.mask_path)
    if not bool(mask.any()):
        raise ValueError("The study-area mask contains no CRA40 grid cells")
    result = classify_precipitation_cwr(precipitation, cwr, mask)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    netcdf_path = args.output_dir / "nmg-zxb_2025_precipitation_class_distribution.nc"
    figure_path = args.output_dir / "nmg-zxb_2025_precipitation_class_distribution.png"
    dual_axis_path = args.output_dir / "nmg-zxb_2025_precipitation_classes_dual_axis.png"
    summary_path = args.output_dir / "nmg-zxb_2025_precipitation_class_summary.csv"
    result.to_netcdf(netcdf_path)
    plot_distributions(result, figure_path)
    plot_dual_axis_summary(result, dual_axis_path)
    write_summary(result, summary_path)
    print(f"NetCDF: {netcdf_path}")
    print(f"Main spatial-distribution figure: {figure_path}")
    print(f"Supplementary dual-axis summary: {dual_axis_path}")
    print(f"Summary: {summary_path}")
    print(f"Coverage: {str(precipitation.time.values[0])[:10]} to {str(precipitation.time.values[-1])[:10]} ({result.attrs['sample_days']} days)")


if __name__ == "__main__":
    main()
