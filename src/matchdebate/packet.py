from __future__ import annotations

import json
from datetime import date
from typing import Any

from matchdebate.fixtures import LabFixture
from matchdebate.matches import (
    Match,
    allowed_rows,
    current_season_rows,
    find_target,
)
from matchdebate.paths import CURRENT_SEASON, format_date

ODDS_AND_RESULT_KEYS = {
    "fthg",
    "ftag",
    "ftr",
    "b365h",
    "b365d",
    "b365a",
    "FTHG",
    "FTAG",
    "FTR",
    "B365H",
    "B365D",
    "B365A",
}


def _empty_record() -> dict[str, int]:
    return {
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goals_for": 0,
        "goals_against": 0,
        "points": 0,
    }


def _apply_result(record: dict[str, int], goals_for: int, goals_against: int) -> None:
    record["played"] += 1
    record["goals_for"] += goals_for
    record["goals_against"] += goals_against
    if goals_for > goals_against:
        record["won"] += 1
        record["points"] += 3
    elif goals_for == goals_against:
        record["drawn"] += 1
        record["points"] += 1
    else:
        record["lost"] += 1


def _result_letter(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "W"
    if goals_for == goals_against:
        return "D"
    return "L"


def _club_form_row(match: Match, team: str) -> dict[str, Any]:
    goals_for = match.goals_for(team)
    goals_against = match.goals_against(team)
    opponent = match.away if team == match.home else match.home
    return {
        "date": format_date(match.date),
        "opponent": opponent,
        "venue": match.venue_for(team),
        "goals_for": goals_for,
        "goals_against": goals_against,
        "result": _result_letter(goals_for, goals_against),
    }


def last_five(matches: list[Match], team: str, cutoff: date) -> list[dict[str, Any]]:
    prior = [match for match in allowed_rows(matches, cutoff) if match.involves(team)]
    prior.sort(key=lambda match: (match.date, match.time), reverse=True)
    return [_club_form_row(match, team) for match in prior[:5]]


def venue_record(
    matches: list[Match],
    team: str,
    cutoff: date,
    season: str,
    venue: str,
) -> dict[str, int]:
    record = _empty_record()
    for match in current_season_rows(matches, cutoff, season):
        if not match.involves(team):
            continue
        if match.venue_for(team) != venue:
            continue
        _apply_result(record, match.goals_for(team), match.goals_against(team))
    return record


def shooting(matches: list[Match], team: str, cutoff: date, season: str) -> dict[str, int]:
    totals = {
        "shots_for": 0,
        "shots_against": 0,
        "shots_on_target_for": 0,
        "shots_on_target_against": 0,
        "matches": 0,
    }
    for match in current_season_rows(matches, cutoff, season):
        if not match.involves(team):
            continue
        if None in (match.hs, match.a_s, match.hst, match.ast):
            continue
        totals["matches"] += 1
        if team == match.home:
            totals["shots_for"] += match.hs
            totals["shots_against"] += match.a_s
            totals["shots_on_target_for"] += match.hst
            totals["shots_on_target_against"] += match.ast
        else:
            totals["shots_for"] += match.a_s
            totals["shots_against"] += match.hs
            totals["shots_on_target_for"] += match.ast
            totals["shots_on_target_against"] += match.hst
    return totals


def league_table(matches: list[Match], cutoff: date, season: str) -> list[dict[str, Any]]:
    rows = current_season_rows(matches, cutoff, season)
    records: dict[str, dict[str, int]] = {}
    for match in rows:
        records.setdefault(match.home, _empty_record())
        records.setdefault(match.away, _empty_record())
        _apply_result(records[match.home], match.fthg, match.ftag)
        _apply_result(records[match.away], match.ftag, match.fthg)

    ranked = sorted(
        records.items(),
        key=lambda item: (
            -item[1]["points"],
            -(item[1]["goals_for"] - item[1]["goals_against"]),
            -item[1]["goals_for"],
            item[0],
        ),
    )
    table = []
    for position, (team, record) in enumerate(ranked, start=1):
        table.append(
            {
                "team": team,
                "position": position,
                "played": record["played"],
                "won": record["won"],
                "drawn": record["drawn"],
                "lost": record["lost"],
                "goals_for": record["goals_for"],
                "goals_against": record["goals_against"],
                "goal_difference": record["goals_for"] - record["goals_against"],
                "points": record["points"],
            }
        )
    return table


def head_to_head(matches: list[Match], home: str, away: str, cutoff: date) -> list[dict[str, Any]]:
    pair = {home, away}
    meetings = [
        match
        for match in allowed_rows(matches, cutoff)
        if {match.home, match.away} == pair
    ]
    meetings.sort(key=lambda match: (match.date, match.time))
    return [
        {
            "date": format_date(match.date),
            "home": match.home,
            "away": match.away,
            "home_goals": match.fthg,
            "away_goals": match.ftag,
        }
        for match in meetings
    ]


def build_packet(matches: list[Match], fixture: LabFixture) -> dict[str, Any]:
    cutoff = fixture.date
    table = league_table(matches, cutoff, CURRENT_SEASON)
    by_team = {row["team"]: row for row in table}
    return {
        "fixture": {
            "id": fixture.id,
            "date": format_date(fixture.date),
            "home": fixture.home,
            "away": fixture.away,
            "type": fixture.type,
        },
        "current_season": CURRENT_SEASON,
        "table": table,
        "home": {
            "team": fixture.home,
            "table_row": by_team.get(fixture.home),
            "last_5": last_five(matches, fixture.home, cutoff),
            "home_record": venue_record(
                matches, fixture.home, cutoff, CURRENT_SEASON, "home"
            ),
            "shooting": shooting(matches, fixture.home, cutoff, CURRENT_SEASON),
        },
        "away": {
            "team": fixture.away,
            "table_row": by_team.get(fixture.away),
            "last_5": last_five(matches, fixture.away, cutoff),
            "away_record": venue_record(
                matches, fixture.away, cutoff, CURRENT_SEASON, "away"
            ),
            "shooting": shooting(matches, fixture.away, cutoff, CURRENT_SEASON),
        },
        "h2h": head_to_head(matches, fixture.home, fixture.away, cutoff),
    }


def build_sidecar(matches: list[Match], fixture: LabFixture) -> dict[str, Any]:
    target = find_target(matches, fixture.home, fixture.away, fixture.date)
    return {
        "fixture_id": fixture.id,
        "date": format_date(fixture.date),
        "home": fixture.home,
        "away": fixture.away,
        "full_time_home_goals": target.fthg,
        "full_time_away_goals": target.ftag,
        "full_time_result": target.ftr,
        "b365_home": target.b365h,
        "b365_draw": target.b365d,
        "b365_away": target.b365a,
    }


def packet_json(packet: dict[str, Any]) -> str:
    return json.dumps(packet, indent=2, sort_keys=False)


def contains_forbidden_keys(payload: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ODDS_AND_RESULT_KEYS:
                    found.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found
