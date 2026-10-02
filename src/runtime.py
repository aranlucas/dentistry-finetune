import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "configs/pilot.json").read_text())
# No model load may silently use remote credentials or send telemetry.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["MLX_METAL_MEMORY_LIMIT"] = str(CFG["wired_limit_mib"] * 1024 ** 2)


def load_local(adapter=False):
    import mlx.core as mx
    from mlx_lm import load
    from resources import cap_mlx
    cap_mlx(CFG)
    model, tokenizer = load(str(ROOT / CFG["model"]),
                            adapter_path=str(ROOT / "adapters/pilot") if adapter else None,
                            trust_remote_code=False)
    mx.eval(model.parameters())
    model.eval()
    return model, tokenizer


def infer(model, tokenizer, text):
    import mlx.core as mx
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler
    from task import messages
    mx.random.seed(CFG["seed"])
    prompt = tokenizer.apply_chat_template(messages(text), tokenize=False, add_generation_prompt=True)
    return generate(model, tokenizer, prompt=prompt, max_tokens=CFG["max_new_tokens"],
                    sampler=make_sampler(temp=0), verbose=False)
