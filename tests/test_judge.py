from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import anthropic
import pytest

from matchdebate.judge import judge_configuration, run_judge, validate_prediction


@pytest.mark.parametrize("probabilities,scoreline,outcome,tied", [
    ({"home": .46, "draw": .10, "away": .44}, {"home": 2, "away": 1}, "home", []),
    ({"home": .32, "draw": .36, "away": .32}, {"home": 1, "away": 1}, "draw", []),
    ({"home": .45, "draw": .10, "away": .45}, {"home": 1, "away": 2}, "away", ["home", "away"]),
    ({"home": .4, "draw": .4, "away": .2}, {"home": 0, "away": 0}, "draw", ["home", "draw"]),
])
def test_code_selects_maximum_probability_with_scoreline_breaking_exact_ties(
    packet, prediction, probabilities, scoreline, outcome, tied,
):
    prediction.update(probabilities=probabilities, scoreline=scoreline, outcome="ignored model selection")
    result = validate_prediction(prediction, packet)
    assert result["outcome"] == outcome
    assert result["tied_outcomes"] == tied


@pytest.mark.parametrize("probabilities", [
    {"home": 60, "draw": 25, "away": 15},
    {"home": .6, "draw": .2, "away": .1},
    {"home": -.1, "draw": .6, "away": .5},
    {"home": True, "draw": 0, "away": 0},
    {"home": float("nan"), "draw": .25, "away": .15},
    {"home": float("inf"), "draw": .25, "away": .15},
    {"home": 10 ** 1000, "draw": .25, "away": .15},
    {"home": "0.6", "draw": .25, "away": .15},
    {"home": .6, "draw": .4},
])
def test_rejects_invalid_probabilities_without_normalizing(packet, prediction, probabilities):
    prediction["probabilities"] = probabilities
    with pytest.raises(ValueError):
        validate_prediction(prediction, packet)


@pytest.mark.parametrize("scoreline", [
    {"home": 1, "away": 1}, {"home": 0, "away": 2},
    {"home": -1, "away": 0}, {"home": 2.0, "away": 1},
    {"home": True, "away": 0},
])
def test_rejects_incompatible_or_invalid_scoreline(packet, prediction, scoreline):
    prediction["scoreline"] = scoreline
    with pytest.raises(ValueError):
        validate_prediction(prediction, packet)


def test_tied_winners_do_not_permit_lower_probability_draw(packet, prediction):
    prediction.update(probabilities={"home": .45, "draw": .1, "away": .45},
                      scoreline={"home": 1, "away": 1})
    with pytest.raises(ValueError, match="highest-probability"):
        validate_prediction(prediction, packet)


@pytest.mark.parametrize("paths", [[], ["home.injuries"], ["fixture.home"],
                                    ["home.home_record.missing"], ["h2h.0.home_goals"], [7]])
def test_claims_need_existing_permitted_packet_fields(packet, prediction, paths):
    prediction["reasoning"][0]["packet_fields"] = paths
    with pytest.raises(ValueError):
        validate_prediction(prediction, packet)


def test_empty_h2h_can_be_cited_as_missing_evidence(packet, prediction):
    prediction["reasoning"] = [{"claim": "No H2H evidence is available.", "packet_fields": ["h2h"]}]
    assert validate_prediction(prediction, packet)["outcome"] == "home"


def test_one_repair_attempt_gets_validation_feedback_but_no_sidecar(packet, prediction, provider):
    broken = copy.deepcopy(prediction)
    broken["scoreline"] = {"home": 1, "away": 1}
    provider.replies = [broken, prediction]
    result = run_judge(packet, {"home": "Home case", "away": "Away case"}, judge_configuration())
    assert result["status"] == "valid"
    assert len(result["attempts"]) == 2
    assert "highest-probability" in provider.calls[1]["messages"][-1]["content"]
    assert json.loads(provider.calls[0]["messages"][0]["content"]) == {
        "packet": packet, "briefs": {"home": "Home case", "away": "Away case"},
    }
    assert all("tools" not in call for call in provider.calls)


def test_two_bad_responses_make_an_invalid_run(packet, provider):
    provider.replies = ["not JSON", "still not JSON"]
    result = run_judge(packet, {}, judge_configuration())
    assert result["status"] == "invalid"
    assert result["prediction"] is None
    assert len(provider.calls) == 2
    assert all("validation_error" in attempt for attempt in result["attempts"])


def test_accepts_a_single_json_fence_without_changing_the_prediction(packet, prediction, provider):
    raw = "```json\n" + json.dumps(prediction) + "\n```"
    provider.replies = [raw]
    result = run_judge(packet, {}, judge_configuration())
    assert result["status"] == "valid"
    assert result["prediction"]["probabilities"] == prediction["probabilities"]
    assert len(result["attempts"]) == 1
    assert result["attempts"][0]["raw"] == raw


def test_fenced_invalid_probabilities_still_require_repair(packet, prediction, provider):
    broken = copy.deepcopy(prediction)
    broken["probabilities"]["home"] = .9
    provider.replies = ["```json\n" + json.dumps(broken) + "\n```", prediction]
    result = run_judge(packet, {}, judge_configuration())
    assert result["status"] == "valid"
    assert len(result["attempts"]) == 2
    assert "sum to 1" in result["attempts"][0]["validation_error"]


def test_disclosed_result_recall_fails_without_repair(packet, prediction, provider):
    prediction["outside_knowledge_used"] = True
    result = run_judge(packet, {}, judge_configuration())
    assert result["status"] == "invalid"
    assert len(provider.calls) == 1


def test_disclosed_recall_in_truncated_json_is_also_terminal(packet, prediction, provider):
    prediction["outside_knowledge_used"] = True
    provider.replies = [(prediction, "max_tokens")]
    result = run_judge(packet, {}, judge_configuration())
    assert result["status"] == "invalid"
    assert len(provider.calls) == 1


def test_truncated_response_is_repaired_even_if_json_looks_valid(packet, prediction, provider):
    provider.replies = [(prediction, "max_tokens"), prediction]
    result = run_judge(packet, {}, judge_configuration())
    assert result["status"] == "valid"
    assert len(result["attempts"]) == 2


def test_transport_failure_is_distinct_from_invalid_prediction(packet, provider):
    provider.error = anthropic.APIConnectionError(request=SimpleNamespace())
    result = run_judge(packet, {}, judge_configuration())
    assert result["status"] == "error"
    assert result["error"] == "APIConnectionError"
    assert len(provider.calls) == 1
