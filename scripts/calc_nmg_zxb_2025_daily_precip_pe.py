"""Calculate daily regional precipitation and precipitation efficiency for nmg-zxb."""

from __future__ import annotations

import csv
import glob
import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.dates import DateFormatter, MonthLocator


BASE = Path(__file__).resolve().parents[1]
DATA_DIR = Path(r"H:\NCEP_fixed\2025\p2_as_matlab")
SHP_PATH = BASE / "data" / "inputs" / "内蒙古中西部" / "内蒙古中西部_7盟市融合研究区.shp"
GEOJSON_PATH = BASE / "data" / "inputs" / "内蒙古中西部" / "内蒙古中西部_7盟市融合研究区.geojson"
OUT_DIR = BASE / "artifacts" / "runs" / "nmg_zxb" / "daily_2025"
CSV_PATH = OUT_DIR / "nmg-zxb_2025_daily_precipitation_pe.csv"
FIG_PATH = OUT_DIR / "nmg-zxb_2025_daily_precipitation_pe.png"


def region_mask(latitudes: np.ndarray, longitudes: np.ndarray) -> np.ndarray:
    with GEOJSON_PATH.open(encoding="utf-8") as f:
        feature = json.load(f)["features"][0]
    rings = feature["geometry"]["coordinates"]

    def in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
        inside = False
        for i, (x1, y1) in enumerate(ring):
            x2, y2 = ring[(i + 1) % len(ring)]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        return inside

    def in_polygon(x: float, y: float) -> bool:
        return in_ring(x, y, rings[0]) and not any(in_ring(x, y, hole) for hole in rings[1:])

    lon_grid, lat_grid = np.meshgrid(longitudes, latitudes)
    flat = [in_polygon(lon, lat) for lon, lat in zip(lon_grid.ravel(), lat_grid.ravel())]
    return np.asarray(flat, dtype=bool).reshape(lat_grid.shape)


def main() -> None:
    files = sorted(glob.glob(str(DATA_DIR / "ResultGrid_D_2025-*.nc")))
    if not files:
        raise FileNotFoundError(f"No 2025 daily files found under {DATA_DIR}")

    first = xr.open_dataset(files[0])
    try:
        lat = first["latitude"].values
        lon = first["longitude"].values
    finally:
        first.close()
    mask = region_mask(lat, lon)
    if not mask.any():
        raise ValueError("The region mask contains no CRA40 grid cells")

    rows: list[dict[str, float | str]] = []
    for path in files:
        with xr.open_dataset(path) as ds:
            sp = np.asarray(ds["SP"].values, dtype=float)
            gmh = np.asarray(ds["GMh"].values, dtype=float)
            dxy = np.asarray(ds["dxy"].values, dtype=float)
            date = np.datetime_as_string(ds["time"].values, unit="D")
            dxy_region = float(np.nansum(dxy[mask]))
            sp_region = float(np.nansum(sp[mask]))
            gmh_region = float(np.nansum(gmh[mask]))
            precipitation_mm = sp_region / dxy_region
            peh_pct = sp_region / gmh_region * 100.0 if gmh_region else np.nan
            rows.append(
                {
                    "date": date,
                    "precipitation_mm": precipitation_mm,
                    "precipitation_efficiency_pct": peh_pct,
                    "sp_kg": sp_region,
                    "gmh_kg": gmh_region,
                    "grid_area_m2": dxy_region,
                }
            )

    rows.sort(key=lambda r: str(r["date"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    dates = [datetime.strptime(str(r["date"]), "%Y-%m-%d") for r in rows]
    precip = np.array([float(r["precipitation_mm"]) for r in rows])
    peh = np.array([float(r["precipitation_efficiency_pct"]) for r in rows])
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(13, 7.8), dpi=180)
    ax1.bar(dates, precip, width=0.8, color="#4C78A8", alpha=0.78, label="Daily precipitation")
    ax2.plot(dates, peh, color="#D62728", linewidth=1.8, marker="o", markersize=2.8, label="Precipitation efficiency")
    ax1.set_ylabel("Daily precipitation (mm)")
    ax2.set_ylabel("Precipitation efficiency PEh (%)")
    ax2.set_xlabel("Date")
    fig.suptitle("Inner Mongolia Central-Western Region: Daily Precipitation and PEh\n2025 (NCEP daily data)")
    ax1.set_title("(a) Daily precipitation", loc="left")
    ax2.set_title("(b) Daily precipitation efficiency", loc="left")
    ax2.xaxis.set_major_locator(MonthLocator())
    ax2.xaxis.set_major_formatter(DateFormatter("%Y-%m"))
    ax1.grid(axis="y", alpha=0.25)
    ax2.grid(axis="y", alpha=0.25)
    ax1.legend(loc="upper left", frameon=False)
    ax2.legend(loc="upper left", frameon=False)
    fig.text(0.01, 0.01, f"Data files: {len(rows)} days; region grid cells: {int(mask.sum())}; PEh = SP / GMh × 100%", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG_PATH, bbox_inches="tight")
    plt.close(fig)
    print(f"CSV: {CSV_PATH}")
    print(f"Figure: {FIG_PATH}")
    print(f"Coverage: {rows[0]['date']} to {rows[-1]['date']} ({len(rows)} days)")


if __name__ == "__main__":
    main()
