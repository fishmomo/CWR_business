import calendar
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts" / "examples" / "hlj_dxal_lq_test"
MONTH_CSV = BASE / "csv" / "hlj-dxal-lq_NCEP_00to25_M.csv"
YEAR_START = 2000
YEAR_END = 2025

SEASONS = {
    "spring_03_05": [3, 4, 5],
    "autumn_09_11": [9, 10, 11],
}

MM_VARS = {
    "GMv": "GMv",
    "GMh": "GMh",
    "Cvh": "MC",
    "CWR": "CWR",
    "Ps": "SP",
}

RANGE_RULES = {
    "GMv_mm": (0, None),
    "GMh_mm": (0, None),
    "Cvh_mm": (0, None),
    "CWR_mm": (0, None),
    "Ps_mm": (0, None),
    "CEv_percent": (0, 100),
    "PEh_percent": (0, 100),
    "RTh_hour": (0, 300),
}


def main():
    df = pd.read_csv(MONTH_CSV)
    df["date"] = pd.to_datetime(df["time"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df = df[(df["year"] >= YEAR_START) & (df["year"] <= YEAR_END)].copy()
    dxy = float(df["dxy"].iloc[0])

    rows = []
    for year in range(YEAR_START, YEAR_END + 1):
        for season, months in SEASONS.items():
            sub = df[(df["year"] == year) & (df["month"].isin(months))].copy()
            if len(sub) != len(months):
                raise ValueError(f"{year} {season} rows={len(sub)}, expected={len(months)}")

            totals = {out_name: float(sub[col].sum()) for out_name, col in MM_VARS.items()}
            ave_mh_mean = float(sub["aveMh"].mean())
            days = sum(calendar.monthrange(year, month)[1] for month in months)
            row = {
                "year": year,
                "season": season,
                "months": "-".join(f"{month:02d}" for month in months),
                "month_count": len(sub),
                "days": days,
            }
            for out_name, total in totals.items():
                row[f"{out_name}_mm"] = total / dxy

            row["CEv_percent"] = totals["CWR"] / totals["GMv"] * 100
            row["PEh_percent"] = totals["Ps"] / totals["GMh"] * 100
            row["RTh_hour"] = ave_mh_mean / (totals["Ps"] / (days * 24))
            rows.append(row)

    yearly = pd.DataFrame(rows)
    value_cols = [
        col
        for col in yearly.columns
        if col.endswith("_mm") or col.endswith("_percent") or col.endswith("_hour")
    ]
    mean = yearly.groupby("season", as_index=False)[value_cols].mean()
    mean.insert(1, "year_range", f"{YEAR_START}-{YEAR_END}")

    yearly_path = BASE / "csv" / "hlj-dxal-lq_NCEP_2000_2025_spring_autumn_yearly.csv"
    spring_path = BASE / "csv" / "hlj-dxal-lq_NCEP_2000_2025_spring_03_05_yearly.csv"
    autumn_path = BASE / "csv" / "hlj-dxal-lq_NCEP_2000_2025_autumn_09_11_yearly.csv"
    mean_path = BASE / "csv" / "hlj-dxal-lq_NCEP_2000_2025_spring_autumn_mean.csv"
    check_path = BASE / "csv" / "hlj-dxal-lq_NCEP_2000_2025_spring_autumn_check.txt"

    yearly.to_csv(yearly_path, index=False, encoding="utf-8-sig")
    yearly[yearly["season"] == "spring_03_05"].to_csv(spring_path, index=False, encoding="utf-8-sig")
    yearly[yearly["season"] == "autumn_09_11"].to_csv(autumn_path, index=False, encoding="utf-8-sig")
    mean.to_csv(mean_path, index=False, encoding="utf-8-sig")

    range_failures = []
    for col, (lower, upper) in RANGE_RULES.items():
        if lower is not None:
            bad = yearly[yearly[col] < lower]
            if not bad.empty:
                range_failures.append(f"{col} below {lower}: {len(bad)}")
        if upper is not None:
            bad = yearly[yearly[col] > upper]
            if not bad.empty:
                range_failures.append(f"{col} above {upper}: {len(bad)}")

    check_lines = [
        f"source={MONTH_CSV}",
        f"year_range={YEAR_START}-{YEAR_END}",
        f"row_count={len(yearly)}",
        f"expected_row_count={(YEAR_END - YEAR_START + 1) * len(SEASONS)}",
        f"dxy={dxy}",
        "spring_months=03,04,05",
        "autumn_months=09,10,11",
        "quantity_units=GMv/GMh/Cvh/CWR/Ps:mm; CEv/PEh:%; RTh:hour",
        "aggregation=water quantities summed over season then divided by dxy; CEv=CWR/GMv*100; PEh=Ps/GMh*100; RTh=mean(aveMh)/(sum(Ps)/(season_days*24))",
        f"missing_values={int(yearly[value_cols].isna().sum().sum())}",
        "range_rules=" + "; ".join(
            f"{col}[{lower if lower is not None else '-inf'},{upper if upper is not None else '+inf'}]"
            for col, (lower, upper) in RANGE_RULES.items()
        ),
        "range_check=" + ("OK" if not range_failures else "FAIL: " + "; ".join(range_failures)),
    ]
    check_path.write_text("\n".join(check_lines), encoding="utf-8")

    print(yearly_path)
    print(spring_path)
    print(autumn_path)
    print(mean_path)
    print(check_path)
    print(mean.round(3).to_string(index=False))
    print("\n".join(check_lines))


if __name__ == "__main__":
    main()
