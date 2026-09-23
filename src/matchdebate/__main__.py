from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from matchdebate.fixtures import get_fixture, load_fixtures
from matchdebate.judge import judge_configuration
from matchdebate.lab import Lab
from matchdebate.matches import load_all_matches
from matchdebate.packet import build_packet, packet_json
from matchdebate.paths import format_date


def _load():
    return load_all_matches()


def cmd_packet(fixture_id: str) -> int:
    fixture = get_fixture(fixture_id)
    packet = build_packet(_load(), fixture)
    sys.stdout.write(packet_json(packet) + "\n")
    return 0


def _print_run(record: dict) -> None:
    print(f"{record['fixture_id']}: {record['run_id']} ({record['status']})", flush=True)
    if record["status"] == "valid":
        print(json.dumps(record["prediction"], indent=2), flush=True)
        print(f"Reveal and score: python -m matchdebate reveal {record['run_id']}", flush=True)
    else:
        error = record.get("error") or next(
            (attempt["validation_error"] for attempt in reversed(record["attempts"])
             if "validation_error" in attempt),
            "Run did not complete.",
        )
        print(f"No valid prediction: {error}", file=sys.stderr, flush=True)


def cmd_list() -> int:
    for fixture in load_fixtures():
        print(
            f"{fixture.id}: {fixture.home} vs {fixture.away} "
            f"{format_date(fixture.date)} ({fixture.type})"
        )
    return 0


def main(argv: list[str] | None = None, *, lab: Lab | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchdebate")
    sub = parser.add_subparsers(dest="command", required=True)

    packet = sub.add_parser("packet", help="Print the Match Packet JSON")
    packet.add_argument("fixture_id")

    run = sub.add_parser("run", help="Run advocates and judge; save a new run")
    run.add_argument("fixture_id", nargs="?")
    run.add_argument("--all", action="store_true", help="Run all five Lab Fixtures")

    judge = sub.add_parser("judge", help="Rerun only the judge on a saved run's exact inputs")
    judge.add_argument("source_run_id")
    for command in (run, judge):
        command.add_argument("--model", help="Judge model (advocates use ANTHROPIC_MODEL)")
        command.add_argument("--prompt-file", type=Path, help="Alternative judge prompt to evaluate")

    reveal = sub.add_parser("reveal", help="Reveal and score a saved valid Judge Prediction")
    reveal.add_argument("run_id")

    evaluate = sub.add_parser("evaluate", help="Reveal selected valid runs and summarize by judge version")
    evaluate.add_argument("run_ids", nargs="+")

    sub.add_parser("list", help="List lab fixtures")

    args = parser.parse_args(argv)
    lab = lab or Lab()
    try:
        if args.command == "packet":
            return cmd_packet(args.fixture_id)
        if args.command == "list":
            return cmd_list()
        if args.command in {"run", "judge"}:
            if args.command == "run" and bool(args.fixture_id) == args.all:
                parser.error("run requires either a fixture_id or --all")
            prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else None
            configuration = judge_configuration(model=args.model, prompt=prompt)
            if args.command == "judge":
                record = lab.rejudge(args.source_run_id, configuration)
                _print_run(record)
                return int(record["status"] != "valid")
            fixture_ids = [fixture.id for fixture in load_fixtures()] if args.all else [args.fixture_id]
            records = []
            for fixture_id in fixture_ids:
                print(f"Running {fixture_id}…", flush=True)
                record = lab.run_fixture(fixture_id, configuration)
                records.append(record)
                _print_run(record)
            if args.all:
                print("Evaluate this batch: python -m matchdebate evaluate " +
                      " ".join(record["run_id"] for record in records), flush=True)
            return int(any(record["status"] != "valid" for record in records))
        if args.command == "reveal":
            print(json.dumps(lab.reveal(args.run_id), indent=2))
            return 0
        if args.command == "evaluate":
            summary = lab.evaluate(args.run_ids)
            print(json.dumps(summary, indent=2))
            return int(any(group["scored_runs"] < group["total_runs"] for group in summary["groups"]))
    except (ValueError, KeyError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
