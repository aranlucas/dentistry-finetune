# Local Study Lab

A bounded Apple Silicon LoRA experiment using local oral-board reference documents. It trains a tiny model to complete a short study note from supplied excerpts, cite the matching excerpt, and abstain when evidence is absent. It also provides a stronger deterministic lexical extraction baseline.

**This is a study formatting/grounding pilot, not a clinical assistant or a test of general oral-board competence.** At the user's explicit request, the original generated train/validation/test datasets, containing short source excerpts, and provenance are included in this private repository under [`datasets/pilot-v1`](datasets/pilot-v1/DATASET_CARD.md). Original source PDFs/full corpus, raw predictions, and adapter/model weights remain local. No inference or embedding APIs are used.

Five [sample practice transcripts](examples/transcripts-v1/README.md) provide fictional examiner/candidate conversations, follow-up probes, and debriefs. They include a strong answer, an explicitly weak opening with correction, appropriate uncertainty, changing clinical facts, and a consent/safety boundary. They are assistant-authored illustrations with source links, **not outputs from the fine-tuned model** or a new benchmark. Only training-source references were used; the original datasets and result are unchanged. Clinical expert review has not been performed.

## What was run

- Apple M5 MacBook Pro, 16 GiB unified memory, sharing the machine with other work.
- `HuggingFaceTB/SmolLM2-135M-Instruct`, pinned revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`, Apache-2.0, nongated public download (~272 MB).
- MLX-LM 0.32.0 and MLX 0.32.3 from official PyPI, Python 3.12.13, dependency versions in `requirements.lock`.
- Six training sources (144 examples), two validation sources (16), four held-out sources (24 planned cases: 16 supported, 8 abstention/adversarial/malformed).
- Rank-8 LoRA on the last four layers; batch 1; assistant-only loss; 384-token sequence ceiling; 325,632 trainable parameters.
- The first 120-update attempt stopped at 59 updates because global swap-outs grew beyond the guard allowance, before saving a checkpoint. The same data/model was then used in one shorter 40-update run, saving every ten updates. The final 40-update adapter was used for evaluation; there was no test-driven checkpoint selection or scaling.
- The saved run took 23.7 seconds, peaked at 471.5 MiB MLX memory, and saved a 1,308,381-byte adapter. It showed no system swap-out increase during that run. Earlier/later global resource interruptions are retained in the aggregate report; overall zero swapping is not claimed.

The measured comparison is in [`runs/results.json`](runs/results.json). If evaluation was interrupted, its status and denominator are explicit, and comparisons use only the same completed cases from each condition. Validation loss decreased, but that is not evidence of better answers. Raw local outputs are independently checked by `src/report.py` without an external model judge.

The completed pilot is a negative fine-tuning result:

| Condition | Parseable JSON | Valid task schema | Exact answer + citation | Abstention cases correct |
| --- | ---: | ---: | ---: | ---: |
| Lexical extraction | 24/24 | 24/24 | 24/24 | 8/8 |
| Base + excerpts | 0/24 | 0/24 | 0/24 | 0/8 |
| Saved LoRA + excerpts | 2/24 | 0/24 | 0/24 | 0/8 |

The base model returned unstructured text; the expected ending occurred somewhere in 15 outputs, which does not satisfy the answer/citation contract. The adapter attempted JSON but 22 outputs did not parse, one used an invalid citation label, and one paired abstention with a citation inconsistently. None contained the expected target ending. This small adapter did not improve exact task success. The lower teacher-forced validation loss failed to predict usable greedy outputs. Prefer deterministic retrieval for this pilot; do not scale training based on these results alone.

Adapter evaluation initially stopped before generation, then stopped after nine cases on the machine-wide swap guard. The remaining fifteen cases were completed in a quiet resource window using the same immutable adapter/data/prompt/decoding fingerprint. No previous answer was retried. Reported evaluation durations distinguish active segments from the final resumed segment.

## Reproduce locally

Requires an Apple Silicon Mac and an authorized local copy of the oral-board reference database. Keep one model job running at a time. The example source database is read-only; the original repository is not modified.

```sh
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.lock
.venv/bin/python src/download_model.py
.venv/bin/python src/make_data.py --source-db /path/to/oral-boards/search.sqlite
.venv/bin/python src/checks.py
nice -n 10 .venv/bin/python src/bounded.py evaluate --condition retrieval
nice -n 10 .venv/bin/python src/bounded.py evaluate --condition base_rag
nice -n 10 .venv/bin/python src/bounded.py train
nice -n 10 .venv/bin/python src/bounded.py evaluate --condition adapter_rag
.venv/bin/python src/report.py
.venv/bin/python src/server.py --port 8765
```

Open `http://127.0.0.1:8765`. The demo starts with harmless synthetic text and can load a local study excerpt pair. It runs at most one inference at a time in a short-lived process, releases model memory afterward, logs no request/answer text, and binds only to loopback. It enforces host/origin checks and does not load external scripts or fonts. Use lexical extraction when model inference is resource-blocked.

`make_data.py` selects twelve active publisher references by local database IDs. For another database version, pass `--selection /path/to/local-selection.json` mapping `train`, `valid`, and `test` to nonoverlapping active IDs. Review the selected sources locally first. Corpus metadata and provenance stay in the ignored local manifest.

Frozen data and predictions refuse overwriting. For an evaluation interrupted by the resource guard, use `--resume` with `src/evaluate.py` or `src/bounded.py`; this continues only missing cases and checks the model/adapter/data/decoding fingerprint. It never gives an already-generated answer a second chance. Use a new experiment directory to change data, prompts, hyperparameters, or model weights.

Resuming an already-complete evaluation returns its saved summary without loading the model, checking Mac resource counters, or replacing its original timing. If all predictions were saved but the final summary was interrupted, resume reconstructs metrics with unknown timing/memory explicitly marked unavailable. A missing original fingerprint or a runtime prompt that differs from frozen messages is rejected before inference.

Hosted CI runs standard-library synthetic contract/resume tests, approved dataset byte/hash/privacy checks, and Python compilation. It never downloads a model, trains, reads the full source corpus, or uploads local runtime files. Run its checks locally with `python3 src/checks.py` and `PYTHONPATH=src python3 -m unittest discover -s tests -v`. The original local corpus integrity test is skipped on CI because that corpus is deliberately absent; the versioned approved snapshot is verified separately.

The observed initial stopped attempt is a historical artifact; a fresh reproduction normally performs the shorter saved run only. `report.py` reads the historical stopped summary if present and otherwise marks it absent. No training/evaluation data are required for the code's synthetic contract tests; local split checks run when data exist.

## What the evaluation means

The questions ask for the omitted ending of a source sentence. Each supported model prompt receives two candidate excerpts, including the target sentence. Retrieval uses the quoted sentence prefix to select and extract the exact ending; it does not read gold labels. Its very strong score is expected for this narrow task. Full-corpus retrieval recall, paraphrase reasoning, medical validity, and real exam performance are not measured.

Metrics include JSON/schema validity, exact answer plus citation, quote containment in the cited excerpt, citation existence, abstention correctness, and unsupported answers. Invalid output counts as failure; no JSON repair, prompt changes, or constrained decoding are applied. Abstaining on a supported question is also a task failure. No-context evaluation, when run, expects abstention for every question rather than treating missing evidence as memorized knowledge.

Source groups, exact normalized sentences, and positive question templates are disjoint across splits. Similar terminology or semantic overlap between documents can remain. The questions are generated mechanically from excerpts and form a small convenience sample, not an independent expert-curated examination. Exact completion is an objective but narrow factual proxy, and no clinician adjudicated reasoning or clinical appropriateness.

## Resource and privacy boundaries

The run checks macOS available-memory percentage, process RSS, `vm_stat` swap-outs, and `pmset` warning status every five seconds and between batches. It stops below 25% system free-memory percentage, above 1,200 MiB process RSS, on more than 64 MiB of new system-wide swap-outs, or on recorded thermal/performance warnings. MLX allocator/cache/wired thresholds are 1,024/64/384 MiB. These are allocator limits plus sampled stop conditions, not an OS hard memory guarantee. The outer wrapper adds a hard wall-clock deadline. Actual temperatures were not measured. A fast change can exceed a threshold between samples. Global swap changes cannot be attributed solely to this experiment.

Public publisher references are selected from the existing active corpus. Identifier-field forms are excluded. Selected references had no matches for MRN/patient-name/SSN/DOB patterns; this is a limited regex screen, not proof that all identifiers are absent. Tables, figure OCR, numeric statements, references, and apparent contact information are excluded from training snippets. No real patient records or private notes/email/code enter training.

The documents retain publisher copyright, and no open document license was verified. The user authorized local study use and subsequently the private `pilot-v1` dataset snapshot. No general redistribution permission or dataset license is inferred. Do not make the source-derived datasets public or redistribute/relicense them without a rights review and any required permission. Original documents, raw predictions, and weights remain local. Source freshness and clinical conflicts were not independently resolved. See [`docs/UPSTREAM.md`](docs/UPSTREAM.md) and the [dataset card](datasets/pilot-v1/DATASET_CARD.md).

Only `src/export_source.py`'s explicit allowlist is intended for GitHub: authored source/configuration, model provenance, aggregate metrics, the six approved files under `datasets/pilot-v1`, and the seven requested files under `examples/transcripts-v1`. Exact source sentences remain confined to the approved pilot snapshot. Source titles and public links are also allowed in the authored transcript bibliographies. The export checks the remaining files for accidental source content. Its archive includes the approved dataset snapshot and authored transcripts; the adapter remains on the Mac. Git ignores runtime training data, future unapproved dataset versions, raw predictions, downloaded weights, adapters, local screenshots, and model caches. Original dataset JSONL bytes/counts/hashes are frozen; use a separate version for any improved board-style QA dataset.
