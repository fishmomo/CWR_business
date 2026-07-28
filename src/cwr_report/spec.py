from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReportSpec:
    report_id: str
    report_inputs: Path
    template: Path
    output: Path
    text_slots: dict[str, Any]
    narrative_slots: dict[str, dict[str, Any]]
    table_slots: dict[str, dict[str, Any]]
    image_slots: dict[str, dict[str, Any]]


def load_report_spec(path: Path) -> ReportSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    spec = ReportSpec(
        report_id=_required_text(payload, "report_id"),
        report_inputs=_resolve_path(base, payload, "report_inputs"),
        template=_resolve_path(base, payload, "template"),
        output=_resolve_path(base, payload, "output"),
        text_slots=_mapping(payload, "text_slots"),
        narrative_slots=_mapping(payload, "narrative_slots"),
        table_slots=_mapping(payload, "table_slots"),
        image_slots=_mapping(payload, "image_slots"),
    )
    if not spec.report_inputs.is_file():
        raise ValueError(f"Report inputs do not exist: {spec.report_inputs}")
    if not spec.template.is_file():
        raise ValueError(f"Report template does not exist: {spec.template}")
    if spec.output.suffix.lower() != ".docx":
        raise ValueError("Report output must use the .docx suffix")
    if spec.output.resolve() == spec.template.resolve():
        raise ValueError("Report output must not overwrite the template")
    return spec


def _required_text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _resolve_path(base: Path, payload: dict, key: str) -> Path:
    raw = _required_text(payload, key)
    path = Path(raw)
    return path if path.is_absolute() else (base / path).resolve()


def _mapping(payload: dict, key: str) -> dict:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value
