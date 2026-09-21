import json

import pytest

from reliability_lab.harness import (
    Scenario,
    evaluate,
    load_scenarios,
    main,
    run_scenario,
)


def test_bundled_scenarios_cover_core_reliability_invariants() -> None:
    report = evaluate(load_scenarios())

    assert report.scorecard.passed == report.scorecard.total == 3
    assert report.scorecard.completion_rate == 1.0
    assert report.scorecard.violations == ()
    assert [result.attempts for result in report.scenarios] == [1, 3, 1]
    assert all(result.duplicate_side_effects == 0 for result in report.scenarios)
    assert all(result.approval_respected for result in report.scenarios)


def test_exhausted_retry_budget_is_reported_as_a_failure() -> None:
    result = run_scenario(
        Scenario("persistent_timeout", max_attempts=2, transient_failures=2)
    )

    assert result.completed is False
    assert result.attempts == 2
    assert result.max_attempts == 2


def test_cli_writes_a_machine_readable_report(tmp_path) -> None:
    output = tmp_path / "scorecard.json"

    assert main(["--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["scorecard"]["passed"] == 3
    assert payload["scorecard"]["total"] == 3
    assert {scenario["name"] for scenario in payload["scenarios"]} == {
        "guarded_side_effect",
        "idempotent_replay",
        "transient_recovery",
    }


def test_fixture_validation_rejects_duplicate_names(tmp_path) -> None:
    fixture = tmp_path / "duplicates.json"
    fixture.write_text('[{"name": "same"}, {"name": "same"}]', encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate scenario name: same"):
        load_scenarios(fixture)
