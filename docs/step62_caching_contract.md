# Step 62 - Caching Contract

No historical Step 62 specification was found in the repository or Git
history. This document records the smallest caching contract justified by the
current architecture.

## Scope

Only the authenticated `GET /api/v1/sources/` read is cached. Source metadata
is shared by the current application model rather than owned by an individual
user. User-owned research, memory, notebook, conversation, provenance, and
document responses remain authoritative reads and are not cached by Step 62.

## Cache behavior

- The cache is process-local and in-memory; it is not a second database.
- The deterministic key is `sources:list:v1`.
- Entries expire after 30 seconds using a monotonic clock.
- A successful `POST /api/v1/sources/` invalidates the source-list entry after
  its database commit succeeds.
- Database errors are returned through the existing error boundary and are
  never cached.
- Cache get/set failures fail open to the authoritative database read.
- Cached values are copied on both write and read to prevent caller mutation.

## Security and observability

Authentication is evaluated before the cache is accessed. The endpoint does
not accept a client-supplied owner identifier. Since the cached payload is
global source metadata, the key contains no user identity, bearer token, or
private data. Cache events log only a fixed cache name and event type; cache
keys and payloads are not logged. The existing request IDs, security headers,
and private API cache policy remain unchanged.
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
