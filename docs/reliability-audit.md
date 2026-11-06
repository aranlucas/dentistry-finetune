# Correctness and reliability audit — 2026-11-06

Baseline: remote main b618950, after the merged untangle pass. Clean isolated worktree; public APIs and frozen pilot artifacts stay unchanged. No local tests, builds, benchmarks, model calls or corpus uploads. Validation runs in CI only.

## Inventory and boundaries

- Python CLI: source selection/extraction, frozen dataset construction, model download/provenance, local MLX training/evaluation and resumptions. `runtime`, `qa`, `qa_long`, `bounded`, `resources` enforce offline inference, local directories, immutable fingerprints, a single model-job lock, memory/swap/thermal limits and deadlines.
- HTTP: loopback `server.make_server`, exact Host/Origin checks, static asset containment, result/comparison/practice GETs, bounded prediction POSTs. Requests and outputs are not logged. No multi-tenant or production service exists.
- React/TypeScript: three study sheets, run selection, case filtering/inspection, ephemeral prediction requests; Zod validates responses and TanStack Query owns server state. Missing local experiments must show errors, never substitute results.
- Persistence: approved byte-frozen pilot snapshot, private run registries/predictions/checkpoints, append-only human judgment chain. Evaluation resume validates recipe hashes and ordered prefixes; completed results are not regenerated.
- Export: `export_source.py` explicit authored-code/aggregate/snapshot/transcript allowlist and local snippet screening. No raw source corpus or weights may leave the machine. New e2e config/tests must be included so exported verification stays reproducible.
- CI: existing Python synthetic contracts/unittest and frontend lint/format/Vitest/build. Add deterministic real `e2e` + `@e2e-dev/web` against the built site and Python HTTP API, without models or private corpus.

## Proven findings before implementation

1. **Medium / high confidence: concurrent judgment writers corrupt the immutable chain.** `judgment_journal.append` reads and verifies the old journal before opening it for append, with no interprocess lock. Two review CLI processes can both observe the same tail and append duplicate sequence/previous hashes (or duplicate judgment IDs), making all later readers reject the journal. Expected: serialize verification and append, with duplicate rejection after acquiring the lock. Regression: two independently opened writer handles append distinct IDs concurrently; every row must verify and both IDs survive. Existing immutability tests cover sequential writes only.
2. **Medium / high confidence: unavailable result files and invalid prediction selections break the HTTP response contract.** `server.Handler.do_GET` reads `/api/results` and `/api/practice` without the error handling used by comparison routes. Missing/corrupt files close the connection. `do_POST` accepts a JSON array/object as `run`, causing an unhashable-key TypeError in development selection; missing selected manifest fields raise uncaught KeyError. Expected: explicit JSON 400 for malformed requests and 503 for unavailable local state, release BUSY after every failure. Regression: real synthetic HTTP requests assert status/error and a subsequent request succeeds.

3. **Medium / high confidence: development resume invents missing provenance.** Independent review found `development.evaluate` and `grounded.evaluate` write a new fingerprint even when saved predictions already exist. With a missing original fingerprint, answers from an unknown recipe can be attributed to current settings. Match the pilot/Q&A fail-closed behavior and assert rejection before any model loading or fingerprint creation.
4. **Medium / high confidence: curated training trusts unverified review decisions.** `curated_dataset.prepare` reads the journal with `rows`, accepting a modified decision despite its stale hash chain. Verify the chain before promoting any reviewed candidates; regression changes a valid JSON decision and requires rejection before tokenizer loading.

5. **Medium / high confidence: partial HTTP bodies hold the inference slot indefinitely.** `do_POST` acquired BUSY before an unbounded body read; the subprocess deadline starts too late to protect it. Bound socket reads and assert a partial-body request gets 408, then a later request is accepted. Invalid child JSON is likewise a 503 response rather than a dropped connection.

## Rejected hypotheses and limits

- Host rebinding and cross-origin requests: exact allowlists already reject these; no authorization redesign justified.
- Arbitrary experiment/static traversal: resolved local-directory and asset-parent checks already constrain paths.
- Pilot/Q&A resume validates fingerprints and prefixes; development variants need the missing-fingerprint fix above.
- Local model failures should use a cloud fallback: rejected; offline-only behavior is intentional.
- MLX runtime/hardware accuracy cannot be established on Linux CI; keep all existing resource guards. This audit establishes software contracts, not medical reliability or new benchmark results.
- e2e applies to the actual web viewer and deterministic keyword-completion journey. Raw extraction CLI uses local browser tooling but has no standalone UI; existing Python dataset/provenance tests cover that boundary. No model credentials or agent steps are warranted.

## Validation evidence

Pending CI and independent review. Regressions will also run against baseline source in CI to demonstrate they detect the defects.

Independent review: one same-provider child challenged the findings and implementation and inspected dataset grouping, model provenance, resource limits, static containment and frontend state. Its additional provenance/body-deadline findings are included above. Published e2e declarations were checked for actual deterministic APIs. Native `fcntl.flock` is used for the existing macOS/Linux journal, requiring no third-party lock library or journal format change. Keyword prediction now imports the resource stack only for model conditions, keeping the no-model CI path standard-library-only.

Source export completed locally: 96 allowlisted authored/approved files; archive and receipt remain under `.local`. Dataset bytes and existing aggregate metrics are unchanged. No test or build ran locally; lockfile install used `--ignore-scripts`.

Dependencies: `e2e@0.23.0` and `@e2e-dev/web@0.15.5` are the real published tester-army runner and browser engine. Current quickstart/CI/GitHub Actions docs and the pinned upstream Vite example were read; their Node requirement is ^22.22.3 or >=24.8.0, satisfied by existing CI Node 24.22.1. CI runs exact locator/action/assertion flows against built React + real Python API: evidence-backed completion, missing-evidence abstention, recovered completion, unavailable Q&A error and navigation back to a working journey. No agent, login, API key or local private dataset is used.

Final independent review accepted the persistence and e2e changes and identified that a socket inactivity timeout alone permits a drip-fed body to monopolize BUSY. The final implementation uses an absolute monotonic body deadline, with a dedicated drip-feed regression in CI as well as the stalled-body case.

First CI run (42300453612) passed website lint/format/Vitest/build, privacy checks, synthetic contracts, all Python tests and compilation. Baseline demonstration then failed because checkout was shallow; CI now fetches history explicitly. Browser journeys still require evidence from the next complete CI run.
