from reliability_lab.evaluation import ScenarioResult, score


def test_scorecard_surfaces_operational_failures() -> None:
    report = score(
        [
            ScenarioResult("healthy", True, 0, 1, 3, True),
            ScenarioResult("unsafe", True, 1, 4, 3, False),
        ]
    )

    assert report.completion_rate == 0.5
    assert report.violations == (
        "unsafe: duplicate side effect, retry budget exceeded, approval bypassed",
    )


def test_empty_scorecard_is_defined() -> None:
    assert score([]).completion_rate == 0.0

