from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock

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


def test_concurrent_replays_execute_side_effect_once() -> None:
    executor = ReliableExecutor(RunStore())
    first_invocation = Event()
    release_tool = Event()
    duplicate_invocation = Event()
    invocation_guard = Lock()
    invocations = 0

    def tool(arguments: dict) -> dict:
        nonlocal invocations
        with invocation_guard:
            invocations += 1
            if invocations == 1:
                first_invocation.set()
            else:
                duplicate_invocation.set()
        if not release_tool.wait(timeout=2):
            raise TimeoutError("test did not release the tool")
        return {"charged": arguments["amount"]}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(executor.execute, call(), tool)
        assert first_invocation.wait(timeout=1)
        second = pool.submit(executor.execute, call(), tool)

        assert not duplicate_invocation.wait(timeout=0.05)
        release_tool.set()
        first_result = first.result(timeout=1)
        second_result = second.result(timeout=1)

    assert invocations == 1
    assert first_result.replayed is False
    assert second_result.replayed is True
    assert first_result.output == second_result.output


def test_different_idempotency_keys_can_execute_concurrently() -> None:
    executor = ReliableExecutor(RunStore())
    both_tools_started = Barrier(2)

    def tool(arguments: dict) -> dict:
        both_tools_started.wait(timeout=1)
        return {"charged": arguments["amount"]}

    other_call = ToolCall("run-2", "charge", {"amount": 30}, "run-2:charge:30")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(executor.execute, call(), tool)
        second = pool.submit(executor.execute, other_call, tool)

        assert first.result(timeout=2).output == {"charged": 25}
        assert second.result(timeout=2).output == {"charged": 30}


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
