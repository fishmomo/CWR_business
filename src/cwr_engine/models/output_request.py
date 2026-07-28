from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OutputRequest:
    kind: str
    name: str
    params: dict[str, Any] = field(default_factory=dict)
