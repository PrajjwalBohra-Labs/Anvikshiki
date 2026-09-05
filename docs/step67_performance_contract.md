# Step 67 — Performance Contract

Step 67 establishes measured, low-risk performance work over the existing
Anvikshiki architecture. It does not add a distributed cache, queue, or
performance-specific database schema.

## Measured bottleneck and change

The authenticated search endpoint retrieved each citation through
`CitationService.generate_citation()` inside the result loop. For `N` results
this added `N` passage queries after retrieval, in addition to the retrieval
and relationship-loading queries. `CitationService.generate_citations()` now
resolves the returned passage IDs in one authoritative query, while the
endpoint preserves result order and the existing citation contract.

The single-passage method remains available for existing callers and delegates
to the same formatter and authoritative lookup.

## Performance and correctness contract

- Search result order, scores, identifiers, provenance, and citation strings
  remain unchanged.
- Duplicate requested passage IDs are de-duplicated for lookup.
- Missing citation data is a safe server error rather than fabricated output.
- No authorization, ownership, cache, or security decision is cached or
  bypassed.
- No migration or new dependency is required.
- The focused regression test asserts one database execution for a batch and
  stable citation values; retrieval and evaluation regression suites continue
  to provide research-quality coverage.

## Verification methodology

The baseline was established by inspecting the search query shape: the prior
result-loop implementation performed one citation lookup per returned result.
The optimized path performs one batched lookup for the complete result set.
Focused tests record the resulting database execution count. Full absolute
latency depends on the local PostgreSQL, model, and storage runtime and is not
used as a portable acceptance threshold.
