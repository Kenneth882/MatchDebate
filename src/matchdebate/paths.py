from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SIDECAR_DIR = DATA_DIR / "sidecars"
BRIEFS_DIR = DATA_DIR / "briefs"
FIXTURES_PATH = DATA_DIR / "lab_fixtures.yaml"

DATE_FORMAT = "%d/%m/%Y"
CURRENT_SEASON = "2023-24"
PRIOR_SEASON = "2022-23"

SEASON_FILES = {
    PRIOR_SEASON: RAW_DIR / "epl-2022-23.csv",
    CURRENT_SEASON: RAW_DIR / "epl-2023-24.csv",
}


def parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FORMAT).date()


def format_date(value: date) -> str:
    return value.strftime(DATE_FORMAT)
