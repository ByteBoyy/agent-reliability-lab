from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    PENDING = "pending"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ToolCall:
    run_id: str
    name: str
    arguments: dict[str, Any]
    idempotency_key: str
    requires_approval: bool = False


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_key: str
    output: dict[str, Any]
    attempts: int
    replayed: bool = False

