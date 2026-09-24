from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager
from threading import Lock
from typing import Any

from .models import ToolCall, ToolResult
from .store import RunStore


class ApprovalRequired(RuntimeError):
    pass


class RetryExhausted(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


Tool = Callable[[dict[str, Any]], dict[str, Any]]


class ReliableExecutor:
    def __init__(self, store: RunStore, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.store = store
        self.max_attempts = max_attempts
        self._key_locks: dict[str, tuple[Lock, int]] = {}
        self._key_locks_guard = Lock()

    @contextmanager
    def _serialize_key(self, key: str):
        with self._key_locks_guard:
            lock, users = self._key_locks.get(key, (Lock(), 0))
            self._key_locks[key] = (lock, users + 1)

        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._key_locks_guard:
                current_lock, users = self._key_locks[key]
                if users == 1:
                    del self._key_locks[key]
                else:
                    self._key_locks[key] = (current_lock, users - 1)

    def execute(self, call: ToolCall, tool: Tool) -> ToolResult:
        identity = json.dumps(
            [call.run_id, call.name, call.arguments, call.requires_approval],
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._serialize_key(call.idempotency_key):
            cached = self.store.result_for(call.idempotency_key)
            if cached:
                output, attempts, original_identity = cached
                if original_identity != identity:
                    raise IdempotencyConflict(call.idempotency_key)
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
                    self.store.save_result(call.idempotency_key, output, attempt, identity)
                    return ToolResult(call.idempotency_key, output, attempt)

            raise AssertionError("retry loop exited unexpectedly")
