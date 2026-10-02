"""Only public downloads; never authentication, remote code, upload, or inference APIs."""
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cfg = json.loads((root / "configs/pilot.json").read_text())
os.environ["HF_HOME"] = str(root / ".hf-cache")
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import snapshot_download

if __name__ == "__main__":
    print(snapshot_download(cfg["upstream"], revision=cfg["revision"], local_dir=root / cfg["model"],
                            allow_patterns=["*.json", "*.safetensors", "*.model", "README.md", "LICENSE", "NOTICE"],
                            token=False, max_workers=1))
