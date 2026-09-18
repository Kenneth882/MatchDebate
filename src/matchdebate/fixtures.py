from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import yaml

from matchdebate.paths import FIXTURES_PATH, parse_date


@dataclass(frozen=True)
class LabFixture:
    id: str
    date: date
    home: str
    away: str
    type: str


def load_fixtures() -> list[LabFixture]:
    payload = yaml.safe_load(FIXTURES_PATH.read_text())
    return [fixture_from_dict(item) for item in payload["fixtures"]]


def fixture_from_dict(item: dict) -> LabFixture:
    return LabFixture(
        id=item["id"],
        date=parse_date(item["date"]),
        home=item["home"],
        away=item["away"],
        type=item["type"],
    )


def get_fixture(fixture_id: str) -> LabFixture:
    for fixture in load_fixtures():
        if fixture.id == fixture_id:
            return fixture
    known = ", ".join(f.id for f in load_fixtures())
    raise KeyError(f"Unknown fixture {fixture_id!r}. Known: {known}")
