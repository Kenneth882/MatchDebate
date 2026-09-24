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
The hidden full-time score and pre-match odds for a Lab Fixture, opened only after the Judge's prediction has been recorded.
_Avoid_: answer key, ground truth file, odds feed

**Advocate Brief**:
The home or away club's written case that they will win, with a proposed scoreline, citing only Match Packet fields.
_Avoid_: prediction, report, scouting report, analysis

**Judge**:
The neutral assessor that uses both Advocate Briefs and their shared Match Packet to make the recorded prediction for a Lab Fixture, replacing the human pick.
_Avoid_: third advocate

**Judge Prediction**:
The Judge's probabilities for home win, draw, and away win, together with an outcome selected by highest probability, a compatible full-time scoreline, and supporting reasoning. Draws have no special selection threshold; an exact tie is resolved by the scoreline only when its outcome is among those tied for highest probability.
_Avoid_: verdict on which advocate argued best

**Evaluation Score**:
The unnormalized three-outcome Brier loss of a recorded Judge Prediction against the revealed result: the sum of squared errors for the home-win, draw, and away-win probabilities, with equal weight for each outcome. Lower is better (0 to 2 per prediction); comparisons use mean loss across valid evaluated fixtures, with selected-outcome accuracy, exact-score accuracy, draw frequency, draw accuracy, and invalid-run counts reported separately.
_Avoid_: training reward

**Judge Reasoning Failure**:
A flaw in how the Judge assesses the Advocate Briefs against the Match Packet, such as accepting an unsupported claim, overlooking conflicting evidence, or mishandling a disagreement. A wrong predicted outcome alone does not establish a reasoning failure.
_Avoid_: any incorrect prediction

**Lab Run**:
A preserved attempt to predict one Lab Fixture, with its Match Packet, both Advocate Briefs, Judge version, and prediction or failure. Judge versions can be compared using the same saved packet and briefs across separate Lab Runs.
_Avoid_: overwrite of a fixture's previous prediction

**Lab Fixture**:
A past Premier League match chosen for a backtest run, with Agent 1 as home and Agent 2 as away.
_Avoid_: live fixture, upcoming match, gameweek pick
