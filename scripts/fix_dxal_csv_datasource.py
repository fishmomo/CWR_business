from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "artifacts" / "examples" / "hlj_dxal_lq_test" / "csv"
FILES = [
    CSV_DIR / "hlj-dxal-lq_NCEP_00to25_Y.csv",
    CSV_DIR / "hlj-dxal-lq_NCEP_00to25_M.csv",
]


def main():
    for path in FILES:
        df = pd.read_csv(path)
        df["datasource"] = "NCEP"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(path)


if __name__ == "__main__":
    main()
