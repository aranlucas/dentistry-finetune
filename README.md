# Oral-board study lab

Small, local LoRA fine-tuning experiments on Apple Silicon, using pediatric-dentistry
reference material from an oral-board study project. The question each experiment asks
is narrow: does a tiny fine-tune make a small model more useful for study, measured on
questions frozen before any evaluation?

**This is a study experiment, not a clinical assistant or a test of oral-board
competence.** Training and evaluation run entirely on one Mac. No inference or
embedding APIs are used. No clinician has reviewed any model output.

Start with the [negative sentence-completion result](#sentence-completion-pilot),
[question-only Q&A](#dental-qa-experiment), or the
[review and reference-reader workflow](#review-dataset-qa-v2).
[Fictional practice transcripts](examples/transcripts-v1/README.md) are separately
authored teaching material, not model outputs or training/evaluation rows.

## The lab website

A local website shows both experiments. Start it with:

```sh
make dev                                          # build, then https://oral-board-local-lab.localhost via Portless
make build && .venv/bin/python src/server.py      # or plain http://127.0.0.1:8765
```

`make build` runs `npm ci` when needed and builds `web/dist/`. `make dev`
requires [Portless](https://github.com/vercel-labs/portless) (`npm install -g portless`);
its first run may ask for `sudo` to bind port 443 and trust a local certificate.
For live reload, start `.venv/bin/python src/server.py` and run `make web-dev`;
Vite forwards `/api` to port 8765 (`LAB_API` overrides the target).

The pages are `/` (pilot), `/qa` (question-only Q&A), and `/development`
(reviewed comparisons). They read saved answers; missing predictions stay missing.
Development judgments are assistant review, not clinical review. Demo requests run
one at a time in a short-lived process and do not log prompts or answers. The server
binds to loopback and checks host/origin. Use the keyword baseline if model inference
is blocked by the resource guard.

Run selection uses ignored pointer files:

| File | Purpose |
| --- | --- |
| `.local/comparison-run.json` | `{"directory": ".local/<run>"}`: a reproduction of the pilot. Its held-out JSONL bytes must match the frozen snapshot. Its answers are labeled separately; the original results stay selectable. |
| `.local/qa-run.json` | Default Q&A run directory. |
| `.local/qa-run-history.json` | Maps `short` and `long` to Q&A run directories for the run switch. |
| `.local/development-run-history.json` | Maps development run labels to objects with a `directory` for each frozen local comparison; `curated` selects the default reviewed run. |

## Sentence-completion pilot

Each held-out case gives the model a study note quoting the start of a source sentence
and two candidate excerpts. The model must return JSON with the exact ending and the
excerpt it came from. It should abstain when the excerpts are missing, unsupported, or
the request is malformed. A deterministic lexical-extraction baseline uses the quoted
prefix to find and copy the ending; it never reads gold labels.

The frozen [dataset card](datasets/pilot-v1/DATASET_CARD.md) describes the
144/16/24 train/validation/test rows, construction, and supervision. The saved pilot
used SmolLM2-135M-Instruct on a 16 GiB Apple M5 Mac, with 40 rank-8 LoRA updates.
See [`configs/pilot.json`](configs/pilot.json),
[model provenance](docs/model-provenance.json), and
[training summary](runs/training-summary.json) for the exact recipe and artifacts.

### Result: negative

| Condition | Parseable JSON | Valid task schema | Exact answer + citation | Abstention cases correct |
| --- | ---: | ---: | ---: | ---: |
| Lexical extraction | 24/24 | 24/24 | 24/24 | 8/8 |
| Base + excerpts | 0/24 | 0/24 | 0/24 | 0/8 |
| Saved LoRA + excerpts | 2/24 | 0/24 | 0/24 | 0/8 |

Neither model met the answer/citation contract; falling validation loss did not
predict usable greedy outputs. For this task, prefer deterministic extraction.
The initial 120-update attempt stopped at 59 updates on the swap guard without a
saved checkpoint; the shorter run was fixed before evaluation. Adapter evaluation
also stopped and resumed with the same frozen recipe, without retrying answers.
The [aggregate report](runs/results.json) retains failures and interruptions;
its final-segment duration must not be read as total evaluation time. Overall zero
swapping is not claimed. `src/report.py` recomputes metrics from local raw outputs
without a model judge.

### What the evaluation means

The keyword baseline's perfect score is expected: the question quotes the start of the
target sentence. Full-corpus retrieval recall, paraphrase reasoning, medical validity, and
exam performance are not measured. Metrics are JSON/schema validity, exact answer plus
citation, quote containment, citation existence, abstention correctness, and unsupported
answers. Invalid output is a failure: there is no JSON repair, prompt change, or
constrained decoding. Abstaining on a supported case is also a failure. A no-context
evaluation, when run, expects abstention for every question.

Source groups, exact normalized sentences, and positive question templates are disjoint
across splits, though similar terminology can remain. Questions were generated
mechanically from excerpts: a small convenience sample, not an expert-curated
examination.

## Dental Q&A experiment

`qa-v1` uses the publisher-linked AAPD flashcard decks from the authorized local Oral
Boards project, read with that project's own Markdown parsers and read-only source
database. Both models get the question alone, with no excerpts. The authored reference
answers are withheld during generation. The authored answers are study aids, not
official answer keys or certified clinical guidance.

- Model: a community MLX 4-bit conversion of Qwen3-0.6B, with thinking disabled for both training and inference. Pinned revisions and file hashes are in [`docs/QWEN3_PROVENANCE.json`](docs/QWEN3_PROVENANCE.json). The adapter is MLX format and loads only against that exact model; it is not a Transformers or PEFT checkpoint.
- Excluded: medical-condition notes, cases, private study guides, inactive publisher documents, identifier-form matches, and over-budget sequences.
- Source groups join shared PDFs, normalized duplicate pairs, and explicit answer links; implicit topic overlap can remain. Groups and questions are frozen before generation.
- Configuration: [`configs/qa-v1.json`](configs/qa-v1.json).

The short run evaluates 12 questions from held-out source groups. The three-pass
run (`src/qa_long.py`) instead uses 12 new questions from the short run's validation
sources, whose aggregate losses were already observed; this is not a pristine
benchmark. Earlier held-out groups are excluded. It resumes committed optimizer and
adapter state after a stop and exposes the final adapter only when its fixed schedule
is complete. No checkpoint is selected on held-out results.

**How to read the results.** Word overlap, repetition, and token-limit flags describe
the text; they are not clinical accuracy. Unseen-source questions measure
generalization, not retention of facts learned in training. A knowledge-learning claim
needs human clinical review and a separately frozen retention evaluation. Results stay
local; view them on the website's `/qa` page.

`src/retry_qa.py` preserves a stopped attempt while starting another on the same
frozen data and saved base answers. `src/development.py` compares a completed adapter
on separate frozen questions; these developmental comparisons are not held-out tests.

## Review dataset (qa-v2)

`src/qa_dataset.py` uses the Oral Boards project's parsers and read-only publisher
database to extract a local candidate snapshot. Earlier validation/evaluation source
families and identifier flags are excluded. `reviewable.jsonl` means structurally
eligible, not clinically approved; `blocked.jsonl` retains unresolved references,
case provenance, rich content, rewrites, and over-budget answers. Answers are never
truncated. Preparation emits no training set and runs no model evaluation.

`src/judge_review.py` records per-candidate decisions in an append-only, hash-chained
journal. Structural triage is separate from direct content review. A keep decision
is provisional and does not authorize training. Use a separately authored successor
via `src/curated_dataset.py` for reviewed training material; preserve the candidate
snapshot and freeze new source groups and questions before evaluation.

Development input conditions must remain distinct:

- Question-only comparisons use `src/development.py`.
- `src/grounded.py` freezes question-based retrieval from training-publisher documents,
  without consulting answer keys or judgments. Lexical excerpts may miss evidence.
- Reference-reader comparisons use reviewer-selected evidence, including irrelevant
  excerpts with an insufficient-evidence target. `src/reference_predict.py` accepts
  a short user-supplied excerpt for an ephemeral local answer.

Compare models within the same input condition; excerpt-assisted scores do not isolate
a question-only fine-tuning gain. `src/answer_review.py` records explicit assistant
judgments, not automatic semantic scores. Development feedback may inform a new version;
held-out output must never be used for tuning. All new data, answers, judgments, and
metrics remain local.

## Reproduce locally

Requires an Apple Silicon Mac and an authorized local copy of the oral-board reference
database (read-only; the original repository is not modified). Run one model job at a
time: a process lock in `src/bounded.py` enforces this.

```sh
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.lock
.venv/bin/python src/download_model.py
.venv/bin/python src/checks.py
```

**Pilot reproduction:** the pilot scripts write root-level `data/`, `adapters/`,
and `runs/`; `src/report.py` overwrites `runs/results.json`. Reproduce in a separate
local experiment copy, preserving this repository's frozen snapshot and aggregate
results. `src/make_data.py --source-db /path/to/oral-boards/search.sqlite` selects
twelve active references by database ID. For a different database version, supply
`--selection /path/to/local-selection.json` mapping `train`, `valid`, and `test` to
reviewed, nonoverlapping active IDs. Run evaluation/training through `src/bounded.py`.

Dental Q&A (short, then three-pass):

```sh
.venv/bin/python src/qa.py prepare --run-dir .local/qa-v1-first --source-project /path/to/oral-boards
nice -n 10 .venv/bin/python src/bounded.py train --experiment qa-v1 --run-dir .local/qa-v1-first
nice -n 10 .venv/bin/python src/bounded.py evaluate --experiment qa-v1 --run-dir .local/qa-v1-first --qa-condition base
nice -n 10 .venv/bin/python src/bounded.py evaluate --experiment qa-v1 --run-dir .local/qa-v1-first --qa-condition adapter
.venv/bin/python src/qa.py report --run-dir .local/qa-v1-first

.venv/bin/python src/qa_long.py prepare --from-run .local/qa-v1-first --run-dir .local/qa-long-first
nice -n 10 .venv/bin/python src/qa_long.py run --run-dir .local/qa-long-first   # repeat until complete
nice -n 10 .venv/bin/python src/bounded.py evaluate --experiment qa-long-v1 --run-dir .local/qa-long-first --qa-condition base
nice -n 10 .venv/bin/python src/bounded.py evaluate --experiment qa-long-v1 --run-dir .local/qa-long-first --qa-condition adapter
.venv/bin/python src/qa.py report --run-dir .local/qa-long-first
```

Review dataset (requires the local tokenizer downloaded by Q&A preparation):

```sh
nice -n 10 .venv/bin/python src/qa_dataset.py prepare --dataset-dir .local/datasets/qa-v2-first \
  --source-project /path/to/oral-boards --model-dir .local/qa-v1-first/models/qwen3-0.6b-4bit
.venv/bin/python src/qa_dataset.py verify --dataset-dir .local/datasets/qa-v2-first
```

**Immutability and resume rules.**

- Q&A dataset versions and saved predictions refuse overwrites. To change data, prompts, hyperparameters, or weights, use a new experiment directory.
- After a guard stop, `--resume` (on `src/evaluate.py` or `src/bounded.py`) continues only missing cases, and checks the model, adapter, data, and decoding fingerprint first. An answer already generated never gets a second chance.
- Resuming a complete evaluation returns its saved summary without loading the model. If every prediction was saved but the summary wasn't, resume rebuilds the metrics and marks timing and memory as unknown.
- A missing fingerprint, or a runtime prompt that differs from the frozen messages, is rejected before inference.
- Only a fully completed adapter may be evaluated. Guard stops preserve the attempt; never overwrite checkpoints or lower resource limits.

**Checks:**

```sh
.venv/bin/python src/checks.py
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

These checks need no model or source corpus. The local corpus integrity test skips
when the corpus is absent; the approved snapshot is checked separately. Hosted CI
also compiles Python and runs the website's lint, format, tests, and build commands
from [`web/package.json`](web/package.json), without downloading models or training.

## Resource and privacy boundaries

Run model jobs one at a time, at low priority, through `src/bounded.py`. Resource
limits live in [`configs/pilot.json`](configs/pilot.json); Q&A configurations must
retain those guards. Stops cover low free memory, process RSS, system-wide swap-out
growth, thermal/performance warnings, and wall-clock deadlines. These sampled checks
are not an OS memory guarantee: fast changes can slip between samples, temperatures
are not measured, and global swap cannot be attributed to this experiment alone.
Never lower limits to get past a stop.

The pilot selected public publisher references, excluding identifier-field forms.
Selected references had no matches for MRN, patient-name, SSN, or DOB patterns. That
is a limited regex screen, not proof that no identifiers exist. Tables, figure OCR,
numeric statements, references, and apparent contact details are excluded from pilot
training snippets. Do not train on patient records or private notes.

The documents keep their publisher copyright; no open license was verified. The user
authorized local study use and, separately, the private `pilot-v1` snapshot. No general
redistribution permission or dataset license is implied. Don't publish or relicense
source-derived data without a rights review. See [`docs/UPSTREAM.md`](docs/UPSTREAM.md)
and the [dataset card](datasets/pilot-v1/DATASET_CARD.md).

Only `src/export_source.py`'s allowlist is intended for GitHub:

- authored code and configuration, including the website (`web/`)
- model provenance
- the pilot's aggregate metrics
- the six approved files in `datasets/pilot-v1`
- the seven authored files in `examples/transcripts-v1`

The export checks everything else for accidental source content. Git ignores runtime
data, unapproved dataset versions, raw predictions, weights, adapters, screenshots, and
model caches. The pilot's dataset JSONL bytes, counts, and hashes are frozen; any
improved dataset needs a new version and its own sharing authorization.
