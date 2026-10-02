"""Use Apple's trainer unchanged; wrap batch iteration to check resources and cool down."""
import hashlib
import json
import time
from types import SimpleNamespace
from runtime import ROOT, CFG
from resources import Guard, cap_mlx


def main():
    if (ROOT / "adapters/pilot/adapters.safetensors").exists():
        raise SystemExit("Existing adapter: use a new experiment directory instead of overwriting it")
    guard = Guard(CFG, ROOT / "runs/train-resources.jsonl", CFG["train_seconds"])
    started = time.perf_counter()
    import mlx.core as mx
    import mlx_lm.tuner.trainer as trainer
    from mlx_lm.lora import CONFIG_DEFAULTS, train_model
    from mlx_lm.tuner.datasets import load_dataset
    from mlx_lm.tuner.callbacks import TrainingCallback
    from runtime import load_local
    from mlx.utils import tree_flatten
    import numpy as np

    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    for split in ["train", "valid", "test"]:
        meta = manifest["splits"][split]
        assert hashlib.sha256((ROOT / "data" / meta["file"]).read_bytes()).hexdigest() == meta["sha256"]
    model, tokenizer = load_local()
    guard.check(force=True)
    settings = {**CONFIG_DEFAULTS, **{k: CFG[k] for k in ["seed", "iters", "batch_size", "num_layers", "max_seq_length", "learning_rate", "lora_parameters"]},
                "model": str(ROOT / CFG["model"]), "train": True, "data": str(ROOT / "data"),
                "mask_prompt": True, "steps_per_report": 10, "steps_per_eval": 60,
                "val_batches": 8, "save_every": 10, "adapter_path": str(ROOT / "adapters/pilot"),
                "trust_remote_code": False, "report_to": None}
    args = SimpleNamespace(**settings)
    np.random.seed(CFG["seed"])
    train_set, valid_set, test_set = load_dataset(args, tokenizer)
    assert len(test_set) == 0, "Held-out data must never be passed to the trainer"
    lengths = [len(train_set.process(train_set[i])[0]) for i in range(len(train_set))] + [len(valid_set.process(valid_set[i])[0]) for i in range(len(valid_set))]
    assert max(lengths) <= CFG["max_seq_length"], "Do not silently truncate targets"
    print(json.dumps({"max_sequence_tokens": max(lengths), "train_rows": len(train_set), "valid_rows": len(valid_set)}), flush=True)
    original_batches = trainer.iterate_batches
    def gentle_batches(*a, **kw):
        for batch in original_batches(*a, **kw):
            guard.check()
            cap_mlx(CFG)  # Apple's trainer can set its own wired limit at entry.
            time.sleep(CFG["cooldown_seconds_per_batch"])
            yield batch
    trainer.iterate_batches = gentle_batches
    # Default arguments bind early; supply our iterator through a train wrapper.
    import mlx_lm.lora as lora
    original_train = lora.train
    def gentle_train(**kwargs):
        return original_train(**kwargs, iterate_batches=gentle_batches)
    lora.train = gentle_train

    class LocalLog(TrainingCallback):
        def write(self, kind, info):
            with (ROOT / "runs/train-metrics.jsonl").open("a") as f:
                f.write(json.dumps({"kind": kind, **info}) + "\n")
            guard.check()
        def on_train_loss_report(self, info): self.write("train", info)
        def on_val_loss_report(self, info): self.write("validation", info)

    train_model(args, model, train_set, valid_set, LocalLog())
    guard.check(force=True)
    adapter = ROOT / "adapters/pilot/adapters.safetensors"
    report = {"status": "completed", "steps": CFG["iters"], "wall_seconds": time.perf_counter() - started,
              "mlx_peak_mib": mx.get_peak_memory() / 1024 ** 2, "max_sequence_tokens": max(lengths),
              "trainable_parameters": sum(v.size for _, v in tree_flatten(model.trainable_parameters())),
              "adapter_bytes": adapter.stat().st_size, "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest()}
    (ROOT / "runs/training-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
