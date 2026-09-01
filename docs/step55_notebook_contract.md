# Step 55 — Notebook Frontend Contract

## Contract provenance

An exhaustive search of the current repository, reachable branches, stashes,
and repository history found no authoritative historical Step 55 notebook
specification, notebook persistence model, or notebook API. This document
therefore establishes the minimum Step 55 contract needed to resolve that
blocker. It is a new project contract, not a reconstruction of a missing
historical requirement.

## Scope

A notebook is a durable, user-owned research note. It is separate from
conversations, research runs, memory, citations, and the provenance graph.
The notebook stores user-authored plain text or Markdown. The frontend edits
the text in a textarea and does not render arbitrary Markdown as HTML.

This step does not add autosave, collaboration, version history, full-text
search, automatic citation insertion, research-run attachment, provenance
edges, or conversion of research evidence into notebook content. Those
behaviors require a separate explicit contract.

## Backend contract

All operations require a valid authenticated bearer session. The owner is
always taken from the authenticated principal; notebook payloads never accept
an owner or user identifier.

| Method | Path | Body | Result |
| --- | --- | --- | --- |
| GET | `/api/v1/notebooks` | none | Current user's notebooks, ordered by `updated_at DESC, notebook_id DESC` |
| POST | `/api/v1/notebooks` | `{title, content}` | Created notebook |
| GET | `/api/v1/notebooks/{notebook_id}` | none | Owned notebook or sanitized 404 |
| PATCH | `/api/v1/notebooks/{notebook_id}` | At least one of `title`, `content` | Updated notebook or sanitized 404 |
| DELETE | `/api/v1/notebooks/{notebook_id}` | none | 204 or sanitized 404 |

Titles are 1–256 characters and content is at most 100,000 characters. JSON
objects reject unknown fields. Returned identifiers and timestamps are
stable DTO fields: `notebook_id`, `title`, `content`, `created_at`, and
`updated_at`.

## Frontend contract

The routes are `/notebook` for the owned notebook index and
`/notebook/{notebook_id}` for a deep-linked editor. The index supports an
explicit new-notebook form. The editor supports explicit save and delete,
with loading, empty, error, and save-result states. Persistence always goes
through the centralized authenticated API client; localStorage is not used as
a substitute for backend persistence.

## Security and integration

Backend ownership checks are authoritative. A client cannot select another
owner. The UI renders notebook content only as text, does not expose tokens,
and does not fabricate citations, evidence, provenance, or research links.
