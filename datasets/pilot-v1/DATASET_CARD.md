# Original pilot dataset, version 1

This immutable snapshot is the actual generated data used in the first local SmolLM2-135M LoRA experiment. It is included in this **private** repository at the user's explicit request. It contains short publisher-reference excerpts and mechanically generated note-completion prompts, not patient records, expert-written board questions, or a clinical-competence benchmark.

| Split | Sources | Supported completions | Missing-context abstention | Unsupported/malformed | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training (`train.jsonl`) | 6 | 120 | 12 | 12 | 144 |
| Validation (`valid.jsonl`) | 2 | 12 | 2 | 2 | 16 |
| Test (`heldout.jsonl`) | 4 | 16 | 4 | 4 | 24 |

`manifest.json` records the exact source titles, relative extracted-document filenames, publisher URLs, original PDF/content checksums, split assignments, generator seed, and question templates. Dataset file bytes and hashes match the original local files. The shared manifest updates the export policy to reflect the new explicit private-sharing authorization and records the original local manifest's checksum. `INTEGRITY.json` independently records byte counts and SHA-256 checksums for all JSON/JSONL files.

## Construction and supervision

The generator reads active publisher references from the authorized local oral-board search database. Its existing active-document selection excludes reviewed superseded/duplicate documents. Separate documents and positive wording templates are assigned to each split before extraction. Exact normalized sentence duplicates across source groups are removed; related terminology or semantic overlap can remain.

Short prose sentences of 14–28 words are selected. Figure OCR, Markdown tables/headings, numeric statements, references, apparent contacts/URLs, and identifier-pattern matches are excluded. Each supported example contains two candidate sentences, including the target sentence. The note gives the first half of that sentence, and the target JSON contains its exact remaining words and the matching `S1`/`S2` citation. Other examples require `{"answer":"ABSTAIN","citation":"NONE"}`. Full message records are present for assistant-only loss masking.

Training and validation tokenized examples had a maximum length of 285 tokens under the original tokenizer, below the configured 384-token ceiling; targets were not truncated. The saved run used 40 batch-size-one updates and 947 supervised output tokens, rank-8 LoRA on four layers, Adam learning rate 0.001, and seed 20261002. It did not complete a full pass through all 144 training rows.

The extractive retrieval baseline sees the same two supplied candidate excerpts and can match the sentence prefix directly. Its perfect score is expected for this task and does not measure full-corpus retrieval recall or clinical reasoning. Exact-answer/schema/citation metrics are automated proxies, not expert clinical assessment. The model's 0/24 structured task result does not establish that every underlying factual response was wrong.

## Privacy and rights

Before export, generated datasets and provenance were checked for patient-ID/MRN fields, SSNs, DOB fields, email/phone patterns, credential/private-key patterns, and local absolute paths; no matches were found. The selected sources are publisher reference documents. Identifier-field forms in the wider collection were excluded. This is a limited pattern screen and source selection, not a guarantee that every possible sensitive item was detected.

The source documents retain publisher copyright. No open document license or general redistribution/training permission was verified. The user's instruction authorizes this private snapshot; it does not establish third-party rights. The repository's MIT code license **does not apply to these derived datasets**. Do not make the repository or datasets public, or redistribute/relicense them, without a separate rights review and any necessary permission. Original PDFs/full source corpus and model/adapter weights are not included.

Source revision dates differ and the pilot did not independently resolve document freshness or clinical conflicts. These rows are for inspecting/reproducing the experiment, not patient care. Future improved QA/rubric datasets must use a separate version and preserve this original negative-run snapshot.
