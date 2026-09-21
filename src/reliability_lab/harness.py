from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Sequence

from .engine import ApprovalRequired, ReliableExecutor, RetryExhausted
from .evaluation import ScenarioResult, Scorecard, score
from .models import ToolCall
from .store import RunStore


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    max_attempts: int = 3
    transient_failures: int = 0
    requires_approval: bool = False
    replay: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Scenario:
        allowed = {
            "name",
            "max_attempts",
            "transient_failures",
            "requires_approval",
            "replay",
        }
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown scenario fields: {', '.join(sorted(unknown))}")

        scenario = cls(**data)
        if not scenario.name.strip():
            raise ValueError("scenario name must not be empty")
        if scenario.max_attempts < 1:
            raise ValueError(f"{scenario.name}: max_attempts must be positive")
        if scenario.transient_failures < 0:
            raise ValueError(f"{scenario.name}: transient_failures must not be negative")
        return scenario


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    scorecard: Scorecard
    scenarios: tuple[ScenarioResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "scorecard": asdict(self.scorecard),
            "scenarios": [asdict(result) for result in self.scenarios],
        }


def load_scenarios(path: str | Path | None = None) -> list[Scenario]:
    if path is None:
        fixture = files("reliability_lab").joinpath("fixtures/scenarios.json")
        payload = json.loads(fixture.read_text(encoding="utf-8"))
    else:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))

    if not isinstance(payload, list):
        raise ValueError("scenario fixture must contain a JSON array")

    scenarios: list[Scenario] = []
    names: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each scenario must be a JSON object")
        scenario = Scenario.from_mapping(item)
        if scenario.name in names:
            raise ValueError(f"duplicate scenario name: {scenario.name}")
        names.add(scenario.name)
        scenarios.append(scenario)
    return scenarios


def run_scenario(scenario: Scenario) -> ScenarioResult:
    store = RunStore()
    executor = ReliableExecutor(store, max_attempts=scenario.max_attempts)
    call = ToolCall(
        run_id=f"evaluation:{scenario.name}",
        name="record_effect",
        arguments={"scenario": scenario.name},
        idempotency_key=f"evaluation:{scenario.name}:record_effect",
        requires_approval=scenario.requires_approval,
    )
    invocations = 0
    side_effects = 0

    def deterministic_tool(arguments: dict[str, Any]) -> dict[str, Any]:
        nonlocal invocations, side_effects
        invocations += 1
        if invocations <= scenario.transient_failures:
            raise TimeoutError(f"deterministic failure {invocations}")
        side_effects += 1
        return {"recorded": arguments["scenario"]}

    approval_respected = True
    if scenario.requires_approval:
        try:
            executor.execute(call, deterministic_tool)
        except ApprovalRequired:
            store.approve(call.idempotency_key)
        else:
            approval_respected = False

    try:
        result = executor.execute(call, deterministic_tool)
    except RetryExhausted:
        result = None

    if result is not None and scenario.replay:
        executor.execute(call, deterministic_tool)

    return ScenarioResult(
        name=scenario.name,
        completed=result is not None,
        duplicate_side_effects=max(0, side_effects - 1),
        attempts=result.attempts if result is not None else invocations,
        max_attempts=scenario.max_attempts,
        approval_respected=approval_respected,
    )


def evaluate(scenarios: Sequence[Scenario]) -> EvaluationReport:
    results = tuple(run_scenario(scenario) for scenario in scenarios)
    return EvaluationReport(score(list(results)), results)


def render_report(report: EvaluationReport) -> str:
    return json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic reliability scenarios and emit a JSON scorecard."
    )
    parser.add_argument("--fixtures", type=Path, help="path to a scenario JSON file")
    parser.add_argument("--output", type=Path, help="write the report to this file")
    args = parser.parse_args(argv)

    report = evaluate(load_scenarios(args.fixtures))
    rendered = render_report(report)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report.scorecard.passed == report.scorecard.total else 1


if __name__ == "__main__":
    raise SystemExit(main())
