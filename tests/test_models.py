from reliability_lab.models import RunStatus, ToolCall


def test_tool_call_preserves_reliability_metadata() -> None:
    call = ToolCall(
        run_id="run-1",
        name="lookup_order",
        arguments={"order_id": "A-42"},
        idempotency_key="run-1:lookup:A-42",
        requires_approval=True,
    )

    assert call.requires_approval is True
    assert call.idempotency_key.startswith(call.run_id)
    assert RunStatus.WAITING_APPROVAL.value == "waiting_approval"
