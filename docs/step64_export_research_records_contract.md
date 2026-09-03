# Step 64 — Export / Research Records Contract

## Specification basis

No historical Step 64 specification or export implementation was found in the
repository or Git history. This document establishes the smallest contract
supported by the existing application: the authoritative research record is a
user-owned `ResearchRunModel`, already inspected through the run, claim, and
provenance services.

## Contract

`GET /api/v1/research/runs/{run_id}/export?format=json` returns a structured
JSON representation of one authenticated user's research run. The response
contains:

- `schema_version` and `format`;
- the existing research run detail, including persisted output references and
  ordered execution steps;
- persisted claims and their evidence links;
- existing provenance traces, including source, document, passage, citation,
  and graph metadata where available.

Only `json` is supported. Unsupported formats return validation failure. The
backend resolves ownership from the authenticated principal; an optional
`user_id` query parameter may only repeat that identity for compatibility with
existing research routes and cannot select another owner.

Lists are returned in deterministic order by stable identifiers after the
underlying services load authoritative records. No export file is written and
no new persistence model or frontend route is introduced.

## Security and integrity

The endpoint uses the existing bearer authentication and
`ResearchRunService.get_owned_run` boundary. Missing authentication returns
`401`; a run owned by another user is indistinguishable from a missing run and
returns `404`. Export data is assembled from existing application services; the
endpoint does not infer claims, citations, evidence, or provenance.

## Verification

Focused tests cover populated and minimal records, deterministic repeated
exports, authentication, cross-user isolation, owner-ID override rejection,
unsupported formats, malformed identifiers, and provenance/evidence
preservation. Runtime verification uses a disposable PostgreSQL database and
temporary authenticated users.
