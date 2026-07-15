from dataclasses import dataclass
from datetime import date
from calendar import monthrange


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
    if scale == "month":
        year = int(payload["year"])
        month = int(payload["month"])
        last_day = monthrange(year, month)[1]
        return TimeSlice(
            scale="month",
            start=f"{year}-{month:02d}-01",
            end=f"{year}-{month:02d}-{last_day:02d}",
            label=f"{year}-{month:02d}",
        )
    if scale == "day":
        day_value = payload.get("day") or payload.get("date")
        normalized = date.fromisoformat(day_value)
        day_text = normalized.isoformat()
        return TimeSlice(
            scale="day",
            start=day_text,
            end=day_text,
            label=day_text,
        )
    return TimeSlice(
        scale=scale,
        start=payload["start"],
        end=payload["end"],
        label=payload["label"],
    )
