"""Build an immutable, local-only review dataset; never train on unreviewed rows."""
import argparse
import collections
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from qa import ROOT, PII, SYSTEM, StudyTokenizer, digest, local_directory, messages, offline


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_rows(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def normalized(text):
    return re.sub(r"\W+", " ", text.lower()).strip()


def family(url):
    """Conservatively join publisher PDF revisions, retaining the original URL."""
    parsed = urlparse(url)
    pathname = parsed.path.lower().rstrip("/")
    if pathname.endswith(".pdf"):
        pathname = re.sub(r"[-_]?(?:20\d\d|\d\d)(?=\.pdf$)", "", pathname)
    return parsed.netloc.lower().removeprefix("www.") + pathname


def protected_sources():
    """Keep every earlier validation/test source out of this training candidate pool."""
    families, pdfs, slugs, pairs, receipts = set(), set(), set(), set(), []
    manifest = ROOT / "datasets/pilot-v1/manifest.json"
    data = json.loads(manifest.read_text())
    receipts.append({"path": str(manifest.relative_to(ROOT)), "sha256": digest(manifest)})
    for doc in data["documents"]:
        if doc["split"] in ["valid", "test"]:
            families.add(family(doc["publisher_url"])); pdfs.add(doc["pdf_sha256"])
    slugs.update(json.loads((ROOT / "configs/qa-v1.json").read_text())["source_exclusions"])
    for name in ["qa-v1-20261009-03", "qa-long-v1-20261009-01"]:
        path = ROOT / ".local" / name / "data/manifest.json"
        if not path.exists(): raise ValueError("Required prior experiment boundary is absent")
        old = json.loads(path.read_text())
        receipts.append({"path": str(path.relative_to(ROOT)), "sha256": digest(path)})
        for split in ["valid", "test"]:
            slugs.update(old["source_groups"][split])
            rows_path = path.parent / old["splits"][split]["file"]
            if digest(rows_path) != old["splits"][split]["sha256"]:
                raise ValueError("Previous frozen dataset changed")
            receipts.append({"path": str(rows_path.relative_to(ROOT)), "sha256": digest(rows_path)})
            for line in rows_path.read_text().splitlines():
                row = json.loads(line)
                families.add(family(row["publisher_url"])); pdfs.add(row["pdf_sha256"])
                slugs.add(row["source_slug"])
                pairs.add(normalized(row["question"] + "\n" + row["answer"]))
    return {"families": sorted(families), "pdf_hashes": sorted(pdfs), "slugs": sorted(slugs),
            "pair_sha256": sorted(hashlib.sha256(p.encode()).hexdigest() for p in pairs),
            "receipts": receipts}


def publisher_index(source):
    database = source / "search.sqlite"
    index = {}
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        docs = connection.execute("SELECT d.title,d.hash,d.active,d.collection,c.doc FROM documents d JOIN content c ON d.hash=c.hash").fetchall()
    for title, content_hash, active, collection, body in docs:
        url = re.search(r"^Source: <([^>]+)>", body, re.M)
        pdf = re.search(r"^PDF SHA-256: `([a-f0-9]{64})`", body, re.M)
        if not url or not pdf: continue
        host = urlparse(url[1]).netloc.lower().removeprefix("www.")
        if host not in ["aapd.org", "abpd.org"]: continue
        value = {"title": title, "content_hash": content_hash, "pdf_sha256": pdf[1],
                 "active": bool(active), "collection": collection,
                 "identifier_form_flag": any(re.search(p, body) for p in PII.values())}
        # Prefer the active record when the database retains earlier versions.
        if url[1] not in index or value["active"]: index[url[1]] = value
    return index, database


def grouping(rows):
    parent = {r["id"]: r["id"] for r in rows}; seen = {}
    def find(k):
        while k != parent[k]: parent[k] = parent[parent[k]]; k = parent[k]
        return k
    def union(a, b):
        a, b = find(a), find(b)
        if a != b: parent[max(a, b)] = min(a, b)
    for row in rows:
        keys = ["file:" + p for p in [row["file"], *row.get("related_files", [])]]
        keys += ["source:" + f for f in row["source_families"]]
        keys += ["pair:" + row["normalized_pair_sha256"]]
        if len(normalized(row["answer"])) >= 80: keys.append("answer:" + row["normalized_answer_sha256"])
        for key in keys:
            if key in seen: union(row["id"], seen[key])
            seen[key] = row["id"]
    groups = collections.defaultdict(list)
    for row in rows:
        row["source_group"] = "group-" + find(row["id"])
        groups[row["source_group"]].append(row["id"])
    return dict(sorted(groups.items()))


def prepare(destination, source, model):
    if destination.exists(): raise ValueError("Existing dataset is immutable; choose a new version directory")
    if source.resolve() == ROOT or not (source / "content/aapd-notes").is_dir():
        raise ValueError("Expected the read-only Oral Boards source project")
    index, database = publisher_index(source)
    boundary = protected_sources()
    script = ROOT / "src/oral_dataset_extract.mjs"
    result = subprocess.run(["node", str(script), str(source)], capture_output=True, text=True,
                            check=True, timeout=60, cwd=source)
    extracted = json.loads(result.stdout)
    if extracted["errors"]: raise ValueError("Source parser rejected content; no dataset was written")
    source_files = sorted({f["path"] for f in extracted["files"]})
    file_metadata = {}
    for name in source_files:
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()): raise ValueError("Source path escaped the project")
        raw = path.read_text()
        file_metadata[name] = {"sha256": digest(path), "bytes": path.stat().st_size,
                               "identifier_form_flag": any(re.search(p, raw) for p in PII.values())}
    offline()
    from transformers import AutoTokenizer
    tokenizer = StudyTokenizer(AutoTokenizer.from_pretrained(model, local_files_only=True, trust_remote_code=False))
    tokenizer_files = {p.name: digest(p) for p in model.iterdir() if p.is_file() and
                       ("token" in p.name or p.name in ["vocab.json", "merges.txt", "special_tokens_map.json"])}
    rows, excluded = [], []
    for number, item in enumerate(extracted["rows"]):
        pair = hashlib.sha256(normalized(item["question"] + "\n" + item["answer"]).encode()).hexdigest()
        identity = "qa2-" + hashlib.sha256((item["file"] + "\n" + item["kind"] + "\n" + item["question"] + "\n" + item["answer"]).encode()).hexdigest()[:24]
        refs = item["references"]
        families = sorted({family(r["url"]) for r in refs if r.get("url")})
        blocks = []
        paths = [item["file"], *item.get("related_files", [])]
        if any(file_metadata[p]["identifier_form_flag"] for p in paths): blocks.append("identifier_form_in_source_file")
        if any(re.search(p, item["question"] + "\n" + item["answer"]) for p in PII.values()):
            blocks.append("identifier_form_in_example")
        publisher_refs = []
        for ref in refs:
            url = ref.get("url", "")
            doc = index.get(url)
            if doc:
                publisher_refs.append({"url": url, **doc, "pages": ref.get("pages"), "revision": ref.get("revision")})
                if not doc["active"]: blocks.append("inactive_publisher_reference")
                if doc["identifier_form_flag"]: blocks.append("identifier_form_in_publisher_reference")
            else: blocks.append("publisher_reference_unverified")
            if urlparse(url).netloc.lower() in ["drive.google.com", "docs.google.com"]:
                blocks.append("private_study_guide_reference")
        if not refs: blocks.append("missing_source_reference")
        linked = [Path(item["file"]).stem, *[Path(p).stem for p in item.get("related_files", [])],
                  *[str(s).split("/")[-1] for s in item.get("related_slugs", [])]]
        if (set(families) & set(boundary["families"]) or set(linked) & set(boundary["slugs"])
                or pair in boundary["pair_sha256"]
                or any(d["pdf_sha256"] in boundary["pdf_hashes"] for d in publisher_refs)):
            blocks.append("prior_validation_or_evaluation_source")
        # Do not retain question/answer text for identifier flags or protected sources.
        if any(b.startswith("identifier_form") or b == "prior_validation_or_evaluation_source" for b in blocks):
            excluded.append({"id": identity, "file": item["file"], "kind": item["kind"],
                             "reasons": sorted(set(blocks)), "source_sha256": file_metadata[item["file"]]["sha256"]})
            continue
        if item.get("requires_case_review"): blocks.append("fictional_case_and_answer_mapping_unverified")
        if item.get("broad_source_mapping"): blocks.append("claim_level_source_mapping_needed")
        if item.get("needs_question_rewrite"): blocks.append("question_rewrite_required")
        if "```" in item["answer"] or re.search(r"<[A-Z][A-Za-z]+", item["answer"]):
            blocks.append("diagram_or_component_requires_review")
        chat = messages(item["question"]) + [{"role": "assistant", "content": item["answer"]}]
        tokens = len(tokenizer.apply_chat_template(chat, tokenize=True, return_dict=False))
        if tokens > 384: blocks.append("sequence_exceeds_current_384_token_recipe")
        if not normalized(item["answer"]): blocks.append("empty_text_answer")
        rows.append({**item, "id": identity, "source_families": families,
                     "source_sha256": file_metadata[item["file"]]["sha256"],
                     "related_file_sha256": {p: file_metadata[p]["sha256"] for p in item.get("related_files", [])},
                     "publisher_references": publisher_refs, "sequence_tokens": tokens,
                     "normalized_pair_sha256": pair,
                     "normalized_answer_sha256": hashlib.sha256(normalized(item["answer"]).encode()).hexdigest(),
                     "review": {"status": "pending", "clinical_correctness": "not_reviewed",
                                "publisher_claim_support": "not_verified", "training_approved": False},
                     "blocking_reasons": sorted(set(blocks)), "messages": chat})
    if len({r["id"] for r in rows + excluded}) != len(rows) + len(excluded):
        raise ValueError("Duplicate stable IDs; review extraction before freezing")
    groups = grouping(rows)
    reviewable = [r for r in rows if not r["blocking_reasons"]]
    blocked = [r for r in rows if r["blocking_reasons"]]
    destination.mkdir(parents=True)
    datasets = {"candidates.jsonl": rows, "reviewable.jsonl": reviewable,
                "blocked.jsonl": blocked, "excluded.jsonl": excluded}
    for name, records in datasets.items(): write_rows(destination / name, records)
    write_json(destination / "source_groups.json", groups)
    write_json(destination / "protected_sources.json", boundary)
    with (destination / "review_queue.csv").open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["id", "kind", "source_file", "tokens", "blocking_reasons", "review_status", "question", "answer"])
        for row in reviewable + blocked:
            writer.writerow([row["id"], row["kind"], row["file"], row["sequence_tokens"],
                             ";".join(row["blocking_reasons"]), "pending", row["question"], row["answer"]])
    counts = {"extracted": len(extracted["rows"]), "candidates": len(rows),
              "reviewable": len(reviewable), "blocked": len(blocked), "excluded": len(excluded),
              "approved_for_training": 0, "source_files": len(source_files), "source_groups": len(groups)}
    manifest = {"version": "qa-v2", "stage": "immutable_review_candidates", "system": SYSTEM,
                "counts": counts, "counts_by_kind": dict(sorted(collections.Counter(r["kind"] for r in rows).items())),
                "reviewable_by_kind": dict(sorted(collections.Counter(r["kind"] for r in reviewable).items())),
                "blocking_reason_counts": dict(collections.Counter(b for r in blocked for b in r["blocking_reasons"])),
                "exclusion_reason_counts": dict(collections.Counter(b for r in excluded for b in r["reasons"])),
                "source_db_sha256": digest(database), "source_files": file_metadata,
                "parser_files": {p: digest(source / p) for p in extracted["parserFiles"]},
                "implementation": {"src/qa_dataset.py": digest(ROOT / "src/qa_dataset.py"),
                                   "src/oral_dataset_extract.mjs": digest(script)},
                "tokenizer": {"local_path": str(model.relative_to(ROOT)), "files": tokenizer_files,
                              "enable_thinking": False, "current_sequence_budget": 384},
                "policy": {"local_only": True, "sharing_authorized": False, "training_started": False,
                           "external_inference_or_embeddings": False, "generated_clinical_answers": False,
                           "answer_truncation": False, "clinical_review_required": True},
                "limits": ["Study answers are not official clinical answer keys.",
                           "Publisher URL matching is not claim-level source verification.",
                           "Identifier regex screening does not prove absence of patient information.",
                           "Source grouping uses files, publisher URL families, exact pairs and substantive identical answers; semantic overlap can remain.",
                           "No training/validation/test split is released. Freeze a reviewed successor and evaluation questions before model evaluation.",
                           "Large connected source groups may require restricting cross-source examples to obtain a usable independent evaluation."],
                "files": {name: {"sha256": digest(destination / name), "count": len(records)} for name, records in datasets.items()}}
    for name in ["source_groups.json", "protected_sources.json", "review_queue.csv"]:
        manifest["files"][name] = {"sha256": digest(destination / name)}
    write_json(destination / "manifest.json", manifest)
    report = "# Local qa-v2 review dataset\n\nThis is an immutable candidate snapshot, not an approved training dataset. No model training or inference was run.\n\n"
    report += "| Allocation | Rows |\n| --- | ---: |\n" + "".join(f"| {k} | {v} |\n" for k, v in counts.items())
    report += "\n## Candidate types\n\n| Type | Candidates | Ready for source/clinical review |\n| --- | ---: | ---: |\n"
    report += "".join(f"| {k} | {n} | {manifest['reviewable_by_kind'].get(k, 0)} |\n" for k, n in manifest["counts_by_kind"].items())
    report += "\n## Review workflow\n\n1. Start with `reviewable.jsonl` or the first rows of `review_queue.csv`. Reviewable means no automated structural block, not clinically approved.\n2. Check every answer against its publisher reference and preserve conditions, exceptions, doses, and uncertainty. Inspect the evidence and source hashes.\n3. Record review decisions in a separate successor; do not edit this snapshot. Question rewrites and case/source reviews also require a successor.\n4. Keep prior validation/evaluation families excluded. Keep source-group relatives and paraphrases together.\n5. Freeze reviewed training splits plus independent generalization and separately labeled retention questions before another model evaluation.\n\n"
    report += "No `train.jsonl` is emitted because all rows await review. Long answers are retained whole and blocked under the existing 384-token recipe. Medical conditions with private or unmatched sources and cases without verified fictional status remain blocked. Excluded identifier/protected-source rows retain metadata only. Source-derived text, CSV, manifests, and all new dataset files remain local; no sharing is authorized.\n"
    (destination / "README.md").write_text(report)
    write_json(destination / "INTEGRITY.json", {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
                                               for p in destination.iterdir() if p.is_file()})
    verify(destination)
    print(json.dumps({"dataset": str(destination), "counts": counts,
                      "reviewable_by_kind": manifest["reviewable_by_kind"]}, indent=2))


def verify(destination):
    integrity = json.loads((destination / "INTEGRITY.json").read_text())
    if {p.name for p in destination.iterdir()} != set(integrity) | {"INTEGRITY.json"}:
        raise ValueError("Dataset files added or removed")
    for name, meta in integrity.items():
        path = destination / name
        if digest(path) != meta["sha256"] or path.stat().st_size != meta["bytes"]:
            raise ValueError("Frozen candidate bytes changed")
    manifest = json.loads((destination / "manifest.json").read_text())
    sets = {name: [json.loads(l) for l in (destination / name).read_text().splitlines()]
            for name in ["candidates.jsonl", "reviewable.jsonl", "blocked.jsonl", "excluded.jsonl"]}
    ids = lambda records: {r["id"] for r in records}
    if (ids(sets["reviewable.jsonl"]) & ids(sets["blocked.jsonl"]) or
            ids(sets["reviewable.jsonl"]) | ids(sets["blocked.jsonl"]) != ids(sets["candidates.jsonl"])):
        raise ValueError("Review allocation mismatch")
    boundary = json.loads((destination / "protected_sources.json").read_text())
    groups = json.loads((destination / "source_groups.json").read_text())
    grouped = [i for members in groups.values() for i in members]
    if len(grouped) != len(set(grouped)) or set(grouped) != ids(sets["candidates.jsonl"]):
        raise ValueError("Source grouping mismatch")
    for row in sets["candidates.jsonl"]:
        if row["review"]["training_approved"] or row["review"]["status"] != "pending":
            raise ValueError("Unreviewed snapshot cannot approve training")
        if set(row["source_families"]) & set(boundary["families"]): raise ValueError("Protected source leaked")
        if row["id"] not in groups[row["source_group"]]: raise ValueError("Row group mismatch")
        if any(re.search(p, row["question"] + "\n" + row["answer"]) for p in PII.values()):
            raise ValueError("Identifier-form text leaked")
        if row["messages"][-1]["content"] != row["answer"]: raise ValueError("Answer changed or truncated")
    if any("question" in r or "answer" in r for r in sets["excluded.jsonl"]):
        raise ValueError("Excluded source text retained")
    if any(r["blocking_reasons"] or r["sequence_tokens"] > 384 for r in sets["reviewable.jsonl"]):
        raise ValueError("Blocked row is marked reviewable")
    if manifest["counts"]["approved_for_training"] != 0 or (destination / "train.jsonl").exists():
        raise ValueError("Candidate snapshot must not become a training set")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "verify"])
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--source-project", default=str(ROOT.parent / "oral-boards"))
    parser.add_argument("--model-dir", default=".local/qa-v1-20261009-03/models/qwen3-0.6b-4bit")
    args = parser.parse_args(); destination = local_directory(args.dataset_dir)
    if args.operation == "prepare": prepare(destination, Path(args.source_project).resolve(), local_directory(args.model_dir))
    else: print(json.dumps({"verified": str(destination), "counts": verify(destination)["counts"]}, indent=2))
