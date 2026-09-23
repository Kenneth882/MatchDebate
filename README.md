# MatchDebate

MatchDebate is a Premier League match prediction backtest lab. Two AI Advocates make opposing cases from the same historical evidence, and a neutral Judge turns those cases into a prediction that can be checked against the actual result.

## Project goal

The goal is to investigate whether structured, evidence-based debate can produce useful football predictions. Each side must explain why its club should win, while the Judge weighs both arguments, considers the possibility of a draw, and assigns probabilities to all three outcomes.

The lab makes those predictions measurable and reviewable: preserve the evidence and reasoning, record the prediction before revealing the result, and compare Judge versions using identical inputs. Success means better forecasting performance across evaluated fixtures, supported by reasoning grounded in the available evidence.

The current project is a historical backtest experiment. Its five selected fixtures establish the workflow; they do not yet demonstrate reliable forecasting performance or improvement on unseen matches.

## The agents

| Role | Responsibility | Status |
| --- | --- | --- |
| Agent 1 — Home Advocate | Argues that the home club wins, proposes a scoreline, and cites Match Packet fields. | Implemented |
| Agent 2 — Away Advocate | Argues that the away club wins, proposes a scoreline, and cites the same Match Packet. | Implemented |
| Agent 3 — Referee | Monitors a future rebuttal round and keeps both Advocates within the debate rules. | Planned |
| Agent 4 — Judge | Assesses both Advocate Briefs and the packet, then returns outcome probabilities, a compatible scoreline, and cited reasoning. | Implemented |

Both Advocates are deliberately assigned a side. The Judge makes the final prediction; it is not required to agree with either Advocate and may predict a draw.

## How a Lab Run works

1. **Select a Lab Fixture:** a past Premier League match from the configured fixture list.
2. **Build the Match Packet:** assemble only evidence available before the fixture's calendar date. Same-day matches are excluded by the Information Cutoff.
3. **Generate the Advocate Briefs:** each Advocate receives the same packet through its only tool, `read_packet`, and makes its case.
4. **Ask the Judge:** the Judge reads both opening briefs and the shared packet, then produces a structured prediction.
5. **Validate and save:** probabilities must sum to one, the scoreline must match the selected outcome, and reasoning must cite existing packet fields. An invalid response gets one repair attempt.
6. **Reveal and evaluate:** only a saved, valid Judge Prediction can unlock the Sidecar containing the actual result and pre-match odds.

Code selects the outcome with the highest probability. For an exact tie, the scoreline must select one of the tied outcomes. Draws have no special threshold or penalty.

## Evidence boundaries

The v1 Match Packet contains:

- Season-to-date league table.
- Each club's last five available Premier League matches.
- Home and away venue records.
- Premier League head-to-head history available before the Information Cutoff.
- Shots and shots on target, for and against.

The packet excludes xG, injuries, managers, similar-opponent analysis, cup matches, news, and odds. The models are not given raw CSVs or the Sidecar. The application uses those files to prepare inputs and later score predictions.

Recalling the real-life result makes a run unsuitable as backtest evidence. A Judge response that discloses outside knowledge fails immediately. Citation validation checks that referenced fields exist; it cannot prove that every claim follows from them or detect all undisclosed result recall.

## Getting started

Use Python 3.11 or newer. Run these commands from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

If an existing virtual environment reports `No module named matchdebate`, rerun the editable install above from this checkout. You can also prefix commands with `PYTHONPATH=src` to use the local source directly.

The repository includes historical CSVs for the 2022–23 and 2023–24 seasons under `data/raw/`, along with five Lab Fixtures in [`data/lab_fixtures.yaml`](data/lab_fixtures.yaml).

List fixtures and inspect a packet without making model API calls:

```sh
python -m matchdebate list
python -m matchdebate packet luton-burnley
```

To generate briefs and predictions, set `ANTHROPIC_API_KEY` in your environment or in a repository-root `.env` file:

```dotenv
ANTHROPIC_API_KEY=your-api-key
```

Optionally set `ANTHROPIC_MODEL` to choose the model used by the Advocates and, by default, the Judge. The `--model` option on `run` or `judge` overrides only the Judge's model. Generating briefs or Judge predictions makes paid Anthropic API calls.

### Run and score a prediction

```sh
python -m matchdebate run luton-burnley
```

The command prints a unique run ID and, if validation succeeds, the prediction. Replace `RUN_ID` below with that printed ID:

```sh
python -m matchdebate reveal RUN_ID
```

To run all five fixtures:

```sh
python -m matchdebate run --all
```

This prints an `evaluate` command containing the batch's run IDs. Evaluation reveals valid runs and summarizes their scores by Judge version. Runs are not automatically revealed when generated; `reveal` and `evaluate` take **run IDs**, not fixture IDs.

### Compare Judge versions

Reuse a saved run's exact packet and briefs with a different Judge prompt:

```sh
python -m matchdebate judge ORIGINAL_RUN_ID --prompt-file path/to/judge-v2.md
python -m matchdebate evaluate ORIGINAL_RUN_ID NEW_RUN_ID
```

Replace the IDs and prompt path with your own. A custom prompt must request the JSON contract defined in [`src/matchdebate/prompts/judge.md`](src/matchdebate/prompts/judge.md).

Rejudging creates a new Lab Run. It does not pass the previous prediction, revealed result, or odds to the new Judge. For a controlled comparison, use the same saved inputs and fixture coverage for each version, selecting one run per fixture per version.

## Measuring performance

The primary metric is **unnormalized three-outcome Brier loss**:

```text
Brier loss = (p_home - y_home)² + (p_draw - y_draw)² + (p_away - y_away)²
```

Here, `p` is the predicted probability and `y` is 1 for the actual outcome and 0 for the other outcomes. Loss ranges from 0 to 2; lower is better.

Evaluation also reports outcome accuracy, exact-score accuracy, draw frequency, draw accuracy (precision), and actual draw counts. Invalid, failed, and pending runs are tracked separately so that a version's failures remain visible alongside its scores. Judge versions are evaluated separately rather than pooled into a single mean.

See [`docs/judge.md`](docs/judge.md) for the complete validation, replay, and evaluation conventions.

## Saved artifacts and code

| Path | Purpose |
| --- | --- |
| `data/raw/` | Historical Premier League CSV inputs. |
| `data/lab_fixtures.yaml` | Selected backtest fixtures. |
| `data/runs/RUN_ID/run.json` | Saved packet, briefs, configuration, Judge attempts, prediction, and status. |
| `data/sidecars/RUN_ID.json` | Separately stored result and odds, withheld from model inputs. |
| `data/runs/RUN_ID/evaluation.json` | Revealed result, odds, and scores after evaluation. |
| `data/briefs/` | Legacy Advocate Briefs; new runs preserve their own briefs. |
| `src/matchdebate/` | Packet construction, model calls, run storage, validation, evaluation, and CLI. |
| `src/matchdebate/prompts/` | Advocate and Judge instructions. |
| `tests/` | Automated checks for packets, Judge behavior, run handling, and evaluation. |

Run and Sidecar directories are ignored by Git. Sidecar separation is an application/model-input boundary; the local files are still accessible to a person with filesystem access. Legacy briefs alone lack the saved packet and version record needed for controlled Judge comparisons.

## Development

Run the test suite after installing the development dependencies:

```sh
python -m pytest -q
```

Tests stub model API calls and exercise the real fixture, storage, validation, repair, reveal, replay, and scoring workflow. They verify application behavior, not live forecasting quality.

Project terminology is documented in [`CONTEXT.MD`](CONTEXT.MD). Contribution workflows and issue tracking are described in [`docs/agents/`](docs/agents/).

## Planned direction

- **Rebuttal round:** let the Advocates challenge specific points, ask and answer questions, and choose whether to incorporate those exchanges into their briefs.
- **Referee:** supervise the rebuttal round and enforce debate boundaries.
- **Broader evaluation:** expand beyond the five initial fixtures, with separate development and held-out evaluation fixtures.
- **Richer evidence:** explore injuries, xG, manager context, and similar-opponent matches in later packet versions.

These are future extensions. The implemented slice evaluates the opening Advocate Briefs with the Judge and preserves each run for repeatable comparison.
