# MatchDebate

A Premier League backtest lab where two advocates argue from a shared pre-kickoff packet.

## Language

**Match Packet**:
The leak-free facts both advocates may use for one Lab Fixture: table, last-5, venue records, H2H, and shooting, all from matches strictly before the fixture date.
_Avoid_: dump, CSV, dataset, scouting report

**Information Cutoff**:
The rule that only matches dated before the Lab Fixture's calendar date count as known. Same-day matches are unseen.
_Avoid_: as-of, snapshot, live data

**Sidecar**:
The hidden full-time score and pre-match odds for a Lab Fixture, opened only after a human has picked a winner.
_Avoid_: answer key, ground truth file, odds feed

**Advocate Brief**:
The home or away club's written case that they will win, with a proposed scoreline, citing only Match Packet fields.
_Avoid_: prediction, report, scouting report, analysis

**Lab Fixture**:
A past Premier League match chosen for a backtest run, with Agent 1 as home and Agent 2 as away.
_Avoid_: live fixture, upcoming match, gameweek pick
