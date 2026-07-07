from dataclasses import dataclass


@dataclass(frozen=True)
class OutputRequest:
    kind: str
    name: str
