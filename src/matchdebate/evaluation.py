from __future__ import annotations

from collections import defaultdict
from statistics import mean

from matchdebate.judge import OUTCOMES, scoreline_outcome


def evaluate_prediction(prediction: dict, sidecar: dict) -> dict:
    home = sidecar["full_time_home_goals"]
    away = sidecar["full_time_away_goals"]
    actual = scoreline_outcome(home, away)
    return {
        "brier_loss": sum(
            (prediction["probabilities"][outcome] - int(outcome == actual)) ** 2
            for outcome in OUTCOMES
        ),
        "outcome_correct": prediction["outcome"] == actual,
        "exact_score_correct": prediction["scoreline"] == {"home": home, "away": away},
        "predicted_outcome": prediction["outcome"],
        "actual_outcome": actual,
    }


def summarize_runs(records: list[dict]) -> dict:
    """Keep versions separate and expose failures and unequal comparison inputs."""
    versions: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for record in records:
        version = record["judge_configuration"]["version"]
        key = (version, record["fixture_id"])
        if key in seen:
            raise ValueError("Select only one run per fixture per judge version for evaluation.")
        seen.add(key)
        versions[version].append(record)

    groups = []
    attempted_inputs = []
    evaluated_inputs = []
    for version, runs in versions.items():
        evaluated = [run for run in runs if run.get("evaluation") is not None]
        scores = [run["evaluation"] for run in evaluated]
        draws = [score for score in scores if score["predicted_outcome"] == "draw"]
        attempted_inputs.append({run["input_id"] for run in runs})
        evaluated_inputs.append({run["input_id"] for run in evaluated})
        groups.append({
            "judge_version": version,
            "model": runs[0]["judge_configuration"]["model"],
            "run_ids": [run["run_id"] for run in runs],
            "total_runs": len(runs),
            "scored_runs": len(scores),
            "invalid_runs": sum(run["status"] == "invalid" for run in runs),
            "error_runs": sum(run["status"] == "error" for run in runs),
            "pending_runs": sum(run["status"] == "pending" for run in runs),
            "mean_brier_loss": mean(score["brier_loss"] for score in scores) if scores else None,
            "outcome_accuracy": mean(score["outcome_correct"] for score in scores) if scores else None,
            "exact_score_accuracy": mean(score["exact_score_correct"] for score in scores) if scores else None,
            "predicted_draws": len(draws),
            "draw_frequency": len(draws) / len(scores) if scores else None,
            # Draw accuracy means precision: correct draws / predicted draws.
            "draw_accuracy": mean(score["outcome_correct"] for score in draws) if draws else None,
            "actual_draws": sum(score["actual_outcome"] == "draw" for score in scores),
        })
    comparable = bool(groups) and all(
        inputs == attempted_inputs[0] for inputs in attempted_inputs + evaluated_inputs
    )
    return {
        "scoring_rule": "three-outcome Brier loss, unnormalized (0..2), lower is better",
        "same_inputs_and_complete_coverage": comparable,
        "comparison_note": (
            "All versions cover the same saved inputs with valid scored predictions."
            if comparable else
            "Unequal inputs or failed/pending runs: these means are not a controlled version comparison."
        ),
        "groups": groups,
    }
