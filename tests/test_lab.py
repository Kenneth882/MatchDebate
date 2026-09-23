from __future__ import annotations

import json
from types import SimpleNamespace

import anthropic
import pytest

from matchdebate.__main__ import main
from matchdebate.judge import judge_configuration
from matchdebate.lab import Lab


@pytest.fixture
def lab(tmp_path):
    return Lab(tmp_path / "runs", tmp_path / "sidecars")


def test_all_five_fixtures_run_save_then_reveal_and_score_through_cli(lab, provider, capsys):
    assert main(["run", "--all"], lab=lab) == 0
    output = capsys.readouterr().out
    paths = sorted(lab.runs_dir.glob("*/run.json"))
    assert len(paths) == 5
    records = [json.loads(path.read_text()) for path in paths]
    assert {record["fixture_id"] for record in records} == {
        "luton-burnley", "luton-tottenham", "crystal-palace-forest",
        "arsenal-man-city", "man-city-brighton",
    }
    assert all(record["status"] == "valid" for record in records)
    assert not list(lab.runs_dir.glob("*/evaluation.json"))
    assert "b365_home" not in output
    assert "full_time_home_goals" not in output
    assert main(["evaluate", *[record["run_id"] for record in records]], lab=lab) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["groups"][0]["scored_runs"] == 5
    assert summary["same_inputs_and_complete_coverage"] is True
    assert len(list(lab.runs_dir.glob("*/evaluation.json"))) == 5
    judge_calls = [call for call in provider.calls if "tools" not in call]
    assert len(judge_calls) == 5
    for call in judge_calls:
        inputs = json.loads(call["messages"][0]["content"])
        assert set(inputs) == {"packet", "briefs"}
        assert set(inputs["briefs"]) == {"home", "away"}
        assert "b365_home" not in call["messages"][0]["content"]
        assert "full_time_home_goals" not in call["messages"][0]["content"]


def test_rejudge_reuses_frozen_inputs_even_after_reveal_and_preserves_previous_run(lab, provider):
    first = lab.run_fixture("arsenal-man-city", judge_configuration())
    lab.reveal(first["run_id"])
    original = (lab.runs_dir / first["run_id"] / "run.json").read_bytes()
    first_judge_inputs = provider.calls[-1]["messages"]
    provider.calls.clear()
    configuration = judge_configuration(prompt="New judge prompt for controlled comparison.")
    second = lab.rejudge(first["run_id"], configuration)
    assert second["run_id"] != first["run_id"]
    assert second["source_run_id"] == first["run_id"]
    assert second["input_id"] == first["input_id"]
    assert second["judge_configuration"]["version"] != first["judge_configuration"]["version"]
    assert len(provider.calls) == 1
    assert provider.calls[0]["messages"] == first_judge_inputs
    assert (lab.runs_dir / first["run_id"] / "run.json").read_bytes() == original
    summary = lab.evaluate([first["run_id"], second["run_id"]])
    assert len(summary["groups"]) == 2
    assert summary["same_inputs_and_complete_coverage"] is True


def test_invalid_judge_is_saved_counted_and_cannot_reveal(lab, provider):
    provider.replies = ["broken", "still broken"]
    record = lab.run_fixture("luton-burnley", judge_configuration())
    assert lab.read_run(record["run_id"])["status"] == "invalid"
    # Absence of the Sidecar must not affect the validation gate.
    (lab.sidecars_dir / f"{record['run_id']}.json").unlink()
    with pytest.raises(ValueError, match="saved, valid"):
        lab.reveal(record["run_id"])
    summary = lab.evaluate([record["run_id"]])
    assert summary["groups"][0]["invalid_runs"] == 1
    assert summary["groups"][0]["mean_brier_loss"] is None
    assert not list(lab.runs_dir.glob("*/evaluation.json"))


def test_duplicate_fixture_version_is_rejected_before_revealing(lab, provider):
    first = lab.run_fixture("luton-burnley", judge_configuration())
    second = lab.rejudge(first["run_id"], judge_configuration())
    with pytest.raises(ValueError, match="one run per fixture"):
        lab.evaluate([first["run_id"], second["run_id"]])
    assert not list(lab.runs_dir.glob("*/evaluation.json"))


def test_changed_inputs_or_forged_selected_outcome_prevent_reveal(lab, provider):
    record = lab.run_fixture("luton-burnley", judge_configuration())
    path = lab.runs_dir / record["run_id"] / "run.json"
    record["prediction"]["outcome"] = "draw"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="inconsistent"):
        lab.reveal(record["run_id"])
    record["packet"]["fixture"]["home"] = "Different club"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="changed"):
        lab.reveal(record["run_id"])


def test_new_runs_do_not_overwrite_existing_fixture_briefs(lab, provider):
    first = lab.run_fixture("luton-burnley", judge_configuration())
    second = lab.run_fixture("luton-burnley", judge_configuration())
    assert first["run_id"] != second["run_id"]
    assert lab.read_run(first["run_id"])["briefs"] == first["briefs"]


def test_cli_reports_missing_runs_without_exposing_legacy_sidecar(lab, capsys):
    lab.sidecars_dir.mkdir(parents=True)
    (lab.sidecars_dir / "luton-burnley.json").write_text('{"secret": "result"}')
    assert main(["reveal", "luton-burnley"], lab=lab) == 1
    output = capsys.readouterr()
    assert "Use a run ID" in output.err
    assert "secret" not in output.out


def test_cli_runs_a_different_judge_prompt_without_rerunning_advocates(lab, provider, tmp_path, capsys):
    first = lab.run_fixture("luton-burnley", judge_configuration())
    prompt = tmp_path / "judge-v2.md"
    prompt.write_text("Another judge prompt.")
    provider.calls.clear()
    assert main(["judge", first["run_id"], "--prompt-file", str(prompt), "--model", "test-model"], lab=lab) == 0
    assert len(provider.calls) == 1
    assert provider.calls[0]["model"] == "test-model"
    assert provider.calls[0]["system"] == prompt.read_text()
    assert "valid" in capsys.readouterr().out


def test_failed_advocates_are_saved_and_counted_without_calling_the_judge(lab, provider, capsys):
    provider.error = anthropic.APIConnectionError(request=SimpleNamespace())
    assert main(["run", "--all"], lab=lab) == 1
    records = [json.loads(path.read_text()) for path in lab.runs_dir.glob("*/run.json")]
    assert len(records) == 5
    assert all(record["status"] == "error" and record["failure_stage"] == "advocates" for record in records)
    assert len(provider.calls) == 5
    with pytest.raises(ValueError, match="both completed Advocate Briefs"):
        lab.rejudge(records[0]["run_id"], judge_configuration())
    assert main(["evaluate", *[record["run_id"] for record in records]], lab=lab) == 1
    summary = lab.evaluate([record["run_id"] for record in records])
    assert summary["groups"][0]["error_runs"] == 5
    assert summary["groups"][0]["mean_brier_loss"] is None


def test_versions_using_different_fixture_inputs_are_not_reported_as_comparable(lab, provider):
    first = lab.run_fixture("luton-burnley", judge_configuration())
    second = lab.run_fixture("man-city-brighton", judge_configuration(prompt="Different prompt."))
    summary = lab.evaluate([first["run_id"], second["run_id"]])
    assert summary["same_inputs_and_complete_coverage"] is False
    assert len(summary["groups"]) == 2
