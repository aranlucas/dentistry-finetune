"""Fresh training attempt with immutable Q&A data and previously saved base answers."""
import argparse
import json
import shutil
from pathlib import Path
from qa import ROOT, comparison_data, digest, local_directory, verify


def fork(source, destination):
    verify(source)
    comparison_data(source)
    if destination.exists():
        raise ValueError("Retry destination already exists; preserve prior attempts")
    fingerprint = source / "runs/base-fingerprint.json"
    if fingerprint.exists() and json.loads(fingerprint.read_text())["implementation_sha256"] != digest(ROOT / "src/qa.py"):
        raise ValueError("Q&A implementation changed; use a new experiment version")
    destination.mkdir(parents=True)
    (destination / "runs").mkdir()
    for name in ["config.json", "model-provenance.json"]:
        shutil.copy2(source / name, destination / name)
    shutil.copytree(source / "data", destination / "data")
    model_directory = (source / "models").resolve()
    if not model_directory.is_relative_to((ROOT / ".local").resolve()):
        raise ValueError("Model directory must stay local")
    (destination / "models").symlink_to(model_directory, target_is_directory=True)
    copied = []
    for path in (source / "runs").glob("base-*"):
        if path.is_file():
            shutil.copy2(path, destination / "runs" / path.name)
            copied.append(path.name)
    (destination / "REPLAY.json").write_text(json.dumps({
        "frozen_dataset_from": str(source.relative_to(ROOT)), "unchanged_configuration": True,
        "base_files_reused_without_new_generations": copied,
        "prior_attempt_preserved": True, "adapter_checkpoint_selected": False,
        "reason": "Fresh training attempt after resource stop; no held-out-driven tuning"
    }, indent=2) + "\n")
    (destination / "STATUS.json").write_text(json.dumps({
        "status": "prepared", "detail": "Fresh training attempt prepared with identical frozen data and configuration. Prior base answers retained."
    }, indent=2) + "\n")
    verify(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-run", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    print(fork(local_directory(args.from_run), local_directory(args.run_dir)))
