from __future__ import annotations

import argparse
import json
import sys

from matchdebate.agents import run_advocate, write_brief
from matchdebate.fixtures import get_fixture, load_fixtures
from matchdebate.matches import load_all_matches
from matchdebate.packet import build_packet, build_sidecar, packet_json
from matchdebate.paths import BRIEFS_DIR, SIDECAR_DIR, format_date


def _load():
    return load_all_matches()


def cmd_packet(fixture_id: str) -> int:
    fixture = get_fixture(fixture_id)
    packet = build_packet(_load(), fixture)
    sys.stdout.write(packet_json(packet) + "\n")
    return 0


def cmd_run(fixture_id: str) -> int:
    fixture = get_fixture(fixture_id)
    matches = _load()
    packet = build_packet(matches, fixture)
    sidecar = build_sidecar(matches, fixture)

    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
    sidecar_path = SIDECAR_DIR / f"{fixture.id}.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")

    home_brief = run_advocate("home", packet)
    away_brief = run_advocate("away", packet)

    fixture_dir = BRIEFS_DIR / fixture.id
    write_brief(fixture_dir / "home.md", home_brief)
    write_brief(fixture_dir / "away.md", away_brief)

    print(f"Wrote {fixture_dir / 'home.md'}")
    print(f"Wrote {fixture_dir / 'away.md'}")
    print(
        f"Pick a winner and score for {fixture.home} vs {fixture.away} "
        f"on {format_date(fixture.date)}, then run:"
    )
    print(f"  python -m matchdebate reveal {fixture.id}")
    return 0


def cmd_reveal(fixture_id: str) -> int:
    path = SIDECAR_DIR / f"{fixture_id}.json"
    if not path.exists():
        print(
            f"No sidecar at {path}. Run `python -m matchdebate run {fixture_id}` first.",
            file=sys.stderr,
        )
        return 1
    sidecar = json.loads(path.read_text(encoding="utf-8"))
    print(
        f"{sidecar['home']} {sidecar['full_time_home_goals']}-"
        f"{sidecar['full_time_away_goals']} {sidecar['away']} "
        f"({sidecar['full_time_result']})"
    )
    print(
        "B365 "
        f"H {sidecar['b365_home']} "
        f"D {sidecar['b365_draw']} "
        f"A {sidecar['b365_away']}"
    )
    return 0


def cmd_list() -> int:
    for fixture in load_fixtures():
        print(
            f"{fixture.id}: {fixture.home} vs {fixture.away} "
            f"{format_date(fixture.date)} ({fixture.type})"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matchdebate")
    sub = parser.add_subparsers(dest="command", required=True)

    packet = sub.add_parser("packet", help="Print the Match Packet JSON")
    packet.add_argument("fixture_id")

    run = sub.add_parser("run", help="Run home and away advocates")
    run.add_argument("fixture_id")

    reveal = sub.add_parser("reveal", help="Show hidden score and odds")
    reveal.add_argument("fixture_id")

    sub.add_parser("list", help="List lab fixtures")

    args = parser.parse_args(argv)
    if args.command == "packet":
        return cmd_packet(args.fixture_id)
    if args.command == "run":
        return cmd_run(args.fixture_id)
    if args.command == "reveal":
        return cmd_reveal(args.fixture_id)
    if args.command == "list":
        return cmd_list()
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
