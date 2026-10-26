# Oral-board study lab roadmap

Updated 2026-10-26. Proposed local research and study-tool improvements, after
Digits/MCP priorities. This document contains authored planning only; no source
corpus, model output, new dataset or model weights are published with it.

## Starting point

Baseline `929a388d77e4ddae316093629d4e5a21bbb21f37`: the [lab](README.md)
already shows frozen experiments, local answers and review journals. The
sentence-completion pilot was a negative result: its deterministic baseline
outperformed the tested model conditions on that narrow task. Other development
comparisons do not establish clinical reliability or independent generalization.

## Ordered releases

1. **Make an experiment's decision easy to inspect.** Add a concise local
   decision view: question asked, input condition, frozen comparison, observed
   failure categories and whether the evidence supports continuing. Acceptance:
   every conclusion links to actual saved cases/aggregate results; missing
   predictions remain missing; development and held-out evidence are clearly
   separated. Do not launch more training just to populate the view.
2. **Compare a useful reference-reading workflow.** Define a small, separately
   frozen study task with supported and insufficient-evidence questions, then
   compare deterministic retrieval, the base model and an eligible adapter under
   the same evidence conditions. Acceptance: choose questions and evaluation
   criteria before outputs; retain negative results; no tuning against held-out
   answers. This is a future experiment, not evidence that the adapter helps.
3. **Support an accountable human review queue.** Extend the existing journals
   with an explicit reviewer identity/role, disagreement and unresolved status
   for each selected answer. Acceptance: assistant review cannot be mislabeled
   clinician review; corrections create a new record; source and prediction
   versions remain linked. Reviewer availability is a prerequisite, not assumed.
4. **Use reviewed material in a bounded study session.** Prototype local
   question, evidence reveal and self-explanation using only deliberately
   selected material. Acceptance: uncertainty and source context remain visible;
   results are not described as clinical advice; exporting any new source-derived
   content requires its own authorization and rights review.

## First slice and evaluation

Start with the decision view over existing saved results. Ask whether a reader
can correctly identify the negative pilot result, the limits of the comparison
and one justified next experiment. Measure comprehension and review time before
spending more compute. More training steps and lower loss are not product value.

Preserve frozen pilot bytes and all existing memory, swap, thermal and job
limits. Training/inference remain local and sequential. Reuse the current
Python/Vitest checks and explicit export allowlist; this roadmap does not expand
the approved dataset or authorize corpus uploads or clinical deployment.
