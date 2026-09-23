from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import anthropic

from matchdebate.agents import model_name, read_prompt, run_advocate
from matchdebate.evaluation import evaluate_prediction, summarize_runs
from matchdebate.fixtures import get_fixture
from matchdebate.judge import fingerprint, run_judge, validate_prediction
from matchdebate.matches import load_all_matches
from matchdebate.packet import build_packet, build_sidecar
from matchdebate.paths import DATA_DIR, SIDECAR_DIR


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class Lab:
    """Own saved inputs, judge runs, and the prediction-before-reveal boundary."""

    def __init__(self, runs_dir: Path = DATA_DIR / "runs", sidecars_dir: Path = SIDECAR_DIR):
        self.runs_dir = runs_dir
        self.sidecars_dir = sidecars_dir

    def _run_path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
            raise ValueError("Invalid run ID.")
        return self.runs_dir / run_id / "run.json"

    def read_run(self, run_id: str) -> dict:
        path = self._run_path(run_id)
        if not path.exists():
            raise ValueError(f"No saved run {run_id!r}. Use a run ID, not a fixture ID.")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["run_id"] != run_id:
            raise ValueError("Saved run ID does not match its directory.")
        if record["input_id"] != fingerprint({"packet": record["packet"], "briefs": record["briefs"]}):
            raise ValueError("Saved packet or briefs changed after this run was recorded.")
        return record

    def _save(self, record: dict) -> None:
        _write_json(self._run_path(record["run_id"]), record)

    def _create(self, packet: dict, briefs: dict, advocates: dict, configuration: dict,
                sidecar: dict, source_run_id: str | None = None) -> dict:
        now = datetime.now(timezone.utc)
        run_id = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:12]
        record = {
            "schema_version": 1,
            "run_id": run_id,
            "created_at": now.isoformat(),
            "fixture_id": packet["fixture"]["id"],
            "source_run_id": source_run_id,
            "packet": packet,
            "briefs": briefs,
            "input_id": fingerprint({"packet": packet, "briefs": briefs}),
            "advocate_configuration": advocates,
            "judge_configuration": configuration,
            "status": "pending",
            "prediction": None,
            "attempts": [],
        }
        self._run_path(run_id).parent.mkdir(parents=True, exist_ok=False)
        # This file is never passed to either the advocates or the judge.
        _write_json(self.sidecars_dir / f"{run_id}.json", sidecar)
        self._save(record)
        return record

    def _judge(self, record: dict) -> dict:
        result = run_judge(record["packet"], record["briefs"], record["judge_configuration"])
        record.update(result)
        self._save(record)
        return record

    def run_fixture(self, fixture_id: str, configuration: dict) -> dict:
        fixture = get_fixture(fixture_id)
        matches = load_all_matches()
        packet = build_packet(matches, fixture)
        advocates = {
            "model": model_name(),
            "prompts": {name: read_prompt(f"{name}.md") for name in ("shared", "home", "away")},
        }
        record = self._create(packet, {}, advocates, configuration, build_sidecar(matches, fixture))
        try:
            for role in ("home", "away"):
                record["briefs"][role] = run_advocate(role, packet)
                record["input_id"] = fingerprint({"packet": packet, "briefs": record["briefs"]})
                self._save(record)
        except (anthropic.APIError, RuntimeError) as error:
            record.update(status="error", error=type(error).__name__, failure_stage="advocates")
            self._save(record)
            return record
        return self._judge(record)

    def rejudge(self, source_run_id: str, configuration: dict) -> dict:
        source = self.read_run(source_run_id)
        if any(not source["briefs"].get(role, "").strip() for role in ("home", "away")):
            raise ValueError("Source run needs both completed Advocate Briefs.")
        # Copy only the original inputs/configuration, never its prediction,
        # response history, evaluation, or revealed result into the new judge.
        sidecar = json.loads((self.sidecars_dir / f"{source_run_id}.json").read_text(encoding="utf-8"))
        record = self._create(
            source["packet"], source["briefs"], source["advocate_configuration"],
            configuration, sidecar, source_run_id,
        )
        return self._judge(record)

    def reveal(self, run_id: str) -> dict:
        record = self.read_run(run_id)
        if record["status"] != "valid":
            raise ValueError("Reveal requires a saved, valid Judge Prediction.")
        checked = validate_prediction(record["prediction"], record["packet"])
        if checked != record["prediction"]:
            raise ValueError("Saved Judge Prediction is inconsistent; reveal refused.")
        # Read the Sidecar only after checking the saved prediction.
        sidecar = json.loads((self.sidecars_dir / f"{run_id}.json").read_text(encoding="utf-8"))
        if sidecar["fixture_id"] != record["fixture_id"]:
            raise ValueError("Sidecar does not belong to this run's Lab Fixture.")
        evaluation = {
            "run_id": run_id,
            "judge_version": record["judge_configuration"]["version"],
            "input_id": record["input_id"],
            "revealed_at": datetime.now(timezone.utc).isoformat(),
            "sidecar": sidecar,
            **evaluate_prediction(checked, sidecar),
        }
        _write_json(self._run_path(run_id).parent / "evaluation.json", evaluation)
        return evaluation

    def evaluate(self, run_ids: list[str]) -> dict:
        records = [self.read_run(run_id) for run_id in run_ids]
        summarize_runs(records)  # Reject duplicate fixture/version entries before any reveal.
        for record in records:
            if record["status"] == "valid":
                record["evaluation"] = self.reveal(record["run_id"])
        return summarize_runs(records)
