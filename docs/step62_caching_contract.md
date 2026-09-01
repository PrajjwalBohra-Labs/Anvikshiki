# Step 62 — Caching Contract

## Contract discovery

No historical Step 62 specification or general cache API was found. Existing
repository evidence supports only two bounded caches:

- Step 17 canonical-URL raw web-response cache under `CACHE_LOCAL_ROOT`;
- Step 38 in-process embedding/reranker reuse.

## Scope decision

Step 62 does not introduce Redis, a general result cache, or frontend query
cache. The existing web cache remains canonical-URL keyed, preserves raw
responses, does not cache failed fetches, and is covered by its existing tests.
API and health responses now send `Cache-Control: no-store`, preventing shared
clients from caching authenticated or operational responses.

A broader TTL/invalidation contract for research, memory, notebook, or
provenance results is not discoverable and remains intentionally unspecified.
