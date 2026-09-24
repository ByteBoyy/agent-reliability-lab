from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .engine import ApprovalRequired, IdempotencyConflict, ReliableExecutor
from .models import ToolCall
from .store import RunStore


class ExecutionRequest(BaseModel):
    run_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False


def create_app(store: RunStore | None = None) -> FastAPI:
    run_store = store or RunStore(os.getenv("RELIABILITY_DB", "runs.db"))
    executor = ReliableExecutor(run_store)
    app = FastAPI(title="Agent Reliability Lab", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/runs/execute")
    def execute(request: ExecutionRequest) -> dict[str, Any]:
        call = ToolCall(
            run_id=request.run_id,
            name="echo",
            arguments=request.arguments,
            idempotency_key=request.idempotency_key,
            requires_approval=request.requires_approval,
        )
        try:
            result = executor.execute(call, lambda arguments: {"echo": arguments})
        except ApprovalRequired as exc:
            raise HTTPException(status_code=409, detail={"approval_required": str(exc)}) from exc
        except IdempotencyConflict as exc:
            raise HTTPException(
                status_code=409, detail={"idempotency_conflict": str(exc)}
            ) from exc
        return {
            "output": result.output,
            "attempts": result.attempts,
            "replayed": result.replayed,
        }

    @app.post("/approvals/{idempotency_key}", status_code=204)
    def approve(idempotency_key: str) -> None:
        run_store.approve(idempotency_key)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("reliability_lab.api:app", host="127.0.0.1", port=8000)
