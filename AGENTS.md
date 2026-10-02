# Local study experiment

- Keep training/evaluation local. Never call inference/embedding APIs or upload corpus text.
- `data/`, `models/`, `adapters/`, `.hf-cache/`, `.local/`, and raw `runs/` outputs are local only.
- Export only authored code/configuration, model provenance, and approved aggregate metrics through `src/export_source.py`.
- Do not weaken memory/swap/thermal guards. Use one job at a time, low priority, and `src/bounded.py`.
- Do not train on real patient records. Select publisher references and exclude flagged identifier forms.
- Freeze source groups and questions before any model evaluation. Never tune against held-out output.
- The benchmark is short extractive note completion, not oral-board reasoning, diagnosis, or medical reliability.
- Verify with `.venv/bin/python src/checks.py`; inspect aggregate metrics and privacy-safe exports before pushing.
