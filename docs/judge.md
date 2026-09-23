# Judge and evaluation workflow

The Judge evaluates the two opening Advocate Briefs against their shared Match
Packet. It replaces the manual pick. The first slice uses the five existing Lab
Fixtures; referee and rebuttal behavior are not part of this slice.

## Run from the repository root

Use the existing virtual environment, or install the project and development
dependencies into one with `python -m pip install -e '.[dev]'`.
Set `ANTHROPIC_API_KEY` in the environment or the repo's `.env`.
`ANTHROPIC_MODEL` configures the advocates and the default Judge model;
`--model` overrides just the Judge. Each run makes paid model API calls.

The `PYTHONPATH=src` prefix below ensures the current checkout is used even if
the virtual environment has an editable install pointing at an older location.

```sh
PYTHONPATH=src .venv/bin/python -m matchdebate run luton-burnley
PYTHONPATH=src .venv/bin/python -m matchdebate run --all
```

Each run prints its unique `RUN_ID` and prediction. It saves the packet, both
briefs, Judge prompt, requested model, response model, response IDs, token usage,
raw attempts, validation feedback, and final status under
`data/runs/RUN_ID/run.json`. Advocate model and prompts are also recorded.
Existing files under `data/briefs/` are left untouched. Legacy briefs alone lack
a saved packet/version record; start a new run to establish comparison inputs.

Reveal and evaluate only after a valid prediction has been saved:

```sh
PYTHONPATH=src .venv/bin/python -m matchdebate reveal RUN_ID
PYTHONPATH=src .venv/bin/python -m matchdebate evaluate RUN_ID_1 RUN_ID_2 RUN_ID_3 RUN_ID_4 RUN_ID_5
```

`reveal` now takes a **run ID**, not a fixture ID. `evaluate` reveals the selected
valid runs and reports metrics separately for each Judge version. Invalid,
failed, or pending runs remain unrevealed and are counted separately; incomplete
evaluation exits with status 1. `run --all` prints an evaluation command containing
the IDs for its batch, and does not reveal results automatically.

The private Sidecar is saved separately under `data/sidecars/RUN_ID.json`.
After an explicit reveal/evaluation, `data/runs/RUN_ID/evaluation.json` contains
the result, odds, and computed scores. Both artifact directories are ignored by
Git. This is an application/model-input boundary, not encryption against a human
who can access the local files.

## Compare Judge versions

```sh
PYTHONPATH=src .venv/bin/python -m matchdebate judge ORIGINAL_RUN_ID --prompt-file path/to/judge-v2.md
PYTHONPATH=src .venv/bin/python -m matchdebate evaluate ORIGINAL_RUN_ID NEW_RUN_ID
```

`judge` saves a new run using the original run's exact packet and briefs. It does
not rerun advocates or supply earlier Judge responses, evaluations, result, or
odds to the new Judge, even if the source run was already revealed. A custom
prompt must request the same JSON contract as `src/matchdebate/prompts/judge.md`.

Repeat this for each of the five original runs to compare two prompts on all
five fixtures. Select one run per fixture per Judge version; duplicate entries
are rejected before evaluation. Versions are never pooled into one mean. The
summary flags unequal saved inputs or incomplete coverage, since those means
are not a controlled comparison. Report failures alongside scores to avoid
rewarding a version that only produces valid predictions on easier fixtures.

The version fingerprint includes the full prompt, requested model, SDK version,
generation settings, and validation/selection policy version. When changing Judge rules,
increment `POLICY_VERSION` in `judge.py`. Actual response models are also saved;
a provider's mutable model alias is not a guarantee of identical model weights.

## Prediction and validation

The model returns JSON containing:

- `probabilities`: numeric `home`, `draw`, and `away`, each in [0, 1], summing to
  1 (floating-point tolerance 1e-9). Values are not silently normalized.
- `scoreline`: nonnegative integer `home` and `away` goal counts.
- `reasoning`: nonempty claims, each with existing `packet_fields` citations.
  The prompt asks the Judge to assess both briefs and the draw evidence.
- `outside_knowledge_used`: a boolean disclosure; `true` fails the run immediately.

Code derives `outcome` from the largest probability. For an exact tie, the
scoreline selects among tied outcomes, and `tied_outcomes` records the tie. For
example, 45% home / 10% draw / 45% away allows 2–1 or 1–2, but rejects 1–1.
32% home / 36% draw / 32% away permits a draw without requiring 50% confidence.

One surrounding Markdown JSON fence is accepted as formatting; its contents
still undergo every validation check, and the raw fenced response is preserved.
Malformed JSON, bad probabilities, incompatible scores, missing/nonexistent
citations, or incomplete responses receive one repair attempt with specific
feedback and the same inputs. A second invalid response is saved as `invalid`,
with no fallback prediction. API/configuration failures are recorded as `error`.
Disclosed outside knowledge is not repaired using the contaminated conversation.

Citation checks establish that fields exist in the allowed packet evidence;
they cannot prove every claim is entailed by those fields. Likewise, a disclosure
field cannot reliably detect undisclosed result recall. Review reasoning as well
as numerical metrics; any discovered result recall makes the run unsuitable as
backtest evidence.

## Evaluation conventions

For probabilities `p_home`, `p_draw`, `p_away`, and one-hot actual outcome `y`:

```text
Brier loss = (p_home - y_home)^2 + (p_draw - y_draw)^2 + (p_away - y_away)^2
```

This is the unnormalized three-category sum (0 to 2), with equal outcome weights.
Zero is perfect; lower mean loss is better. No extra draw reward or penalty is
applied. Outcome accuracy and exact-score accuracy are separate measures.

Draw frequency is predicted draws / scored runs. Draw accuracy means precision:
correctly predicted draws / predicted draws. It is `null` if no draws were
predicted. Counts of actual draws are also reported. All prediction metrics
exclude invalid/error/pending runs; their counts and coverage remain visible.

Five selected fixtures verify the workflow; they do not establish calibration,
reliable draw weights, or improvement on unseen fixtures. Expanding to separate
development and held-out evaluation fixtures is the next evaluation milestone.

## Verification

```sh
.venv/bin/python -m pytest -q
```

Tests stub the model API while exercising the real five-fixture packet building,
storage, validation, repair, reveal boundary, replay, and scoring workflow. These
tests verify behavior, not the live Judge's forecasting ability.
