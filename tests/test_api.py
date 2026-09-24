from fastapi.testclient import TestClient

from reliability_lab.api import create_app
from reliability_lab.store import RunStore


def test_execute_endpoint_exposes_replay_state() -> None:
    client = TestClient(create_app(RunStore()))
    payload = {
        "run_id": "run-7",
        "idempotency_key": "run-7:echo",
        "arguments": {"message": "hello"},
    }

    first = client.post("/runs/execute", json=payload)
    second = client.post("/runs/execute", json=payload)

    assert first.json()["replayed"] is False
    assert second.json()["replayed"] is True


def test_execute_endpoint_rejects_changed_payload_for_saved_key() -> None:
    client = TestClient(create_app(RunStore()))
    payload = {
        "run_id": "run-7",
        "idempotency_key": "run-7:echo",
        "arguments": {"message": "hello"},
    }

    assert client.post("/runs/execute", json=payload).status_code == 200
    payload["arguments"] = {"message": "changed"}
    response = client.post("/runs/execute", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == {"idempotency_conflict": "run-7:echo"}


def test_approval_endpoint_unblocks_guarded_execution() -> None:
    client = TestClient(create_app(RunStore()))
    payload = {
        "run_id": "run-8",
        "idempotency_key": "run-8:echo",
        "arguments": {},
        "requires_approval": True,
    }

    assert client.post("/runs/execute", json=payload).status_code == 409
    assert client.post("/approvals/run-8:echo").status_code == 204
    assert client.post("/runs/execute", json=payload).status_code == 200
