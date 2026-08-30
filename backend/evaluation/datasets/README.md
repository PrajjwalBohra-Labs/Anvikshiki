# Retrieval golden set v1

`retrieval_golden_set_v1.json` is a small, durable, passage-level regression
set. It contains six philosophical sources and seven queries, including one
explicitly contrasting Epicurean pleasure with Aristotelian virtue and one
cross-passage Stoic query.

The Tarka Samgraha record uses a copied two-page philosophical PDF fixture from
`data/originals/*_tarka_samgraha.pdf`. The remaining primary-source
excerpts are short public-domain translations documented by their Project
Gutenberg URLs in the dataset. The set is intentionally small and is not claimed
to represent production retrieval quality or the breadth of philosophical
traditions.

Each corpus passage has a stable dataset key. During evaluation the loader maps
that key to the actual PostgreSQL source, document, document-version, page, and
passage IDs created or reused through normal ingestion. Ground-truth labels are
explicit graded relevance values from 1 (contextual) through 3 (directly
relevant); no labels are inferred from retrieval output.

Run from the repository root:

```powershell
python -m backend.evaluation.retrieval_evaluation --json
```

The command requires the configured PostgreSQL/pgvector database and local
embedding/reranker models. Use `--write-baseline path.json` to record a report;
use `--baseline path.json` on a later run to report metric deltas.
