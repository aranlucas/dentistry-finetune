# Oral-board study lab

Small, local LoRA fine-tuning experiments on Apple Silicon, using pediatric-dentistry
reference material from an oral-board study project. The question each experiment asks
is narrow: does a tiny fine-tune make a small model more useful for study, measured on
questions frozen before any evaluation?

**This is a study experiment, not a clinical assistant or a test of oral-board
competence.** Training and evaluation run entirely on one Mac. No inference or
embedding APIs are used. No clinician has reviewed any model output.

| Workstream | What it does | Status | Where its data lives |
| --- | --- | --- | --- |
| [Sentence-completion pilot](#sentence-completion-pilot) | SmolLM2-135M learns to finish a source sentence, cite the excerpt, or abstain | Complete; negative result | Approved snapshot in [`datasets/pilot-v1`](datasets/pilot-v1/DATASET_CARD.md); metrics in [`runs/`](runs/results.json) |
| [Dental Q&A](#dental-qa-experiment) | Qwen3-0.6B answers AAPD flashcard questions with no excerpts | Short and three-pass runs complete; clinical review pending | `.local/` only |
| [Review dataset](#review-dataset-qa-v2) | Extracts a larger candidate pool and logs per-row review decisions | Candidate review continues; separately authored subsets used in local development runs | `.local/` only |
| [Reference reader](#reproduce-locally) | Answers questions using supplied publisher excerpts, including insufficient-evidence probes | Local development runs; comparison and review status shown on the website | `.local/` only |
| [Practice transcripts](#practice-transcripts) | Five authored, fictional examiner/candidate conversations | Delivered | [`examples/transcripts-v1`](examples/transcripts-v1/README.md) |

## The lab website

A local website shows both experiments. Start it with:

```sh
make dev                                          # https://oral-board-local-lab.localhost via Portless
.venv/bin/python src/server.py --port 8765        # or plain http://127.0.0.1:8765
```

`make dev` runs the server through [Portless](https://github.com/vercel-labs/portless)
(`npm install -g portless`); its first run may ask for `sudo` to bind port 443 and trust
a local certificate.

Each page opens with a charting grid: one column per frozen question, one row per
condition. It borrows the dental-charting convention of blue for completed work and red
for problems.

- **`/` Sentence-completion pilot.** Blue marks an exact answer with the right citation;
  a red cross marks a contract failure; a dashed outline means that run's answer file
  isn't on this Mac. Select any mark to open that case. Below the grid: the answer-contract
  table, how each model failed, training versus validation loss, every case side by side
  with its excerpts, and a one-request local demo.
- **`/qa` Dental Q&A.** Each cell shows word overlap with the authored reference, with
  red flags for repeated phrases (R) and token-limit stops (L). A switch picks the short
  or three-pass run. Below: loss curves, every question with both answers and the
  withheld reference, and a one-question local demo.
- **`/development` Reviewed answers.** Compare actual base and adapter responses,
  inspect each logged assistant judgment, and read the evidence supplied to both
  models. Select earlier development versions or try a question with a short reference
  excerpt. Missing generations and pending judgments remain explicit.

The site reads saved files and never invents answer text. Missing predictions are
labeled as missing, and aggregate scores are never turned into per-case answers. Demo
requests run one at a time in a short-lived process. Model memory is released afterwards
and no request or answer text is logged. The server binds only to loopback, checks
host/origin, and loads no external scripts or fonts. The pages are `web/index.html`,
`web/qa.html`, `web/development.html`, and the shared `web/lab.css` and `web/lab.js`. They support light and dark
mode and phone widths. If model inference is blocked by the resource guard, use the
keyword baseline.

Run selection uses ignored pointer files:

| File | Purpose |
| --- | --- |
| `.local/comparison-run.json` | `{"directory": ".local/<run>"}`: a reproduction of the pilot. Its held-out JSONL bytes must match the frozen snapshot. Its answers are labeled separately; the original results stay selectable. |
| `.local/qa-run.json` | Default Q&A run directory. |
| `.local/qa-run-history.json` | Maps `short` and `long` to Q&A run directories for the run switch. |
| `.local/development-run-history.json` | Maps development run labels to frozen local comparisons; `curated` selects the default reviewed run. |

## Sentence-completion pilot

Each held-out case gives the model a study note quoting the start of a source sentence
and two candidate excerpts. The model must return JSON with the exact ending and the
excerpt it came from. It should abstain when the excerpts are missing, unsupported, or
the request is malformed. A deterministic lexical-extraction baseline uses the quoted
prefix to find and copy the ending; it never reads gold labels.

### What was run

- Apple M5 MacBook Pro, 16 GiB unified memory, shared with other work.
- `HuggingFaceTB/SmolLM2-135M-Instruct`, revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`, Apache-2.0, nongated (~272 MB).
- MLX-LM 0.32.0 and MLX 0.32.3 from PyPI, Python 3.12.13; versions pinned in `requirements.lock`.
- Six training sources (144 examples), two validation sources (16), four held-out sources (24 cases: 16 supported, 8 abstention/adversarial/malformed).
- Rank-8 LoRA on the last four layers; batch 1; assistant-only loss; 384-token ceiling; 325,632 trainable parameters.
- A first 120-update attempt stopped at 59 updates when global swap-outs exceeded the guard, before any checkpoint was saved. One shorter 40-update run, saving every ten updates, followed on the same data and model. Its final adapter was evaluated. No checkpoint was chosen using test results.
- The saved run took 23.7 s, peaked at 471.5 MiB MLX memory, and produced a 1,308,381-byte adapter, with no system swap-out increase during that run. Earlier and later interruptions are kept in the report; overall zero swapping is not claimed.

### Result: negative

| Condition | Parseable JSON | Valid task schema | Exact answer + citation | Abstention cases correct |
| --- | ---: | ---: | ---: | ---: |
| Lexical extraction | 24/24 | 24/24 | 24/24 | 8/8 |
| Base + excerpts | 0/24 | 0/24 | 0/24 | 0/8 |
| Saved LoRA + excerpts | 2/24 | 0/24 | 0/24 | 0/8 |

The base model returned unstructured text. The expected ending appeared somewhere in 15
outputs, which still fails the answer/citation contract. The adapter attempted JSON:
22 outputs didn't parse, one used an invalid citation label, and one paired an abstention
with a citation. None contained the target ending. Validation loss fell, but that did
not predict usable greedy outputs. For this task, prefer deterministic retrieval and
don't scale training on these results.

Adapter evaluation stopped twice on the machine-wide swap guard: once before generation,
then after nine cases. The remaining fifteen cases ran in a quiet window with the same
immutable adapter, data, prompt, and decoding fingerprint. No answer was retried.
Durations distinguish the active segments from the final resumed one. Full metrics are
in [`runs/results.json`](runs/results.json), checked by `src/report.py` without any
model judge.

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

Two training schedules exist:

| Run | Schedule | Evaluation questions |
| --- | --- | --- |
| Short (`qa-v1`) | 64 updates in one bounded job | 12 from held-out source groups |
| Three-pass (`qa-long-v1`, `src/qa_long.py`) | Fixed three-epoch schedule over the short run's training and validation pools, at most 64 updates per bounded job | 12 new questions from the short run's *validation* sources. Their aggregate losses were already observed, so this is not a pristine benchmark. Every earlier held-out group is excluded. |

The three-pass run commits a checkpoint transaction every eight updates: adapter, Adam
moments, step counter, random key, and schedule position. Repeating `run` resumes from
the last commit. The adapter is published locally only after every scheduled update.
There is no held-out checkpoint selection.

**How to read the results.** Word overlap, repetition, and token-limit flags describe
the text; they are not clinical accuracy. Unseen-source questions measure
generalization, not retention of facts learned in training. A knowledge-learning claim
needs human clinical review and a separately frozen retention evaluation. Results stay
local; view them on the website's `/qa` page.

Supporting tools:

- `src/retry_qa.py` makes a fresh training attempt after a resource stop. It reuses the frozen data, configuration, and saved base answers, and preserves the earlier attempt.
- `src/development.py` runs explicitly developmental comparisons against a completed adapter on a separate frozen question file. These are not held-out benchmarks.

## Review dataset (qa-v2)

`src/qa_dataset.py` and `src/oral_dataset_extract.mjs` extract a larger candidate pool
using the Oral Boards project's own parsers. The pool covers flashcards, whole AAPD note
sections, medical-condition sections, study-theme decisions and pathways, and
case-answer sections. It is a review snapshot, not a training set. No source-project
file is modified.

- Builder inputs: the pinned local tokenizer, the read-only publisher database, and the earlier frozen manifests, which preserve their source boundaries. Earlier validation and evaluation families and identifier flags are excluded; excluded rows keep metadata only.
- `reviewable.jsonl` passes structural checks; source support and clinical correctness still need review. `blocked.jsonl` records unmatched or private references, unverified fictional cases, rich content, question rewrites, and over-budget targets. Answers are never truncated.
- No `train.jsonl` is emitted, and no training or evaluation runs during preparation.
- `src/judge_review.py` keeps an append-only, hash-chained journal of per-row review decisions, with the source packets behind each decision. Logged judgments are immutable, and none is a clinical certification.

Review decisions feed a separate successor dataset that preserves this snapshot's
integrity receipt. That successor must freeze source-group splits and questions before
any evaluation.

## Practice transcripts

Five [fictional examiner/candidate conversations](examples/transcripts-v1/README.md)
with follow-up probes and debriefs. They cover a strong answer, a weak opening with
correction, appropriate uncertainty, changing clinical facts, and a consent/safety
boundary. They were authored by the assistant from training-source references only.
They are **not model outputs**, not a benchmark, and not training rows. No clinician has
reviewed them.

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

Sentence-completion pilot:

```sh
.venv/bin/python src/make_data.py --source-db /path/to/oral-boards/search.sqlite
nice -n 10 .venv/bin/python src/bounded.py evaluate --condition retrieval
nice -n 10 .venv/bin/python src/bounded.py evaluate --condition base_rag
nice -n 10 .venv/bin/python src/bounded.py train
nice -n 10 .venv/bin/python src/bounded.py evaluate --condition adapter_rag
.venv/bin/python src/report.py
```

`make_data.py` selects twelve active publisher references by local database ID. For
another database version, pass `--selection /path/to/local-selection.json` mapping
`train`, `valid`, and `test` to nonoverlapping active IDs. Review the selected sources
first.

Dental Q&A (short, then three-pass):

```sh
.venv/bin/python src/qa.py prepare --run-dir .local/qa-v1-first
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

Review dataset:

```sh
nice -n 10 .venv/bin/python src/qa_dataset.py prepare --dataset-dir .local/datasets/qa-v2-first
.venv/bin/python src/qa_dataset.py verify --dataset-dir .local/datasets/qa-v2-first
```

**Assistant review and curated development.** `src/judge_review.py` builds local
publisher-evidence packets and records explicit per-candidate assistant decisions in
an append-only hash-chained journal. Template screening and structural triage are
labelled separately from direct content review. A keep recommendation is provisional
study review, not clinical certification or automatic training approval.

`src/curated_dataset.py` accepts a separately authored specification with questions,
concise answers and individual source assessments. It freezes a new local training
version with source-group separation and a fixed resumable schedule. It never edits
the candidate snapshot or the pilot. `src/development.py`, invoked through
`src/bounded.py --experiment qa-development`, generates answers to separately frozen
practice questions. `src/answer_review.py` records the assistant's explicit judgments;
it does not automatically score semantics. Development feedback can inform a new
version; original held-out outputs cannot.

The loopback website at `/development` reads actual development answers, source-linked
study references and verified judgment journals. These checks probe seen facts under
new wording and are explicitly not an independent generalization benchmark. New
datasets, model weights, outputs, judgments and their metrics stay local; the export
includes only the authored tooling and empty website shell.

`src/grounded.py` prepares a separate excerpt-assisted development condition. It
retrieves from training-publisher documents using question text alone, freezes the
selected excerpts and complete model inputs, and runs both models through
`src/bounded.py --experiment qa-grounded`. It does not retrieve from answer keys or
judgments. The page identifies this input condition and shows the excerpts actually
supplied. Its scores must be compared within the same input condition; they do not
isolate a question-only fine-tuning gain. Partial lexical excerpts can miss needed
evidence, and all new inputs and responses remain local.

A separate reference-reader version can train on assistant-reviewed publisher spans plus authored questions, including deliberately irrelevant excerpts with an insufficient-evidence target. Its frozen comparison is labelled reviewer-selected evidence, not automatic retrieval. The local page shows the same supplied evidence for both models. `src/reference_predict.py`, invoked through `src/bounded.py --experiment qa-reader`, accepts a short user-supplied excerpt for an ephemeral local answer. It uses the unchanged resource and input-token guards; the prompt and answer are not added to a dataset.

**Immutability and resume rules.**

- Frozen data and predictions refuse overwrites. To change data, prompts, hyperparameters, or weights, use a new experiment directory.
- After a guard stop, `--resume` (on `src/evaluate.py` or `src/bounded.py`) continues only missing cases, and checks the model, adapter, data, and decoding fingerprint first. An answer already generated never gets a second chance.
- Resuming a complete evaluation returns its saved summary without loading the model. If every prediction was saved but the summary wasn't, resume rebuilds the metrics and marks timing and memory as unknown.
- A missing fingerprint, or a runtime prompt that differs from the frozen messages, is rejected before inference.
- Only a fully completed adapter may be evaluated. Guard stops preserve the attempt; never overwrite checkpoints or lower resource limits.

**Tests and CI.** Hosted CI runs standard-library synthetic contract and resume tests,
approved-dataset byte/hash/privacy checks, and Python compilation. It never downloads a
model, trains, reads the source corpus, or uploads local files. Run the same checks
locally:

```sh
python3 src/checks.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The local corpus integrity test is skipped on CI because the corpus is deliberately
absent. The versioned approved snapshot is verified separately.

## Resource and privacy boundaries

The guard samples macOS free-memory percentage, process RSS, `vm_stat` swap-outs, and
`pmset` warnings every five seconds and between batches. It stops below 25% free memory,
above 1,200 MiB RSS, on more than 64 MiB of new system-wide swap-outs, or on a
thermal/performance warning. MLX allocator/cache/wired limits are 1,024/64/384 MiB. An
outer wrapper adds a hard wall-clock deadline. These are sampled stop conditions, not an
OS memory guarantee. A fast change can slip between samples, temperatures are not
measured, and global swap can't be attributed to this experiment alone.

Only public publisher references are selected. Identifier-field forms are excluded, and
the selected references had no matches for MRN, patient-name, SSN, or DOB patterns. That
is a limited regex screen, not proof that no identifiers exist. Tables, figure OCR,
numeric statements, references, and apparent contact details are excluded from training
snippets. No patient records or private notes enter training.

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

## Repository layout

| Path | Contents |
| --- | --- |
| `src/` | Data preparation, training, evaluation, reporting, the resource guard, the bounded job wrapper, and the local web server |
| `web/` | The lab website: `index.html`, `qa.html`, `development.html`, and the shared `lab.css` and `lab.js` |
| `configs/` | Frozen experiment configurations |
| `docs/` | Upstream licensing notes, hardware, and model provenance |
| `datasets/pilot-v1/` | The approved, immutable pilot dataset snapshot |
| `runs/` | The pilot's aggregate metrics and training summary |
| `examples/transcripts-v1/` | Authored practice transcripts and their bibliographies |
| `tests/` | Synthetic contract, resume, server, comparison, and transcript tests |
