from dataclasses import dataclass


@dataclass(frozen=True)
class TimeSlice:
    scale: str
    start: str
    end: str
    label: str


def normalize_time_slice(payload: dict) -> TimeSlice:
    scale = payload["scale"]
    if scale == "year":
        year = int(payload["year"])
        return TimeSlice(
            scale="year",
            start=f"{year}-01-01",
            end=f"{year}-12-31",
            label=str(year),
        )
    return TimeSlice(
        scale=scale,
        start=payload["start"],
        end=payload["end"],
        label=payload["label"],
    )
