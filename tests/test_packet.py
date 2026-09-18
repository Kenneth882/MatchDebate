from __future__ import annotations

import json
from typing import Any

import pytest

from matchdebate.fixtures import get_fixture, load_fixtures
from matchdebate.matches import load_all_matches
from matchdebate.packet import build_packet, build_sidecar, contains_forbidden_keys
from matchdebate.paths import format_date

LAB_IDS = [
    "luton-burnley",
    "luton-tottenham",
    "crystal-palace-forest",
    "arsenal-man-city",
    "man-city-brighton",
]


@pytest.fixture(scope="module")
def matches():
    return load_all_matches()


def _dates_in(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "date" and isinstance(value, str):
                found.append(value)
            found.extend(_dates_in(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_dates_in(item))
    return found


def _table_row(packet: dict[str, Any], team: str) -> dict[str, Any]:
    for row in packet["table"]:
        if row["team"] == team:
            return row
    raise AssertionError(f"{team} missing from table")


@pytest.mark.parametrize("fixture_id", LAB_IDS)
def test_packet_omits_result_and_odds_keys(matches, fixture_id):
    fixture = get_fixture(fixture_id)
    packet = build_packet(matches, fixture)
    forbidden = contains_forbidden_keys(packet)
    assert forbidden == set()
    blob = json.dumps(packet)
    assert "B365" not in blob
    assert "FTHG" not in blob
    assert "FTAG" not in blob
    assert '"FTR"' not in blob


@pytest.mark.parametrize("fixture_id", LAB_IDS)
def test_packet_drops_same_calendar_date(matches, fixture_id):
    fixture = get_fixture(fixture_id)
    packet = build_packet(matches, fixture)
    cutoff = format_date(fixture.date)
    date_hits = _dates_in(packet)
    fixture_date_hits = [value for value in date_hits if value == cutoff]
    assert fixture_date_hits == [cutoff]
    assert cutoff not in _dates_in(packet["home"]["last_5"])
    assert cutoff not in _dates_in(packet["away"]["last_5"])
    assert cutoff not in _dates_in(packet["h2h"])


def test_arsenal_city_packet_hides_target_and_other_eighth_october_matches(matches):
    fixture = get_fixture("arsenal-man-city")
    packet = build_packet(matches, fixture)
    assert packet["fixture"]["date"] == "08/10/2023"
    assert packet["home"]["last_5"] != []
    assert not any(row["date"] == "08/10/2023" for row in packet["home"]["last_5"])
    assert not any(row["date"] == "08/10/2023" for row in packet["away"]["last_5"])
    assert not any(row["date"] == "08/10/2023" for row in packet["h2h"])
    assert not any(
        row["home"] == "Arsenal"
        and row["away"] == "Man City"
        and row["date"] == "08/10/2023"
        for row in packet["h2h"]
    )


def test_arsenal_points_before_city_match_are_hand_computed(matches):
    """Independent reconstruction: Arsenal's 2023/24 PL results with date < 08/10/2023.

    12/08 Forest H 2-1 W, 21/08 Palace A 0-1 W, 26/08 Fulham H 2-2 D,
    03/09 United H 3-1 W, 17/09 Everton A 0-1 W, 24/09 Spurs H 2-2 D,
    30/09 Bournemouth A 0-4 W.
    """
    packet = build_packet(matches, get_fixture("arsenal-man-city"))
    arsenal = _table_row(packet, "Arsenal")
    assert arsenal["played"] == 7
    assert arsenal["won"] == 5
    assert arsenal["drawn"] == 2
    assert arsenal["lost"] == 0
    assert arsenal["goals_for"] == 15
    assert arsenal["goals_against"] == 6
    assert arsenal["goal_difference"] == 9
    assert arsenal["points"] == 17

    city = _table_row(packet, "Man City")
    # 11/08 Burnley A 0-3 W, 19/08 Newcastle H 1-0 W, 27/08 Sheff Utd A 1-2 W,
    # 02/09 Fulham H 5-1 W, 16/09 West Ham A 1-3 W, 23/09 Forest H 2-0 W,
    # 30/09 Wolves A 2-1 L.
    assert city["played"] == 7
    assert city["won"] == 6
    assert city["drawn"] == 0
    assert city["lost"] == 1
    assert city["goals_for"] == 17
    assert city["goals_against"] == 5
    assert city["goal_difference"] == 12
    assert city["points"] == 18


def test_luton_burnley_h2h_is_empty(matches):
    packet = build_packet(matches, get_fixture("luton-burnley"))
    assert packet["h2h"] == []


def test_arsenal_city_sidecar_is_home_win_and_not_in_packet(matches):
    fixture = get_fixture("arsenal-man-city")
    packet = build_packet(matches, fixture)
    sidecar = build_sidecar(matches, fixture)
    assert sidecar["full_time_home_goals"] == 1
    assert sidecar["full_time_away_goals"] == 0
    assert sidecar["full_time_result"] == "H"
    assert sidecar["b365_home"] == 2.9
    assert "full_time_home_goals" not in packet
    assert "b365_home" not in packet


def test_all_lab_fixtures_resolve(matches):
    for fixture in load_fixtures():
        sidecar = build_sidecar(matches, fixture)
        assert sidecar["home"] == fixture.home
        assert sidecar["away"] == fixture.away
