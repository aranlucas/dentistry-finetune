# Upstream software and model

- [MLX-LM](https://github.com/ml-explore/mlx-lm), Apple ML Explore, MIT. Installed from official PyPI as `mlx-lm==0.32.0`.
- [MLX](https://github.com/ml-explore/mlx), Apple ML Explore, MIT. Installed from official PyPI as `mlx==0.32.3` with its matching Metal wheel.
- [SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct), HuggingFaceTB, Apache-2.0 according to the publisher model card. Revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`; public and nongated at download time. File sizes and SHA-256 values are in `model-provenance.json`.
- [Official MLX-LM LoRA guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md). This project calls the installed trainer and wraps its batch iterator for resource checks and cooldowns. It does not vendor the trainer.

The repository's MIT license covers authored code only. It does not license upstream model weights, adapters derived from the study corpus, source documents, or derived datasets. Model weights are not included in Git. The source documents are publisher reference materials; no open redistribution/training license was verified. Local study use was requested by the user, followed by an explicit request to include the original generated datasets and provenance in this private repository. That approved snapshot is under `datasets/pilot-v1/`. The instruction does not establish third-party rights or general redistribution permission. Original source documents, raw predictions, and adapters remain local. Do not make source-derived datasets public or redistribute/relicense them without a rights review and any required permission.

The local reference database's active-document selection applies its existing reviewed replacement policy. Publication years and extracted revision dates differ, and no claim is made that every source is the latest worldwide. This pilot does not resolve clinical conflicts or assess patient-care suitability.
