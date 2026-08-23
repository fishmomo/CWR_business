import argparse
import json
from pathlib import Path

from cwr_engine.business_request import run_business_request
from cwr_engine.business_metrics.cloud_water import (
    build_cloud_water_business_metrics,
)
from cwr_engine.pipeline import run_task
from cwr_engine.workflows.cloud_water_single_year import (
    build_cloud_water_single_year_workflow,
)
from cwr_engine.workflows.cloud_water_multi_year import (
    build_cloud_water_multi_year_workflow,
)
from cwr_engine.workflows.cloud_water_single_year_request import (
    build_cloud_water_single_year_request_set,
    load_request_set,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    requests = parser.add_mutually_exclusive_group(required=True)
    requests.add_argument("--task")
    requests.add_argument("--request")
    requests.add_argument("--business-metrics-spec")
    requests.add_argument("--workflow-spec")
    parser.add_argument("--output-root", required=False)
    args = parser.parse_args(argv)
    if args.request:
        request_path = Path(args.request)
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        if request_payload.get("request_set"):
            if args.output_root:
                parser.error("--output-root cannot be used with request sets")
            output = build_cloud_water_single_year_request_set(request_path)
        else:
            output = run_business_request(
                request_path,
                Path(args.output_root) if args.output_root else None,
            )
        print(output)
    elif args.workflow_spec:
        if args.output_root:
            parser.error("--output-root cannot be used with --workflow-spec")
        workflow_path = Path(args.workflow_spec)
        workflow_payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        workflow = workflow_payload.get("workflow")
        if workflow == "cloud_water_single_year":
            output = build_cloud_water_single_year_workflow(workflow_path)
        elif workflow == "cloud_water_multi_year":
            output = build_cloud_water_multi_year_workflow(workflow_path)
        else:
            parser.error(f"Unsupported workflow: {workflow}")
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
