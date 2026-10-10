"""Versioned local Q&A experiment; never modifies the frozen cloze pilot."""
import argparse
import collections
import hashlib
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = (
    "You are a pediatric dentistry study assistant. Answer the study question directly "
    "and concisely. Preserve relevant conditions, exceptions, and uncertainty. "
    "Do not invent facts or citations. If you do not know, say so. "
    "This is educational study, not care for a real patient."
)
PII = {
    "patient_identifier": r"(?i)\b(?:MRN|patient\s+(?:ID|name)|medical\s+record\s+(?:number|#))\s*[:#]\s*\S+",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "dob": r"(?i)\b(?:date of birth|DOB)\s*[:=]\s*\d",
}
GUARD_KEYS = ["train_seconds", "memory_limit_mib", "cache_limit_mib", "wired_limit_mib",
              "minimum_system_free_percent", "max_system_swapout_growth_mib",
              "max_process_rss_mib", "cooldown_seconds_per_batch"]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def local_directory(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to((ROOT / ".local").resolve()):
        raise ValueError("Q&A experiment must stay within .local")
    return path


def config(run):
    cfg = json.loads((run / "config.json").read_text())
    original = json.loads((ROOT / "configs/pilot.json").read_text())
    if any(cfg[k] != original[k] for k in GUARD_KEYS):
        raise ValueError("Q&A resource guards must equal the original pilot")
    if cfg["experiment"] != "qa-v1":
        raise ValueError("Unknown Q&A task version")
    return cfg


def offline():
    os.environ.update(HF_HUB_OFFLINE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
                      HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")


def messages(question):
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]


class StudyTokenizer:
    """Apply the same explicit non-thinking template during training and inference."""
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __getattr__(self, name):
        return getattr(self.tokenizer, name)

    def apply_chat_template(self, *args, **kwargs):
        kwargs["enable_thinking"] = False
        return self.tokenizer.apply_chat_template(*args, **kwargs)


def read_cards(source):
    # Use the source project's real Markdown/YAML parsers. No app, build,
    # search, embeddings, environment files, or browser progress is accessed.
    script = r'''
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root = process.argv[2];
const {parseFlashcardMarkdown} = await import(pathToFileURL(path.join(root,'lib/flashcard-markdown.ts')));
const {parseMarkdownFrontmatter} = await import(pathToFileURL(path.join(root,'lib/markdown-frontmatter.ts')));
const output=[];
for (const name of fs.readdirSync(path.join(root,'content/aapd-notes')).sort()) {
 if (!name.endsWith('.mdx')) continue;
 const notePath=path.join('content/aapd-notes',name);
 const noteText=fs.readFileSync(path.join(root,notePath),'utf8');
 const note=parseMarkdownFrontmatter(noteText,'Missing note frontmatter');
 for (const id of note.data.flashcards ?? []) {
  if (!/^aapd-notes\/[a-z0-9_-]+$/.test(id)) throw new Error('Unexpected deck path');
  const deckPath='content/flashcards/'+id+'.mdx';
  const deckText=fs.readFileSync(path.join(root,deckPath),'utf8');
  const deck=parseFlashcardMarkdown(deckText);
  if (deck.metadata.source !== '/notes/'+name.slice(0,-4)) throw new Error('Deck source mismatch');
  output.push({slug:name.slice(0,-4),notePath,deckPath,noteText,deckText,
    metadata:note.data,cards:deck.cards});
 }
}
process.stdout.write(JSON.stringify(output));
'''
    result = subprocess.run(["node", "--input-type=module", "-", str(source)],
                            input=script, text=True, capture_output=True, check=True,
                            cwd=source, timeout=30)
    return json.loads(result.stdout)


def download(run, cfg):
    os.environ.update(HF_HOME=str(run / ".hf-cache"), HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
                      HF_HUB_DISABLE_TELEMETRY="1", HF_HUB_DISABLE_XET="1")
    os.environ.pop("HF_HUB_OFFLINE", None)
    from huggingface_hub import snapshot_download, hf_hub_download
    destination = run / cfg["model"]
    snapshot_download(cfg["upstream"], revision=cfg["revision"], local_dir=destination,
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "README.md", "LICENSE"],
                      token=False, max_workers=1)
    license_path = hf_hub_download(cfg["base_upstream"], "LICENSE", revision=cfg["base_revision"],
                                   token=False, cache_dir=run / ".hf-cache")
    (destination / "UPSTREAM_LICENSE").write_bytes(Path(license_path).read_bytes())
    provenance = {"repository": cfg["upstream"], "revision": cfg["revision"],
                  "original_repository": cfg["base_upstream"], "original_revision": cfg["base_revision"],
                  "quantization": "community MLX 4-bit conversion; original full-precision equivalence not independently established",
                  "files": {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
                            for p in destination.iterdir() if p.is_file()}}
    (run / "model-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


def prepare(run, source):
    if run.exists():
        raise ValueError("Existing experiment: never overwrite a frozen Q&A dataset")
    run.mkdir(parents=True)
    (run / "runs").mkdir()
    (run / "config.json").write_bytes((ROOT / "configs/qa-v1.json").read_bytes())
    cfg = config(run)
    download(run, cfg)
    offline()
    from transformers import AutoTokenizer
    tokenizer = StudyTokenizer(AutoTokenizer.from_pretrained(run / cfg["model"], local_files_only=True,
                                                              trust_remote_code=False))
    decks = read_cards(source)
    database = source / "search.sqlite"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        docs = connection.execute("SELECT d.title,d.hash,c.doc FROM documents d JOIN content c ON d.hash=c.hash WHERE d.active=1 AND d.collection='aapd'").fetchall()
    by_url = {}
    for title, content_hash, body in docs:
        url = re.search(r"^Source: <([^>]+)>", body, re.M)
        pdf = re.search(r"^PDF SHA-256: `([a-f0-9]{64})`", body, re.M)
        if url and pdf and url[1].startswith("https://www.aapd.org/"):
            by_url[url[1]] = {"title": title, "content_hash": content_hash,
                              "pdf_sha256": pdf[1], "flagged": any(re.search(p, body) for p in PII.values())}
    exclusions = collections.Counter()
    candidates = []
    for deck in decks:
        url = deck["metadata"].get("pdf_url", "")
        doc = by_url.get(url)
        if deck["slug"] in cfg["source_exclusions"]:
            exclusions["original_validation_or_heldout_topic"] += len(deck["cards"]); continue
        if not doc:
            exclusions["no_matching_active_publisher_pdf"] += len(deck["cards"]); continue
        if doc["flagged"] or any(re.search(p, deck["noteText"] + deck["deckText"]) for p in PII.values()):
            exclusions["identifier_form_flag"] += len(deck["cards"]); continue
        for card in deck["cards"]:
            chat = messages(card["front"]) + [{"role": "assistant", "content": card["back"]}]
            tokens = tokenizer.apply_chat_template(chat, tokenize=True, return_dict=False)
            if len(tokens) > cfg["max_seq_length"]:
                exclusions["sequence_over_budget_no_truncation"] += 1; continue
            if "```" in card["back"] or re.search(r"<[A-Z][A-Za-z]+", card["back"]):
                exclusions["diagram_or_component"] += 1; continue
            candidates.append({"id": "qa-" + hashlib.sha256((deck["deckPath"] + "\n" + card["front"]).encode()).hexdigest()[:16],
                               "question": card["front"], "answer": card["back"], "messages": chat,
                               "source_slug": deck["slug"], "source_title": deck["metadata"]["title"],
                               "publisher_url": url, "source_revision": deck["metadata"].get("source_revision"),
                               "pdf_sha256": doc["pdf_sha256"], "publisher_content_hash": doc["content_hash"],
                               "note_path": deck["notePath"], "deck_path": deck["deckPath"],
                               "note_sha256": hashlib.sha256(deck["noteText"].encode()).hexdigest(),
                               "deck_sha256": hashlib.sha256(deck["deckText"].encode()).hexdigest(),
                               "sequence_tokens": len(tokens)})
    # Same publisher PDF, normalized duplicate Q&A, and explicit answer links
    # share a component. Notes/decks are never split by individual row.
    parent = {c["source_slug"]: c["source_slug"] for c in candidates}
    def find(s):
        while s != parent[s]:
            parent[s] = parent[parent[s]]; s = parent[s]
        return s
    def union(a, b):
        a, b = find(a), find(b)
        if a != b: parent[max(a, b)] = min(a, b)
    seen = {}
    for row in candidates:
        keys = ["pdf:" + row["pdf_sha256"], "pair:" + re.sub(r"\W+", " ", row["question"] + " " + row["answer"]).lower()]
        for key in keys:
            if key in seen: union(row["source_slug"], seen[key])
            seen[key] = row["source_slug"]
        for linked in re.findall(r"\]\(/notes/([a-z0-9_-]+)(?:#[^)]*)?\)", row["answer"]):
            if linked in parent: union(row["source_slug"], linked)
    groups = collections.defaultdict(list)
    for row in candidates:
        row["source_group"] = find(row["source_slug"])
        groups[row["source_group"]].append(row)
    group_ids = sorted(groups)
    random.Random(cfg["seed"]).shuffle(group_ids)
    if len(group_ids) < 10: raise ValueError("Insufficient independent source groups")
    test_groups = set(group_ids[:max(3, len(group_ids) // 10)])
    valid_groups = set(group_ids[len(test_groups):len(test_groups) + max(3, len(group_ids) // 10)])
    rows = {"train": [], "valid": [], "test": []}
    for row in candidates:
        split = "test" if row["source_group"] in test_groups else "valid" if row["source_group"] in valid_groups else "train"
        rows[split].append(row)
    # A deterministic, source-diverse subset of held-out questions is frozen
    # now, before either model is evaluated. The rest are not evaluated.
    pools = {g: sorted(groups[g], key=lambda r: r["id"]) for g in sorted(test_groups)}
    selected = []
    while len(selected) < cfg["evaluation_cases"] and any(pools.values()):
        for g in sorted(pools):
            if pools[g] and len(selected) < cfg["evaluation_cases"]: selected.append(pools[g].pop(0))
    rows["test"] = selected
    data = run / "data"; data.mkdir()
    manifest = {"experiment": "qa-v1", "system": SYSTEM, "config_sha256": digest(run / "config.json"),
                "source_db_sha256": digest(database), "model_provenance_sha256": digest(run / "model-provenance.json"),
                "seed": cfg["seed"], "candidate_pairs": len(candidates), "exclusions": dict(exclusions),
                "source_groups": {k: sorted({r["source_group"] for r in v}) for k, v in rows.items()},
                "unused_heldout_candidates": sum(len(v) for v in pools.values()),
                "rights": "Local study only; source-linked authored answers; no sharing approval or clinical accuracy certification",
                "split_limit": "Groups cover primary PDFs, exact normalized duplicate pairs, and explicit answer links; implicit clinical overlap may remain",
                "evaluation_limit": "Unseen-source Q&A; does not measure recall of facts explicitly learned in training; clinical grading requires human review",
                "splits": {}}
    for split, examples in rows.items():
        random.Random(cfg["seed"]).shuffle(examples)
        path = data / ("heldout.jsonl" if split == "test" else split + ".jsonl")
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in examples))
        manifest["splits"][split] = {"file": path.name, "count": len(examples), "sha256": digest(path)}
    (data / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (run / "STATUS.json").write_text(json.dumps({"status": "prepared", "detail": "Frozen local Q&A dataset; models not evaluated."}))
    print(json.dumps({"run": str(run), "split_counts": {s: len(v) for s, v in rows.items()},
                      "source_groups": {s: len(manifest['source_groups'][s]) for s in rows}, "exclusions": dict(exclusions)}, indent=2))


def verify(run):
    cfg = config(run)
    manifest = json.loads((run / "data/manifest.json").read_text())
    if manifest["config_sha256"] != digest(run / "config.json") or manifest["system"] != SYSTEM:
        raise ValueError("Frozen configuration or task prompt changed")
    if manifest["model_provenance_sha256"] != digest(run / "model-provenance.json"):
        raise ValueError("Frozen model provenance changed")
    provenance = json.loads((run / "model-provenance.json").read_text())
    for name, info in provenance["files"].items():
        if digest(run / cfg["model"] / name) != info["sha256"]:
            raise ValueError("Pinned local model bytes changed")
    for meta in manifest["splits"].values():
        if digest(run / "data" / meta["file"]) != meta["sha256"]:
            raise ValueError("Frozen Q&A rows changed")
    groups = [set(v) for v in manifest["source_groups"].values()]
    if any(a & b for i, a in enumerate(groups) for b in groups[i + 1:]):
        raise ValueError("Q&A source groups overlap")
    return cfg, manifest


def load(run, cfg, adapter=False):
    offline()
    os.environ["MLX_METAL_MEMORY_LIMIT"] = str(cfg["wired_limit_mib"] * 1024 ** 2)
    from resources import cap_mlx
    cap_mlx(cfg)
    import mlx.core as mx
    from mlx_lm import load as mlx_load
    model, tokenizer = mlx_load(str(run / cfg["model"]),
                                adapter_path=str(run / "adapters/qa") if adapter else None,
                                trust_remote_code=False)
    mx.eval(model.parameters()); model.eval()
    return model, StudyTokenizer(tokenizer)


def train(run):
    if os.environ.get("DENTISTRY_BOUNDED_JOB") != "1":
        raise ValueError("Run training through src/bounded.py")
    cfg, _ = verify(run)
    if (run / "adapters").exists():
        raise ValueError("Training already attempted here; preserve it and use a new run directory")
    from resources import Guard, cap_mlx
    guard = Guard(cfg, run / "runs/train-resources.jsonl", cfg["train_seconds"])
    started = time.perf_counter()
    import mlx.core as mx
    import mlx_lm.tuner.trainer as trainer
    from mlx_lm.lora import CONFIG_DEFAULTS, train_model
    from mlx_lm.tuner.datasets import load_dataset
    from mlx_lm.tuner.callbacks import TrainingCallback
    from mlx.utils import tree_flatten
    import numpy as np
    model, tokenizer = load(run, cfg)
    guard.check(force=True)
    keys = ["seed", "iters", "batch_size", "num_layers", "max_seq_length", "learning_rate", "lora_parameters", "grad_checkpoint"]
    args = SimpleNamespace(**{**CONFIG_DEFAULTS, **{k: cfg[k] for k in keys},
                              "model": str(run / cfg["model"]), "train": True, "data": str(run / "data"),
                              "mask_prompt": True, "steps_per_report": 8, "steps_per_eval": cfg["iters"] + 1,
                              "val_batches": 4, "save_every": 16,
                              "adapter_path": str(run / "adapters/qa"), "trust_remote_code": False, "report_to": None})
    np.random.seed(cfg["seed"])
    train_set, valid_set, test_set = load_dataset(args, tokenizer)
    if len(test_set): raise ValueError("Held-out rows reached trainer")
    lengths = [len(ds.process(ds[i])[0]) for ds in [train_set, valid_set] for i in range(len(ds))]
    if max(lengths) > cfg["max_seq_length"]: raise ValueError("Targets would be truncated")
    original_batches = trainer.iterate_batches
    def gentle_batches(*a, **kw):
        for batch in original_batches(*a, **kw):
            guard.check(); cap_mlx(cfg)
            time.sleep(cfg["cooldown_seconds_per_batch"])
            yield batch
    import mlx_lm.lora as lora
    original_train = lora.train
    def gentle_train(**kw):
        return original_train(**kw, iterate_batches=gentle_batches)
    lora.train = gentle_train
    class Log(TrainingCallback):
        def write(self, kind, info):
            with (run / "runs/train-metrics.jsonl").open("a") as f: f.write(json.dumps({"kind": kind, **info}) + "\n")
            guard.check()
        def on_train_loss_report(self, info): self.write("train", info)
        def on_val_loss_report(self, info): self.write("validation", info)
    train_model(args, model, train_set, valid_set, Log())
    guard.check(force=True)
    adapter = run / "adapters/qa/adapters.safetensors"
    report = {"status": "completed", "steps": cfg["iters"], "wall_seconds": time.perf_counter() - started,
              "mlx_peak_mib": mx.get_peak_memory() / 1024 ** 2, "adapter_bytes": adapter.stat().st_size,
              "adapter_sha256": digest(adapter), "max_sequence_tokens": max(lengths),
              "train_rows": len(train_set), "valid_rows": len(valid_set),
              "trainable_parameters": sum(v.size for _, v in tree_flatten(model.trainable_parameters()))}
    (run / "runs/training-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


def diagnostic(raw, reference):
    # Text overlap is descriptive, never a clinical correctness score.
    words = lambda t: re.findall(r"\b\w+\b", t.lower())
    a, b = collections.Counter(words(raw)), collections.Counter(words(reference))
    shared = sum((a & b).values())
    precision = shared / sum(a.values()) if a else 0
    recall = shared / sum(b.values()) if b else 0
    tokens = words(raw)
    grams = collections.Counter(tuple(tokens[i:i + 4]) for i in range(max(0, len(tokens) - 3)))
    return {"reference_word_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
            "repeated_fourgram": max(grams.values(), default=0) >= 3,
            "empty": not raw.strip(), "clinical_review": "pending"}


def generate_response(model, tokenizer, cfg, question, seed, guard):
    import mlx.core as mx
    from resources import cap_mlx
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import make_sampler
    mx.random.seed(seed)
    prompt = tokenizer.apply_chat_template(messages(question), tokenize=False, add_generation_prompt=True)
    if len(tokenizer.encode(prompt)) > cfg["max_seq_length"]:
        raise ValueError("Question exceeds local token budget")
    started = time.perf_counter(); parts = []; last = None
    for output in stream_generate(model, tokenizer.tokenizer, prompt=prompt, max_tokens=cfg["max_new_tokens"],
                                  sampler=make_sampler(temp=cfg["temperature"], top_p=cfg["top_p"], top_k=cfg["top_k"])):
        parts.append(output.text); last = output; guard.check(); cap_mlx(cfg)
    return {"raw": "".join(parts), "seed": seed, "seconds": time.perf_counter() - started,
            "generation_tokens": last.generation_tokens if last else 0,
            "finish_reason": last.finish_reason if last else None}


def predict(run):
    """Ephemeral local question; never saved as training or evaluation data."""
    if os.environ.get("DENTISTRY_BOUNDED_JOB") != "1":
        raise ValueError("Run inference through src/bounded.py")
    request = json.loads(sys.stdin.read(4096))
    if not isinstance(request, dict) or set(request) != {"question", "condition"}:
        raise ValueError("Expected a question and model condition")
    question, condition = request["question"], request["condition"]
    if not isinstance(question, str) or not question.strip() or len(question) > 500 or condition not in ["base", "adapter"]:
        raise ValueError("Invalid local study request")
    if any(re.search(p, question) for p in PII.values()):
        raise ValueError("Identifier-form questions are excluded")
    cfg, _ = verify(run)
    if condition == "adapter" and not (run / "runs/training-summary.json").exists():
        raise ValueError("Completed adapter unavailable")
    from resources import Guard
    guard = Guard(cfg, run / "runs/demo-resources.jsonl", 45)
    model, tokenizer = load(run, cfg, condition == "adapter")
    guard.check(force=True)
    response = generate_response(model, tokenizer, cfg, question, cfg["seed"], guard)
    guard.check(force=True)
    print(json.dumps({"condition": condition, "clinical_review": "pending", **response}))


def evaluate(run, condition, resume=False):
    if os.environ.get("DENTISTRY_BOUNDED_JOB") != "1":
        raise ValueError("Run evaluation through src/bounded.py")
    cfg, manifest = verify(run)
    if condition == "adapter" and not (run / "runs/training-summary.json").exists():
        raise ValueError("Only a fully completed training run may be evaluated")
    path = run / f"runs/{condition}-predictions.jsonl"
    fingerprint_path = run / f"runs/{condition}-fingerprint.json"
    fingerprint = {"condition": condition, "config_sha256": manifest["config_sha256"],
                   "implementation_sha256": digest(ROOT / "src/qa.py"),
                   "test_sha256": manifest["splits"]["test"]["sha256"],
                   "model_provenance_sha256": manifest["model_provenance_sha256"],
                   "adapter_sha256": digest(run / "adapters/qa/adapters.safetensors") if condition == "adapter" else None,
                   "reference_excerpts": False, "repair": False}
    if path.exists() and not resume: raise ValueError("Refusing to overwrite predictions; resume only missing rows")
    if fingerprint_path.exists():
        if json.loads(fingerprint_path.read_text()) != fingerprint: raise ValueError("Evaluation fingerprint changed")
    elif path.exists(): raise ValueError("Predictions lack an immutable fingerprint")
    else: fingerprint_path.write_text(json.dumps(fingerprint, indent=2) + "\n")
    examples = [json.loads(l) for l in (run / "data/heldout.jsonl").read_text().splitlines()]
    records = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    if [r["id"] for r in records] != [r["id"] for r in examples[:len(records)]]: raise ValueError("Saved predictions are not an exact prefix")
    if len(records) == len(examples): return
    from resources import Guard
    guard = Guard(cfg, run / f"runs/{condition}-resources.jsonl", 300)
    started = time.perf_counter()
    model, tokenizer = load(run, cfg, condition == "adapter")
    guard.check(force=True)
    import mlx.core as mx
    for example in examples[len(records):]:
        guard.check(force=True)
        seed = (cfg["seed"] + int(hashlib.sha256(example["id"].encode()).hexdigest()[:8], 16)) % (2 ** 32)
        response = generate_response(model, tokenizer, cfg, example["question"], seed, guard)
        record = {"id": example["id"], **response, **diagnostic(response["raw"], example["answer"])}
        with path.open("a") as f: f.write(json.dumps(record) + "\n")
        print(json.dumps({"condition": condition, "completed": len(records) + 1, "finish_reason": record["finish_reason"]}), flush=True)
        records.append(record); time.sleep(cfg["cooldown_seconds_per_batch"])
    guard.check(force=True)
    (run / f"runs/{condition}-summary.json").write_text(json.dumps({"status": "complete", "n": len(records),
        "wall_seconds": time.perf_counter() - started, "mlx_peak_mib": mx.get_peak_memory() / 1024 ** 2}, indent=2) + "\n")


def comparison_data(run):
    """Read local results without loading a model or returning training rows."""
    cfg = config(run)
    manifest = json.loads((run / "data/manifest.json").read_text())
    if digest(run / "config.json") != manifest["config_sha256"] or manifest["system"] != SYSTEM:
        raise ValueError("Frozen Q&A task changed")
    meta = manifest["splits"]["test"]
    path = run / "data" / meta["file"]
    if digest(path) != meta["sha256"]: raise ValueError("Frozen questions changed")
    examples = [json.loads(l) for l in path.read_text().splitlines()]
    outputs = {}
    for condition in ["base", "adapter"]:
        path = run / f"runs/{condition}-predictions.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
        if [r["id"] for r in rows] != [e["id"] for e in examples[:len(rows)]]:
            raise ValueError("Q&A prediction order changed")
        if rows:
            fingerprint = json.loads((run / f"runs/{condition}-fingerprint.json").read_text())
            if (fingerprint["test_sha256"] != meta["sha256"] or
                fingerprint["config_sha256"] != manifest["config_sha256"] or
                fingerprint["model_provenance_sha256"] != manifest["model_provenance_sha256"] or
                fingerprint["condition"] != condition or fingerprint["reference_excerpts"]):
                raise ValueError("Q&A evaluation settings changed")
            for row, example in zip(rows, examples):
                expected = diagnostic(row["raw"], example["answer"])
                if any(row[k] != v for k, v in expected.items()): raise ValueError("Q&A diagnostics changed")
            if condition == "adapter":
                training = json.loads((run / "runs/training-summary.json").read_text())
                if fingerprint["adapter_sha256"] != training["adapter_sha256"] or digest(run / "adapters/qa/adapters.safetensors") != training["adapter_sha256"]:
                    raise ValueError("Completed Q&A adapter changed")
        outputs[condition] = {r["id"]: r for r in rows}
    training = run / "runs/training-summary.json"
    metrics = run / "runs/train-metrics.jsonl"
    status = run / "STATUS.json"
    return {"experiment": "qa-v1", "model": cfg["upstream"], "revision": cfg["revision"],
            "dataset_counts": {k: v["count"] for k, v in manifest["splits"].items()},
            "clinical_review": "pending", "reference_excerpts": False,
            "training": json.loads(training.read_text()) if training.exists() else None,
            "loss": [json.loads(l) for l in metrics.read_text().splitlines()] if metrics.exists() else [],
            "status": json.loads(status.read_text()) if status.exists() else {"status": "in_progress"},
            "cases": [{"id": e["id"], "question": e["question"], "reference": e["answer"],
                       "source_title": e["source_title"], "publisher_url": e["publisher_url"],
                       "source_revision": e["source_revision"],
                       "outputs": {k: v.get(e["id"]) for k, v in outputs.items()}}
                      for e in examples]}


def report(run):
    cfg, manifest = verify(run)
    comparison = comparison_data(run)
    result = {"experiment": "qa-v1", "model": cfg["upstream"], "revision": cfg["revision"],
              "reference_excerpts": False, "planned_cases": manifest["splits"]["test"]["count"],
              "split_counts": {k: v["count"] for k, v in manifest["splits"].items()},
              "clinical_review": "pending", "metric_limit": "Word overlap is not factual accuracy or medical reliability.",
              "conditions": {}}
    for condition in ["base", "adapter"]:
        rows = [e["outputs"][condition] for e in comparison["cases"] if e["outputs"][condition] is not None]
        result["conditions"][condition] = {"n": len(rows), "status": "complete" if len(rows) == result["planned_cases"] else "pending",
            "mean_reference_word_f1": sum(r["reference_word_f1"] for r in rows) / len(rows) if rows else None,
            "repetition_count": sum(r["repeated_fourgram"] for r in rows),
            "token_limit_count": sum(r["finish_reason"] == "length" for r in rows)}
    training = run / "runs/training-summary.json"
    result["training"] = json.loads(training.read_text()) if training.exists() else None
    (run / "runs/results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "train", "evaluate", "report", "predict"])
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-project", default=str(ROOT.parent / "oral-boards"))
    parser.add_argument("--condition", choices=["base", "adapter"])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run = local_directory(args.run_dir)
    if args.operation == "prepare": prepare(run, Path(args.source_project).resolve())
    elif args.operation == "train": train(run)
    elif args.operation == "report": report(run)
    elif args.operation == "predict": predict(run)
    elif args.condition: evaluate(run, args.condition, args.resume)
    else: parser.error("--condition is required for evaluation")


if __name__ == "__main__":
    main()
