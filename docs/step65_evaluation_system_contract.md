# Step 65 — Evaluation System Contract

## Status and scope

No historical Step 65 specification was present in the repository or Git
history. This contract records the minimum implementation aligned with the
existing Step 16 retrieval evaluation and its versioned golden dataset. It is
an operator/test capability; it does not change production retrieval.

## Dataset and safety

`backend.evaluation.retrieval_evaluation` validates a JSON dataset with a
dataset ID/version, non-empty corpus and queries, stable source/document/
passage keys, non-empty passage content, positive page numbers, and explicit
graded relevance values from 1 through 3. IDs and query metadata must be
non-empty strings; duplicate corpus/query/ground-truth keys and malformed
records are rejected. Corpus filenames resolve beneath the dataset's
`corpus_root`; traversal and missing fixtures are rejected.

## Evaluation and metrics

The runner reuses the existing PostgreSQL/pgvector ingestion, embedding,
lexical, semantic, hybrid, and reranked retrieval services. It evaluates the
retrieved top `k` using recall@k, precision@k, MRR, and nDCG@k. Empty result
sets and empty ground truth use zero-valued metrics. MRR is measured within the
same top-k cutoff. Citation accuracy, provenance resolution, primary-source
hit rate, and contradiction recall are reported only from backend-returned
metadata and explicit dataset classifications.

## Reproducibility and baselines

Stable dataset keys and backend identity metadata are preserved in reports.
`canonical_evaluation_result()` excludes timestamps and database-specific
identifiers from the signed representation, and `deterministic_signature()`
stores its SHA-256 signature. `compare_baseline()` reports per-method metric
deltas and a deterministically ordered list of negative (regression) deltas.

## CLI and API

Run from the repository root with the repository interpreter:

```powershell
.venv\Scripts\python.exe -m backend.evaluation.retrieval_evaluation --json
```

`--dataset`, `--top-k`, `--baseline`, and `--write-baseline` are supported.
The programmatic API is `load_dataset`, `validate_dataset`,
`calculate_metrics`, `evaluate_dataset`, `compare_baseline`,
`canonical_evaluation_result`, and `deterministic_signature`.

Evaluation is authenticated only by operator/runtime configuration and does not
provide a user-facing API. It accepts no modules, commands, URLs, or user
identity selectors. No database migration, frontend surface, or new
dependency is required.

## Verification

Focused contract tests are in
`backend/tests/unit/test_step65_evaluation_system.py`; existing dataset and
metric tests remain in `backend/tests/evaluation/test_retrieval_evaluation.py`.
The real corpus evaluation requires PostgreSQL/pgvector and the configured
local embedding/reranker models. If those runtime prerequisites are unavailable
the focused validation/metric tests remain valid, but a full retrieval report
is not claimed.
