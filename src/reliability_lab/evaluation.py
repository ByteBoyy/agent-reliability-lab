from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    completed: bool
    duplicate_side_effects: int
    attempts: int
    max_attempts: int
    approval_respected: bool


@dataclass(frozen=True, slots=True)
class Scorecard:
    passed: int
    total: int
    completion_rate: float
    violations: tuple[str, ...]


def score(results: list[ScenarioResult]) -> Scorecard:
    if not results:
        return Scorecard(0, 0, 0.0, ())

    violations: list[str] = []
    passed = 0
    for result in results:
        failures = []
        if not result.completed:
            failures.append("incomplete")
        if result.duplicate_side_effects:
            failures.append("duplicate side effect")
        if result.attempts > result.max_attempts:
            failures.append("retry budget exceeded")
        if not result.approval_respected:
            failures.append("approval bypassed")

        if failures:
            violations.append(f"{result.name}: {', '.join(failures)}")
        else:
            passed += 1

    return Scorecard(passed, len(results), passed / len(results), tuple(violations))

