import argparse
from pathlib import Path

from cwr_engine.business_metrics.cloud_water import (
    build_cloud_water_business_metrics,
)
from cwr_engine.pipeline import run_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    requests = parser.add_mutually_exclusive_group(required=True)
    requests.add_argument("--task")
    requests.add_argument("--business-metrics-spec")
    parser.add_argument("--output-root", required=False)
    args = parser.parse_args(argv)
    if args.business_metrics_spec:
        if args.output_root:
            parser.error(
                "--output-root cannot be used with --business-metrics-spec"
            )
        output = build_cloud_water_business_metrics(
            Path(args.business_metrics_spec)
        )
        print(output)
    else:
        run_task(
            task_path=Path(args.task),
            output_root=Path(args.output_root) if args.output_root else None,
        )
    return 0
