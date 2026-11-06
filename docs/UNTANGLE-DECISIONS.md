# Untangle decision log

## Scope and baseline (2026-11-05)

Skill fetched verbatim before inspection from https://raw.githubusercontent.com/caldoai/skills/main/skills/untangle-codebase/SKILL.md (142 lines); both Comments and Tests selected by the user. Bound branch: `refactor/untangle-codebase-20261106`. Initial worktree clean. No training, inference, dataset generation, uploads, publishing or changes to approved snapshot/results authorized or performed.

Inventory: all tracked Python and MJS source; six Python test modules and synthetic checks; React API/router/hooks/pages/components/styles and router tests; Makefile, package/Python/config files, CI, export boundaries, README/ROADMAP/provenance and transcript/dataset metadata. Approximately 6,246 lines of code/tests. Independent Python and frontend inventory reviewers examined hidden links, needless links, surplus and special cases. Recent history already pruned redundant documentation/tests; avoid repeating that work.

Baseline: Python 3.14.8 available, no `.venv` or Python 3.12 interpreter installed. `python src/checks.py`: 4 tests, one expected local-data skip, pass. `PYTHONPATH=src python -m unittest discover -s tests -v`: 19 tests, 3 failures, all HTTP origin acceptance tests requiring absent `web/dist/index.html` (503 versus 200). These are baseline fixture failures, not introduced failures. Web dependencies installed locally for checks; baseline checks recorded below before editing frontend.

## Design decisions before implementation

1. Put the pilot's template vocabulary and lexical extractor in `task.py`, the existing stable task contract.
   - Hidden link: `make_data.TEMPLATES` and `evaluate.retrieval_answer` independently list the same six prefixes.
   - Needless link: live `predict` and synthetic checks import evaluation orchestration just for lexical extraction.
   - Preserve exact strings, ordering, extraction semantics and snapshot bytes. No new general-purpose library is appropriate for this domain contract.
2. Give append-only judgment storage one focused module owning row reading, sequence/hash verification and append.
   - Hidden link: `answer_review`, `judge_review`, and server independently verify the same hash chain.
   - Needless link: answer review and curated dataset depend on the dataset-review CLI for storage primitives.
   - Preserve JSON hashing/serialization and existing records. Keep answer binding and semantic review with callers. Standard-library JSON/hashlib are the existing fit; no additional dependency.
3. Make API response contracts explicit for pending pilot results and selected development run.
   - Hidden link: server returns null rate/training/report when incomplete but web schemas reject them.
   - Hidden link: picker guesses selected run by label while Ask guesses first registry entry, although server defaults to curated. Return authoritative run id; consume it throughout the page.
4. Flatten CI checks to native sequential Actions steps.
   - Special case/surplus: unsupported `parallel` step wrapper prevents validation from running. Keep every check.
5. Remove only comments that restate the implementation; retain research/privacy/environment rationale.
6. Clean tests last: isolate real HTTP origin tests with synthetic index.html; retain meaningful privacy/export/resume/router/integrity coverage. Remove incidental fixture duplication only if verified redundant.
   - New tests will cover journal tampering/immutability (independently specified chain behavior), null pending API data and authoritative run selection. They must catch plausible regressions without mirroring implementation.

## Retained requirements / rejected churn

- `qa.py` implementation bytes and `qa_long.py` checkpoint code are fingerprinted by historical runs. Do not split these modules or rewrite fingerprints: saved runs must fail closed on changed recipes. Their existing broad responsibility is an acknowledged compatibility constraint.
- Independent report scoring is intentionally independent assurance, not duplicate task logic to merge.
- Resource guards, exclusive job locks, telemetry errors, low priority, cooldown sleeps, local directory checks, explicit model/tokenizer handling, historic checkpoint migration validation, source exclusions and strict duplicate-key parsing protect requirements and remain.
- Distinct development/grounded evaluation fingerprints and reference inputs warrant separate workflows; generic orchestration would hide these differences.
- Local outputs may be missing; never invent predictions/timings or regenerate held-out answers.
- Existing component colocation and TanStack Query server state are coherent. No broad directory/style rewrite or dependency additions justified.

## Implementation, validation and review

To be updated as changes and independent review rounds complete. Baseline failures are tracked above separately from introduced failures.

Completed all six decisions. Journal append now preflights duplicate IDs and verifies the existing chain before any writes; duplicate batches and corrupted journals leave prior bytes untouched. Restating frontend comments removed, while privacy/environment rationale remains. Test cleanup followed structural edits: origin tests use a synthetic app fixture, existing meaningful tests retained, and journal, run-selection and pending-response regression tests added.

Independent final review searched the current diff/repository for special cases, hidden links, needless links and surplus and found no further worthwhile structural changes. Its request for an independently fixed legacy journal fixture was implemented. Historical fingerprinted modules remain unchanged for the documented compatibility reason.

Validation: Python 3.12 environment created locally. Synthetic checks pass (4, one local-corpus skip); full unittest suite passed (23) before the final legacy fixture; the final 24-test run has no retained result and must be verified in CI. Web lint passes with native `--threads=1`, formatting passes, Vitest passes (26), TypeScript and production build pass. Initial multiworker Tailwind lint timed out under shared machine load; retry used one worker without changing rules or timeouts. New API-test lint errors were fixed, not suppressed. Export screening passes; approved dataset, aggregate results, resource guards and fingerprinted Q&A source have no diff. No model inference/training was performed on this Linux host; Mac-only model execution remains untested.

Latest user constraint: all further tests/builds run only in CI. No owned local test process remained at the transition. CI retains behavioral Python/Vitest checks and export screening through the export regression test. Merge is authorized only after required checks/reviews pass.
