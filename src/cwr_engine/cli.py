import argparse
from pathlib import Path

from cwr_engine.pipeline import run_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-root", required=False)
    args = parser.parse_args(argv)
    run_task(
        task_path=Path(args.task),
        output_root=Path(args.output_root) if args.output_root else None,
    )
    return 0
