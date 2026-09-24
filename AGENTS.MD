Project Scope: A Premier League match prediction backtest lab with home and away Advocates and a Judge. Rebuttals and the Referee are deferred.

Agent1 and Agent2:
This slice is a lab backtest, not a live product. Pick a past Premier League Lab Fixture. Agent 1 is the home advocate; Agent 2 is the away advocate. Both receive the same Match Packet and may only call `read_packet`. Each Advocate Brief always claims that side wins and proposes a scoreline, citing only packet fields (table, last-5, venue record, H2H, shooting).

v1 packet: season-to-date table, last 5, home/away venue splits, Premier League H2H before the Information Cutoff, shots and shots on target. No xG, injuries, managers, similar opponents, cups, news, or odds. Agents never see the raw CSVs or the Sidecar. Recalling the real-life result is a failed run.

The Judge reads both briefs and the shared Match Packet, and replaces the manual pick. A valid Judge Prediction must be saved before the Sidecar (result + odds) can be revealed and scored. Later work may add injuries, xG, manager context, and similar-opponent matches.

Rebuttal round and Agent 3 (Referee): Deferred pending review of Judge failures. Before proposing either extension, read the scope decision in `docs/judge.md`.

Agent4:
Agent 4 is the Judge. It returns probabilities for home win, draw, and away win, a compatible scoreline, and reasoning citing Match Packet fields. Code selects the highest-probability outcome; for an exact tie, the scoreline must select one of the tied outcomes. There is no special draw threshold or penalty. The implemented slice judges the opening Advocate Briefs.

Evaluate recorded predictions with unnormalized three-outcome Brier loss (lower is better), tracking outcome accuracy, exact-score accuracy, draw diagnostics, and failures separately. Allow one repair attempt for an invalid Judge response. A disclosed use of outside knowledge fails the run immediately. Preserve Lab Runs and reuse their exact packet and briefs when comparing Judge versions; never feed a previous prediction, revealed result, or odds into the Judge. See `docs/judge.md` for the workflow and evaluation conventions.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the repo root, ADRs in `docs/adr/`. See `docs/agents/domain.md`.
