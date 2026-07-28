import argparse
from pathlib import Path

from cwr_report.assembler import build_report
from cwr_report.profiles.cloud_water_single_year import (
    build_cloud_water_single_year_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    requests = parser.add_mutually_exclusive_group(required=True)
    requests.add_argument("--spec")
    requests.add_argument("--profile-spec")
    args = parser.parse_args(argv)
    output = (
        build_report(Path(args.spec))
        if args.spec
        else build_cloud_water_single_year_report(Path(args.profile_spec))
    )
    print(output)
    return 0
