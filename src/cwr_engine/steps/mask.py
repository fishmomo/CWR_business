from cwr_engine.cache import build_mask_signature
from cwr_engine.models.region import MaskBundle


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("mask")
    task = context["task"]
    payload = task.region_spec.payload
    grid_definition = {"lat": "lat", "lon": "lon", "resolution": "demo-grid"}
    signature = build_mask_signature(
        {"kind": task.region_spec.kind, "payload": payload},
        grid_definition,
    )
    context["mask_bundle"] = MaskBundle(
        mask_path=str(context["output_root"] / "mask" / "mask_bundle.json"),
        preview_path=str(context["output_root"] / "mask" / "mask_preview.png"),
        grid_definition=grid_definition,
        signature=signature,
    )
    return context
