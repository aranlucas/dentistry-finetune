# Local study experiment

- Keep training/evaluation local. Never call inference/embedding APIs or upload the raw source corpus.
- `data/`, `models/`, `adapters/`, `.hf-cache/`, `.local/`, and raw `runs/` outputs are local only.
- Export only authored code/configuration, model provenance, and approved aggregate metrics through `src/export_source.py`.
- The user explicitly authorized the versioned generated dataset snapshot under `datasets/pilot-v1/` in this private repository. Preserve its original JSONL bytes; future datasets need a separate version and sharing authorization. Do not export raw PDFs, full documents, weights, or unrelated data.
- The user also requested sample practice transcripts. The authored, fictional `examples/transcripts-v1/` files and their source bibliographies are approved deliverables. They are not model outputs or benchmark/training rows. Use training-source documents only; do not draw teaching samples from the original validation or held-out sources. Keep the pilot data/results immutable.
- Do not weaken memory/swap/thermal guards. Use one job at a time, low priority, and `src/bounded.py`.
- Do not train on real patient records. Select publisher references and exclude flagged identifier forms.
- Freeze source groups and questions before any model evaluation. Never tune against held-out output.
- The benchmark is short extractive note completion, not oral-board reasoning, diagnosis, or medical reliability.
- Verify with `.venv/bin/python src/checks.py`; inspect aggregate metrics and privacy-safe exports before pushing.

## Scripts: native first

Before adding a script file (`scripts/`, `bin/`, `tools/`, root `*.sh|*.py|*.mjs`) or a package script that runs one, take the first rung that works:

1. A flag or subcommand of a tool the repo already uses (`<tool> --help`).
2. Declarative config for that tool (`pyproject.toml`, `configs/pilot.json`, `web/vite.config.ts`, `web/oxfmt.config.ts`, `web/tsconfig.json`).
3. A maintained plugin for that tool.
4. A one-line Makefile target or web/package.json script that calls a native command.
5. A test in the existing runner (Python unittest and web Vitest), for anything that asserts.
6. A custom script, only for behavior specific to this repo. Its first comment names the native rung it couldn't use and why. It has a test in the existing runner, and the PR that adds it quotes that comment.

## Code: libraries first

Before hand-writing general-purpose code, use a well-maintained library: actively released, widely adopted, typed, and a fit for this stack. Reach for one already in the dependencies first. Write custom code for domain logic and for the glue no library covers. A PR that adds a dependency says why it was picked; a PR that hand-writes something a library covers names the library and why it didn't fit.

- Local model loading, inference, and LoRA training → mlx-lm with MLX.
- Process and memory measurements → psutil; keep the repository's resource guards around it.
- Website server state → TanStack Query (@tanstack/react-query) useQuery/useMutation.
