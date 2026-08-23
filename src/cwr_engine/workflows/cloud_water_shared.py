from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4


def finalize_report_inputs(
    path: Path,
    staged_output: Path,
    final_output: Path,
    report_filename: str,
    *,
    workflow_name: str,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload = rebase_paths(payload, staged_output, final_output)
    payload["inputs"]["workflow"] = workflow_name
    payload["artifacts"].append(
        {
            "kind": "docx_report",
            "name": Path(report_filename).stem,
            "profile": workflow_name,
            "schema_version": 1,
            "path": str(final_output / "report" / report_filename),
        }
    )
    steps = payload["runtime"]["workflow_steps"]
    executed = payload["runtime"]["executed_steps"]
    if "docx_report" not in steps:
        steps.append("docx_report")
    if "docx_report" not in executed:
        executed.append("docx_report")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_request_set_manifest(
    path: Path,
    request_set_id: str,
    request_set: str,
    members: list[dict[str, Any]],
    product_report_inputs: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "request_set_id": request_set_id,
        "request_set": request_set,
        "members": members,
        "product_report_inputs": str(product_report_inputs),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def rebase_paths(value: Any, source_root: Path, target_root: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: rebase_paths(item, source_root, target_root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            rebase_paths(item, source_root, target_root) for item in value
        ]
    if not isinstance(value, str):
        return value
    try:
        relative = Path(value).resolve().relative_to(source_root.resolve())
    except (OSError, ValueError):
        return value
    return str(target_root / relative)


def publish_directory(staged: Path, target: Path) -> None:
    backup: Path | None = None
    if target.exists():
        backup = target.parent / f".{target.name}-backup-{uuid4().hex}"
        target.replace(backup)
    try:
        staged.replace(target)
    except Exception:
        if backup is not None and backup.exists():
            backup.replace(target)
        raise
    if backup is not None:
        shutil.rmtree(backup)
