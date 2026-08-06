import argparse
import json
from pathlib import Path

from cwr_report.assembler import build_report
from cwr_report.profiles.cloud_water_single_year import (
    build_cloud_water_single_year_report,
)
from cwr_report.profiles.cloud_water_multi_year import (
    build_cloud_water_multi_year_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    requests = parser.add_mutually_exclusive_group(required=True)
    requests.add_argument("--spec")
    requests.add_argument("--profile-spec")
    args = parser.parse_args(argv)
    if args.spec:
        output = build_report(Path(args.spec))
    else:
        profile_path = Path(args.profile_spec)
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        profile = payload.get("profile")
        if profile == "cloud_water_single_year":
            output = build_cloud_water_single_year_report(profile_path)
        elif profile == "cloud_water_multi_year":
            output = build_cloud_water_multi_year_report(profile_path)
        else:
            parser.error(f"Unsupported profile: {profile}")
    print(output)
    return 0
