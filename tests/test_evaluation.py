from __future__ import annotations

import pytest

from matchdebate.evaluation import evaluate_prediction, summarize_runs
from matchdebate.judge import validate_prediction


def test_brier_loss_and_both_accuracy_measures_have_independent_meanings(packet, prediction):
    prediction["probabilities"] = {"home": .5, "draw": .3, "away": .2}
    checked = validate_prediction(prediction, packet)
    score = evaluate_prediction(checked, {"full_time_home_goals": 3, "full_time_away_goals": 1})
    assert score["brier_loss"] == pytest.approx(.38)
    assert score["outcome_correct"] is True
    assert score["exact_score_correct"] is False


@pytest.mark.parametrize("probabilities,actual_goals,expected", [
    ({"home": 1, "draw": 0, "away": 0}, (2, 1), 0),
    ({"home": 1, "draw": 0, "away": 0}, (0, 1), 2),
    ({"home": 0, "draw": 1, "away": 0}, (1, 1), 0),
    ({"home": 0, "draw": 1, "away": 0}, (1, 0), 2),
])
def test_brier_endpoints_treat_draws_and_wins_equally(prediction, probabilities, actual_goals, expected):
    prediction.update(probabilities=probabilities, outcome="home")
    score = evaluate_prediction(prediction, {
        "full_time_home_goals": actual_goals[0], "full_time_away_goals": actual_goals[1],
    })
    assert score["brier_loss"] == expected


def test_summary_excludes_failures_and_keeps_versions_and_draw_denominators_visible():
    def record(fixture, status, version="v1", evaluation=None):
        return {"run_id": fixture + version, "fixture_id": fixture, "input_id": fixture,
                "status": status, "judge_configuration": {"version": version, "model": "test"},
                "evaluation": evaluation}

    good_draw = {"brier_loss": .2, "outcome_correct": True, "exact_score_correct": True,
                 "predicted_outcome": "draw", "actual_outcome": "draw"}
    bad_draw = {"brier_loss": 1.2, "outcome_correct": False, "exact_score_correct": False,
                "predicted_outcome": "draw", "actual_outcome": "away"}
    result = summarize_runs([
        record("a", "valid", evaluation=good_draw),
        record("b", "valid", evaluation=bad_draw),
        record("c", "invalid"), record("d", "error"),
        record("a", "invalid", version="v2"),
    ])
    first, second = result["groups"]
    assert first["mean_brier_loss"] == pytest.approx(.7)
    assert first["outcome_accuracy"] == .5
    assert first["exact_score_accuracy"] == .5
    assert first["draw_frequency"] == 1
    assert first["draw_accuracy"] == .5
    assert first["invalid_runs"] == first["error_runs"] == 1
    assert first["scored_runs"] == 2
    assert second["mean_brier_loss"] is None
    assert second["draw_accuracy"] is None
    assert result["same_inputs_and_complete_coverage"] is False
