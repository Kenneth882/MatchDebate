Project Scope: This project is being built to create a match predectior for soccer matches. However the way it would be built is by using 3 agents. 

Agent1 and Agent2:
This slice is a lab backtest, not a live product. Pick a past Premier League Lab Fixture. Agent 1 is the home advocate; Agent 2 is the away advocate. Both receive the same Match Packet and may only call `read_packet`. Each Advocate Brief always claims that side wins and proposes a scoreline, citing only packet fields (table, last-5, venue record, H2H, shooting).

v1 packet: season-to-date table, last 5, home/away venue splits, Premier League H2H before the Information Cutoff, shots and shots on target. No xG, injuries, managers, similar opponents, cups, news, or odds. Agents never see the raw CSVs or the Sidecar. Recalling the real-life result is a failed run.

You read both briefs, pick a winner and score, then open the Sidecar (result + odds) to compare. Later work may add injuries, xG, manager context, and similar-opponent matches.

Agent 3: Agent 3 will act as Referee that will simply monitor the Rebutal round and keep both agents in Line if necassary.
Rebutal Round: In this round the agents will argue against one another with their report and have turns to argue against specific points with both agents being able to question each others points as well as respond. The agents will then have a choice to add these rebutal questions to their reports or omit them.




Agent4:
Agent 4 is the judge. Agent 4 looks at the final reports and picks a side which it thinks will win and by what score. This will be done by looking at both reports and highliting how it came to that conclusion

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the repo root, ADRs in `docs/adr/`. See `docs/agents/domain.md`.
