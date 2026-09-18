import pytest

from reliability_lab.engine import ApprovalRequired, ReliableExecutor, RetryExhausted
from reliability_lab.models import ToolCall
from reliability_lab.store import RunStore


def call(*, approval: bool = False) -> ToolCall:
    return ToolCall("run-1", "charge", {"amount": 25}, "run-1:charge:25", approval)


def test_replays_saved_result_without_repeating_side_effect() -> None:
    invocations = 0

    def tool(arguments: dict) -> dict:
        nonlocal invocations
        invocations += 1
        return {"charged": arguments["amount"]}

    executor = ReliableExecutor(RunStore())
    first = executor.execute(call(), tool)
    second = executor.execute(call(), tool)

    assert first.replayed is False
    assert second.replayed is True
    assert invocations == 1


def test_blocks_sensitive_call_until_approved() -> None:
    store = RunStore()
    executor = ReliableExecutor(store)

    with pytest.raises(ApprovalRequired):
        executor.execute(call(approval=True), lambda args: args)

    store.approve(call(approval=True).idempotency_key)
    assert executor.execute(call(approval=True), lambda args: args).output == {"amount": 25}


def test_retries_transient_failure_with_a_hard_limit() -> None:
    attempts = 0

    def flaky(_: dict) -> dict:
        nonlocal attempts
        attempts += 1
        raise TimeoutError("fixture timeout")

    with pytest.raises(RetryExhausted):
        ReliableExecutor(RunStore(), max_attempts=2).execute(call(), flaky)

    assert attempts == 2
