from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class Target:
    kind: str
    value: str

@dataclass
class TestResult:
    status: str
    kind: str
    target: str
    server: str
    server_port: int
    network: str
    elapsed_ms: int
    reason: str = ""
    config: dict[str, Any] | None = None

    def to_dict(self):
        return asdict(self)
