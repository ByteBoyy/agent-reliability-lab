# Agent Reliability Lab

A small offline-first laboratory for the parts of tool-using agents that tend to
fail outside a demo. It makes retry budgets, approval gates, idempotency, and
replay behavior observable without requiring an LLM key.

## What works today

- SQLite-backed tool results survive process restarts.
- An idempotency key prevents repeated side effects during replay.
- Sensitive calls stop at an explicit approval gate.
- Transient failures retry within a hard attempt budget.
- Deterministic scorecards report completion and safety violations.

```python
from reliability_lab.engine import ReliableExecutor
from reliability_lab.models import ToolCall
from reliability_lab.store import RunStore

store = RunStore("runs.db")
executor = ReliableExecutor(store, max_attempts=3)
call = ToolCall(
    run_id="checkout-42",
    name="reserve_inventory",
    arguments={"sku": "A-12"},
    idempotency_key="checkout-42:reserve:A-12",
)

result = executor.execute(call, lambda args: {"reserved": args["sku"]})
```

Run the offline suite with:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

Install the API extra and start the local service with:

```bash
.venv/bin/pip install -e '.[api]'
reliability-lab
```

The API exposes health, execution, and approval endpoints. Repeating an
execution with the same idempotency key returns the stored result with
`replayed` set to `true`.
Reusing a key with a different run, tool, arguments, or approval requirement
returns HTTP 409. Existing SQLite rows created before call identity was stored
also return a conflict because their original request cannot be verified.

## Next slices

- Persist run state transitions and resumable checkpoints.
- Expose runs and approvals through FastAPI.
- Add deterministic failure fixtures and JSON evaluation reports.
- Add PostgreSQL and a small trace viewer after the local contract is stable.
