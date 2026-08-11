-- Relational schema for Anvikshiki (§9 entities + §23 tables).
-- Pure SQLite DDL, stdlib sqlite3 only. IDs are TEXT (uuid4 strings)
-- so entities can be referenced consistently across tables and,
-- later, across services without leaking an autoincrement scheme.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    project_id TEXT REFERENCES projects(id),
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS definitions (
    id TEXT PRIMARY KEY,
    concept_id TEXT REFERENCES concepts(id),
    text TEXT NOT NULL,
    source_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    url TEXT,
    source_type TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    source_id TEXT REFERENCES sources(id),
    title TEXT NOT NULL,
    file_path TEXT,
    content_hash TEXT,
    is_immutable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    heading TEXT,
    order_index INTEGER NOT NULL,
    content TEXT
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    concept_id TEXT REFERENCES concepts(id),
    text TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    claim_id TEXT REFERENCES claims(id),
    document_id TEXT REFERENCES documents(id),
    section_id TEXT REFERENCES sections(id),
    excerpt TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS arguments (
    id TEXT PRIMARY KEY,
    claim_id TEXT REFERENCES claims(id),
    structure_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    conversation_id TEXT REFERENCES conversations(id),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
    id TEXT PRIMARY KEY,
    question_id TEXT REFERENCES questions(id),
    text TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS examples (
    id TEXT PRIMARY KEY,
    concept_id TEXT REFERENCES concepts(id),
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS counterexamples (
    id TEXT PRIMARY KEY,
    concept_id TEXT REFERENCES concepts(id),
    text TEXT NOT NULL
);

-- Generic entity graph edges implementing the §9 Relationship entity
-- and relationship types: requires, supports, contradicts, extends,
-- contains, references, belongs_to, derived_from, related_to.
CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS annotations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- "references" is a SQL keyword; always double-quote the identifier.
CREATE TABLE IF NOT EXISTS "references" (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    citation_text TEXT,
    url TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Backs all four persistent memory tiers (§10): Concept, Project,
-- Research, System. Deliberately separate from the concepts/projects/
-- annotations/settings tables -- those hold domain entities (§9),
-- this holds memory-tier records about them.
CREATE TABLE IF NOT EXISTS memory_records (
    id TEXT PRIMARY KEY,
    tier TEXT NOT NULL,
    scope_id TEXT,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);
