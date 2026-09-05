# Step 69 — Backup / Recovery Contract

Anvikshiki uses PostgreSQL and pgvector as its authoritative persistent store.
Step 69 provides a local administrative CLI using PostgreSQL-native custom
format dumps. It is not exposed through FastAPI and is not available to normal
application users.

## Scope

The dump covers the complete database schema and data, including users and
sessions, sources, documents, passages, vectors, research runs and events,
claims, evidence, provenance graph records, memory records, and background
jobs. PostgreSQL indexes, constraints, triggers, and the `vector` extension are
included by the native dump/schema.

## Commands

From the repository root, with PostgreSQL client tools available locally or in
the existing Compose container:

```powershell
.venv\Scripts\python.exe -m backend.tools.database_backup backup `
  --database anvikshiki_db --docker-container anvikshiki-postgres-1 `
  --output-dir backups --label local-2026-09-02

.venv\Scripts\python.exe -m backend.tools.database_backup validate `
  --backup backups\local-2026-09-02.dump --docker-container anvikshiki-postgres-1

.venv\Scripts\python.exe -m backend.tools.database_backup restore `
  --database anvikshiki_recovery --backup backups\local-2026-09-02.dump `
  --docker-container anvikshiki-postgres-1 --create-target
```

Database names and backup labels are strictly validated. The CLI never accepts
arbitrary shell commands or executable paths, and it does not print database
URLs or credentials. A SHA-256 sidecar is written beside each dump.

## Migration and recovery

The source schema is at Alembic revision `0014_background_jobs`. A recovery
database is created empty, receives the native dump, and is verified with
`pg_restore --list`, PostgreSQL queries, and application startup. The restored
database must be treated as being at the dumped migration revision; subsequent
application migrations can then be applied normally.

## Failure behavior and security

Empty, missing, invalid, or failed artifacts return non-zero status and do not
report success. Temporary container copies are removed after validation or
restore. Backup files are sensitive local administrative artifacts and are
ignored by the repository's existing `data/` policy; they must not be
committed. Credentials, bearer tokens, private user content, and raw database
URLs are not placed in filenames, manifests, or logs.
