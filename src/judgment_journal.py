# Native JSON/JSONL commands cannot enforce this repository's append-only judgment hash chain.
"""Local judgment storage shared by authoring, review and result readers."""
import hashlib
import json
import time


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def verified_rows(path):
    entries = rows(path)
    previous = None
    seen = set()
    for sequence, entry in enumerate(entries, 1):
        value = dict(entry)
        sha = value.pop('entry_sha256')
        if value['sequence'] != sequence or value['previous_sha256'] != previous:
            raise ValueError('Judgment sequence changed')
        if hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != sha:
            raise ValueError('Logged judgment changed')
        if value['id'] in seen:
            raise ValueError('Existing judgment is immutable')
        seen.add(value['id'])
        previous = sha
    return entries


def append(review, entries):
    path = review / 'judgments.jsonl'
    old = verified_rows(path)
    entries = list(entries)
    seen = {entry['id'] for entry in old}
    ids = [entry['id'] for entry in entries]
    if len(set(ids)) != len(ids) or seen.intersection(ids):
        raise ValueError('Existing judgment is immutable')
    previous = old[-1]['entry_sha256'] if old else None
    with path.open('a') as stream:
        for sequence, entry in enumerate(entries, len(old) + 1):
            value = {**entry, 'sequence': sequence, 'previous_sha256': previous,
                     'time_unix': time.time()}
            previous = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            value['entry_sha256'] = previous
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')
            stream.flush()
