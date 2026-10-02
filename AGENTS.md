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
