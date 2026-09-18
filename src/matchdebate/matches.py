from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from matchdebate.paths import SEASON_FILES, parse_date


@dataclass(frozen=True)
class Match:
    season: str
    date: date
    time: str
    home: str
    away: str
    fthg: int
    ftag: int
    ftr: str
    hs: int | None
    a_s: int | None
    hst: int | None
    ast: int | None
    b365h: float | None
    b365d: float | None
    b365a: float | None

    def involves(self, team: str) -> bool:
        return team in (self.home, self.away)

    def goals_for(self, team: str) -> int:
        if team == self.home:
            return self.fthg
        if team == self.away:
            return self.ftag
        raise ValueError(f"{team} did not play in {self.home} vs {self.away}")

    def goals_against(self, team: str) -> int:
        if team == self.home:
            return self.ftag
        if team == self.away:
            return self.fthg
        raise ValueError(f"{team} did not play in {self.home} vs {self.away}")

    def venue_for(self, team: str) -> str:
        if team == self.home:
            return "home"
        if team == self.away:
            return "away"
        raise ValueError(f"{team} did not play in {self.home} vs {self.away}")


def _optional_int(value: str) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)


def _optional_float(value: str) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def load_season(path: Path, season: str) -> list[Match]:
    matches: list[Match] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            matches.append(
                Match(
                    season=season,
                    date=parse_date(row["Date"]),
                    time=row.get("Time") or "",
                    home=row["HomeTeam"],
                    away=row["AwayTeam"],
                    fthg=int(row["FTHG"]),
                    ftag=int(row["FTAG"]),
                    ftr=row["FTR"],
                    hs=_optional_int(row.get("HS") or ""),
                    a_s=_optional_int(row.get("AS") or ""),
                    hst=_optional_int(row.get("HST") or ""),
                    ast=_optional_int(row.get("AST") or ""),
                    b365h=_optional_float(row.get("B365H") or ""),
                    b365d=_optional_float(row.get("B365D") or ""),
                    b365a=_optional_float(row.get("B365A") or ""),
                )
            )
    return matches


def load_all_matches() -> list[Match]:
    matches: list[Match] = []
    for season, path in SEASON_FILES.items():
        matches.extend(load_season(path, season))
    matches.sort(key=lambda match: (match.date, match.time, match.home, match.away))
    return matches


def allowed_rows(matches: list[Match], cutoff: date) -> list[Match]:
    return [match for match in matches if match.date < cutoff]


def current_season_rows(matches: list[Match], cutoff: date, season: str) -> list[Match]:
    return [
        match
        for match in allowed_rows(matches, cutoff)
        if match.season == season
    ]


def find_target(matches: list[Match], home: str, away: str, on: date) -> Match:
    found = [
        match
        for match in matches
        if match.date == on and match.home == home and match.away == away
    ]
    if len(found) != 1:
        raise ValueError(
            f"Expected one match {home} vs {away} on {on.isoformat()}, found {len(found)}"
        )
    return found[0]
