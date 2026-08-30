import argparse
import json
from pathlib import Path

from cwr_engine.business_request import run_business_request
from cwr_engine.business_metrics.cloud_water import (
    build_cloud_water_business_metrics,
)
from cwr_engine.pipeline import run_task
from cwr_engine.registries.thematic_products import THEMATIC_PRODUCTS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    requests = parser.add_mutually_exclusive_group(required=True)
    requests.add_argument("--task")
    requests.add_argument("--request")
    requests.add_argument("--business-metrics-spec")
    parser.add_argument("--output-root", required=False)
    args = parser.parse_args(argv)
    if args.request:
        request_path = Path(args.request)
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        request_set = request_payload.get("request_set")
        if request_set:
            if args.output_root:
                parser.error("--output-root cannot be used with request sets")
            try:
                product = THEMATIC_PRODUCTS.resolve(request_set)
            except LookupError as exc:
                parser.error(str(exc))
            output = product.builder(request_path)
        else:
            output = run_business_request(
                request_path,
                Path(args.output_root) if args.output_root else None,
            )
        print(output)
    elif args.business_metrics_spec:
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
