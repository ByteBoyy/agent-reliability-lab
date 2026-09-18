from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .models import ToolCall, ToolResult
from .store import RunStore


class ApprovalRequired(RuntimeError):
    pass


class RetryExhausted(RuntimeError):
    pass


Tool = Callable[[dict[str, Any]], dict[str, Any]]


class ReliableExecutor:
    def __init__(self, store: RunStore, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.store = store
        self.max_attempts = max_attempts

    def execute(self, call: ToolCall, tool: Tool) -> ToolResult:
        cached = self.store.result_for(call.idempotency_key)
        if cached:
            output, attempts = cached
            return ToolResult(call.idempotency_key, output, attempts, replayed=True)

        if call.requires_approval and not self.store.is_approved(call.idempotency_key):
            raise ApprovalRequired(call.idempotency_key)

        for attempt in range(1, self.max_attempts + 1):
            try:
                output = tool(call.arguments)
            except Exception as exc:
                if attempt == self.max_attempts:
                    raise RetryExhausted(
                        f"{call.name} failed after {attempt} attempts"
                    ) from exc
            else:
                self.store.save_result(call.idempotency_key, output, attempt)
                return ToolResult(call.idempotency_key, output, attempt)

        raise AssertionError("retry loop exited unexpectedly")

