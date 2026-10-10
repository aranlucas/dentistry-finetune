"""Fixed three-pass schedule with resumable optimizer state and unchanged guards."""
import argparse
import collections
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from qa import ROOT, SYSTEM, config, digest, load, local_directory, verify


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def prepare(source, destination):
    cfg, old = verify(source)
    if destination.exists(): raise ValueError("Existing long experiment is immutable")
    # Repartition only the old training pool. Previous validation source groups
    # become the new generation benchmark; previous test topics are excluded.
    training = [json.loads(l) for l in (source / "data/train.jsonl").read_text().splitlines()]
    previous_valid = [json.loads(l) for l in (source / "data/valid.jsonl").read_text().splitlines()]
    groups = sorted({r["source_group"] for r in training})
    random.Random(20261010).shuffle(groups)
    validation_groups = set(groups[:max(3, len(groups) // 10)])
    rows = {"train": [r for r in training if r["source_group"] not in validation_groups],
            "valid": [r for r in training if r["source_group"] in validation_groups], "test": []}
    pools = collections.defaultdict(list)
    for row in sorted(previous_valid, key=lambda r: r["id"]): pools[row["source_group"]].append(row)
    while len(rows["test"]) < 12 and any(pools.values()):
        for group in sorted(pools):
            if pools[group] and len(rows["test"]) < 12: rows["test"].append(pools[group].pop(0))
    cfg = {**cfg, "schedule": "qa-long-v1", "seed": 20261010, "epochs": 3,
           "segment_steps": 64, "checkpoint_every": 8,
           "total_steps": 3 * len(rows["train"])}
    destination.mkdir(parents=True); (destination / "data").mkdir(); (destination / "runs").mkdir()
    write_json(destination / "config.json", cfg)
    shutil.copy2(source / "model-provenance.json", destination / "model-provenance.json")
    model_path = (source / "models").resolve()
    if not model_path.is_relative_to((ROOT / ".local").resolve()): raise ValueError("Model must stay local")
    (destination / "models").symlink_to(model_path, target_is_directory=True)
    schedule = []
    for epoch in range(cfg["epochs"]):
        indices = list(range(len(rows["train"])))
        random.Random(cfg["seed"] + epoch).shuffle(indices)
        schedule.extend(indices)
    write_json(destination / "data/schedule.json", schedule)
    manifest = {"experiment": "qa-long-v1", "system": SYSTEM, "seed": cfg["seed"],
                "config_sha256": digest(destination / "config.json"),
                "model_provenance_sha256": digest(destination / "model-provenance.json"),
                "schedule_sha256": digest(destination / "data/schedule.json"),
                "parent_dataset": str(source.relative_to(ROOT)),
                "parent_manifest_sha256": digest(source / "data/manifest.json"),
                "source_db_sha256": old["source_db_sha256"],
                "source_groups": {k: sorted({r["source_group"] for r in v}) for k, v in rows.items()},
                "previous_heldout_topics_excluded": old["source_groups"]["test"],
                "unused_heldout_candidates": sum(len(v) for v in pools.values()),
                "evaluation_limit": "New generation questions from the previous pilot's validation sources; prior aggregate validation losses were observed. No prior held-out outputs or source groups are used here. This is not an independent clinical benchmark.",
                "rights": "Local study only; no dataset, output, or weight sharing authorized",
                "splits": {}}
    for split, examples in rows.items():
        path = destination / "data" / ("heldout.jsonl" if split == "test" else split + ".jsonl")
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in examples))
        manifest["splits"][split] = {"file": path.name, "count": len(examples), "sha256": digest(path)}
    write_json(destination / "data/manifest.json", manifest)
    write_json(destination / "STATUS.json", {"status": "prepared", "detail": f"Frozen three-pass schedule: {cfg['total_steps']} updates. Previous held-out topics excluded."})
    verify_long(destination)
    print(json.dumps({"run": str(destination), "total_steps": cfg["total_steps"],
                      "epochs": cfg["epochs"], "split_counts": {k: len(v) for k, v in rows.items()}}, indent=2))


def verify_long(run):
    cfg, manifest = verify(run)
    if cfg.get("schedule") != "qa-long-v1": raise ValueError("Wrong training schedule")
    path = run / "data/schedule.json"
    if digest(path) != manifest["schedule_sha256"]: raise ValueError("Frozen training order changed")
    schedule = json.loads(path.read_text()); n = manifest["splits"]["train"]["count"]
    if len(schedule) != cfg["total_steps"] or collections.Counter(schedule) != {i: cfg["epochs"] for i in range(n)}:
        raise ValueError("Schedule does not visit each training row once per epoch")
    if any(set(v) & set(manifest["previous_heldout_topics_excluded"]) for v in manifest["source_groups"].values()):
        raise ValueError("Previous held-out topics leaked into longer experiment")
    return cfg, manifest, schedule


def progress(run):
    pointer = run / "runs/progress.json"
    if not pointer.exists(): return None
    info = json.loads(pointer.read_text())
    checkpoint = run / info["directory"]
    if not checkpoint.resolve().is_relative_to((run / "runs/checkpoints").resolve()): raise ValueError("Invalid checkpoint path")
    saved = json.loads((checkpoint / "state.json").read_text())
    if saved["steps"] != info["steps"]: raise ValueError("Checkpoint step mismatch")
    for name, sha in saved["hashes"].items():
        if digest(checkpoint / name) != sha: raise ValueError("Checkpoint bytes changed")
    current_sha = digest(ROOT / "src/qa_long.py")
    if saved["implementation_sha256"] != current_sha:
        migration = json.loads((run / "IMPLEMENTATION_FIX.json").read_text())
        if (saved["implementation_sha256"] != "2820b2e2fe01968fcba574d749a283bd96bf3dcbeb09f6e5e244663d2a75d5df"
                or migration["from_sha256"] != saved["implementation_sha256"]
                or migration["to_sha256"] != current_sha
                or saved["steps"] > 64):
            raise ValueError("Long training implementation changed after checkpoint")
    manifest = json.loads((run / "data/manifest.json").read_text())
    if (saved["config_sha256"] != manifest["config_sha256"]
            or saved["schedule_sha256"] != manifest["schedule_sha256"]):
        raise ValueError("Checkpoint belongs to a different frozen recipe")
    return checkpoint, saved


def train_segment(run):
    if os.environ.get("DENTISTRY_BOUNDED_JOB") != "1": raise ValueError("Use src/bounded.py")
    cfg, manifest, schedule = verify_long(run)
    saved = progress(run)
    start = saved[1]["steps"] if saved else 0
    if start >= cfg["total_steps"]: return
    count = min(cfg["segment_steps"], cfg["total_steps"] - start)
    from resources import Guard, cap_mlx
    attempt = f"segment-{start:06d}-{time.time_ns()}"
    guard = Guard(cfg, run / f"runs/{attempt}-resources.jsonl", cfg["train_seconds"])
    started = time.perf_counter()
    import mlx.core as mx
    import numpy as np
    import mlx_lm.lora as lora
    import mlx_lm.tuner.trainer as trainer
    from mlx_lm.tuner.datasets import load_dataset
    from mlx_lm.tuner.callbacks import TrainingCallback
    from mlx.utils import tree_flatten, tree_unflatten
    model, tokenizer = load(run, cfg)
    guard.check(force=True)
    keys = ["seed", "batch_size", "num_layers", "max_seq_length", "learning_rate", "lora_parameters", "grad_checkpoint"]
    directory = run / "runs/segments" / attempt
    directory.mkdir(parents=True)
    settings = {**lora.CONFIG_DEFAULTS, **{k: cfg[k] for k in keys},
                "model": str(run / cfg["model"]), "train": True, "data": str(run / "data"),
                "iters": count, "mask_prompt": True, "steps_per_report": cfg["checkpoint_every"],
                "steps_per_eval": count + 1, "val_batches": 4, "save_every": count,
                "adapter_path": str(directory), "report_to": None,
                "resume_adapter_file": str(saved[0] / "adapter.safetensors") if saved else None}
    args = SimpleNamespace(**settings)
    train_set, valid_set, test_set = load_dataset(args, tokenizer)
    if len(test_set): raise ValueError("Held-out rows reached trainer")
    holder = {}
    def batches(dataset, batch_size, max_seq_length, loop=False, **kwargs):
        if batch_size != 1: raise ValueError("Long schedule is single-example only")
        indices = schedule[start:start + count] if loop else range(len(dataset))
        for index in indices:
            guard.check(); cap_mlx(cfg)
            tokens, offset = dataset[index]
            if len(tokens) > max_seq_length: raise ValueError("Target would be truncated")
            width = min(max_seq_length, 1 + 32 * ((len(tokens) + 31) // 32))
            padded = np.zeros((1, width), np.int32); padded[0, :len(tokens)] = tokens
            time.sleep(cfg["cooldown_seconds_per_batch"])
            yield mx.array(padded), mx.array([[offset, len(tokens)]])
    original_train = lora.train
    def continuing_train(**kw):
        optimizer = kw["optimizer"]; holder["optimizer"] = optimizer
        if saved:
            optimizer.state = tree_unflatten(list(mx.load(str(saved[0] / "optimizer.safetensors")).items()))
            if int(optimizer.step.item()) != start: raise ValueError("Adam step counter was not restored")
            random_state = mx.load(str(saved[0] / "random.safetensors"))
            if set(random_state) != {str(i) for i in range(len(mx.random.state))}:
                raise ValueError("Checkpoint random state has an incompatible shape")
            # MLX 0.32.3 exposes a read-only state container. Its contained
            # arrays remain mutable; update each key without replacing it.
            for i in range(len(mx.random.state)):
                mx.random.state[i][:] = random_state[str(i)]
                if not mx.array_equal(mx.random.state[i], random_state[str(i)]).item():
                    raise ValueError("Random key was not restored exactly")
        return original_train(**kw, iterate_batches=batches)
    lora.train = continuing_train
    def checkpoint(steps):
        destination = run / "runs/checkpoints" / f"{steps:07d}"
        if destination.exists(): raise ValueError("Refusing to overwrite a committed checkpoint")
        temporary = destination.with_name(destination.name + ".pending")
        temporary.mkdir(parents=True, exist_ok=True)
        optimizer = holder["optimizer"]
        mx.eval(model.trainable_parameters(), optimizer.state, mx.random.state)
        if int(optimizer.step.item()) != steps: raise ValueError("Adam step counter differs from scheduled position")
        mx.save_safetensors(str(temporary / "adapter.safetensors"), dict(tree_flatten(model.trainable_parameters())))
        mx.save_safetensors(str(temporary / "optimizer.safetensors"), dict(tree_flatten(optimizer.state)))
        mx.save_safetensors(str(temporary / "random.safetensors"), {str(i): v for i, v in enumerate(mx.random.state)})
        write_json(temporary / "state.json", {"steps": steps, "implementation_sha256": digest(ROOT / "src/qa_long.py"),
                   "config_sha256": manifest["config_sha256"], "schedule_sha256": manifest["schedule_sha256"],
                   "hashes": {name: digest(temporary / name) for name in ["adapter.safetensors", "optimizer.safetensors", "random.safetensors"]}})
        temporary.replace(destination)
        write_json(run / "runs/progress.json", {"steps": steps, "directory": str(destination.relative_to(run))})
    class Log(TrainingCallback):
        def on_train_loss_report(self, info):
            checkpoint(start + info["iteration"])
            with (run / "runs/train-metrics.jsonl").open("a") as f:
                f.write(json.dumps({"kind": "train", **info, "iteration": start + info["iteration"], "segment": attempt}) + "\n")
            guard.check()
        def on_val_loss_report(self, info):
            with (run / "runs/train-metrics.jsonl").open("a") as f:
                f.write(json.dumps({"kind": "validation", **info, "iteration": start + info["iteration"], "segment": attempt}) + "\n")
            guard.check()
    lora.train_model(args, model, train_set, valid_set, Log())
    guard.check(force=True)
    summary = {"start": start, "steps": count, "end": start + count,
               "wall_seconds": time.perf_counter() - started, "mlx_peak_mib": mx.get_peak_memory() / 1048576,
               "resource_log": f"runs/{attempt}-resources.jsonl", "segment": attempt}
    write_json(directory / "completed.json", summary)
    if start + count == cfg["total_steps"]:
        final = run / "adapters/qa"; final.mkdir(parents=True)
        final_state = progress(run)
        shutil.copy2(final_state[0] / "adapter.safetensors", final / "adapters.safetensors")
        shutil.copy2(directory / "adapter_config.json", final / "adapter_config.json")
        segments = [json.loads(p.read_text()) for p in (run / "runs/segments").glob("*/completed.json")]
        write_json(run / "runs/training-summary.json", {"status": "completed", "steps": cfg["total_steps"],
            "epochs": cfg["epochs"], "segments": len(segments), "train_rows": len(train_set), "valid_rows": len(valid_set),
            "wall_seconds": sum(s["wall_seconds"] for s in segments), "mlx_peak_mib": max(s["mlx_peak_mib"] for s in segments),
            "adapter_bytes": (final / "adapters.safetensors").stat().st_size,
            "adapter_sha256": digest(final / "adapters.safetensors"),
            "optimizer_state_preserved": True, "frozen_schedule_completed": True})
    print(json.dumps(summary), flush=True)


def run_schedule(run):
    cfg, _, _ = verify_long(run)
    while True:
        current = progress(run); completed = current[1]["steps"] if current else 0
        if completed == cfg["total_steps"]: break
        write_json(run / "STATUS.json", {"status": "training", "detail": f"Three-pass schedule: {completed}/{cfg['total_steps']} updates committed. Adam and dataset position preserved."})
        command = [sys.executable, str(ROOT / "src/bounded.py"), "train", "--experiment", "qa-long-v1", "--run-dir", str(run)]
        log = run / "runs" / f"job-{completed:06d}-{time.time_ns()}.log"
        with log.open("w") as output:
            result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, cwd=ROOT, timeout=105)
        current = progress(run); completed = current[1]["steps"] if current else 0
        print(json.dumps({"committed_steps": completed, "total_steps": cfg["total_steps"], "returncode": result.returncode, "log": str(log)}), flush=True)
        if result.returncode:
            write_json(run / "STATUS.json", {"status": "resource_blocked", "detail": f"Training stopped at committed update {completed}; optimizer and adapter checkpoint preserved. Inspect the local job log."})
            raise SystemExit(result.returncode)
        time.sleep(1)
    write_json(run / "STATUS.json", {"status": "trained", "detail": "All three passes completed. Final adapter evaluation pending."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "train", "run"])
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--from-run")
    args = parser.parse_args(); run = local_directory(args.run_dir)
    if args.operation == "prepare":
        if not args.from_run: parser.error("--from-run is required")
        prepare(local_directory(args.from_run), run)
    elif args.operation == "train": train_segment(run)
    else: run_schedule(run)
