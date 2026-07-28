import argparse
from pathlib import Path

from cwr_report.assembler import build_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    output = build_report(Path(args.spec))
    print(output)
    return 0
