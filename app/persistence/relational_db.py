"""
Relational storage layer (§23 relational DB) built on the §9 entity
schema. Stdlib sqlite3 only — zero compiled dependencies. This module
owns connections and table creation plus minimal create/read helpers;
full CRUD per entity belongs to the Application-layer services.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    _ensure_parent_dir(settings.database_path)
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        # Migration for pre-existing DBs created before the `sources`
        # column existed (fresh installs already get it from schema.sql).
        try:
            conn.execute("ALTER TABLE answers ADD COLUMN sources TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- Concepts ---

def create_concept(name: str, description: str = "") -> str:
    concept_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO concepts (id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (concept_id, name, description, now, now),
        )
    return concept_id


def get_concept(concept_id: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
    return dict(row) if row else None


# --- Documents ---

def create_document(
    title: str,
    file_path: str,
    content_hash: str,
    project_id: str | None = None,
    source_id: str | None = None,
) -> str:
    document_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO documents "
            "(id, project_id, source_id, title, file_path, content_hash, is_immutable, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (document_id, project_id, source_id, title, file_path, content_hash, now),
        )
    return document_id


def get_document(document_id: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
    return dict(row) if row else None


# --- Relationships (generic entity graph edges, §9) ---

def create_relationship(
    source_type: str, source_id: str, target_type: str, target_id: str, relationship_type: str
) -> str:
    relationship_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO relationships "
            "(id, source_type, source_id, target_type, target_id, relationship_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (relationship_id, source_type, source_id, target_type, target_id, relationship_type, now),
        )
    return relationship_id


def get_relationships_for(entity_type: str, entity_id: str) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM relationships WHERE "
            "(source_type = ? AND source_id = ?) OR (target_type = ? AND target_id = ?)",
            (entity_type, entity_id, entity_type, entity_id),
        ).fetchall()
    return [dict(row) for row in rows]


# --- Projects ---

def create_project(name: str, description: str = "", user_id: str | None = None) -> str:
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO projects (id, user_id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, user_id, name, description, now, now),
        )
    return project_id


def get_project(project_id: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    return dict(row) if row else None



# --- Memory records (backs the four persistent memory tiers, §10) ---

def create_memory_record(
    tier: str, content: str, scope_id: str | None = None, metadata: dict | None = None
) -> str:
    record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO memory_records (id, tier, scope_id, content, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (record_id, tier, scope_id, content, json.dumps(metadata or {}), now),
        )
    return record_id


def get_memory_record(record_id: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM memory_records WHERE id = ?", (record_id,)
        ).fetchone()
    return dict(row) if row else None


# --- Sessions (Session Engine, §11) ---

def create_session(user_id: str | None = None) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, started_at, status) VALUES (?, ?, ?, ?)",
            (session_id, user_id, now, "active"),
        )
    return session_id


def get_session(session_id: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


# --- Questions / Answers (turn persistence, §17 "every response is traceable") ---

def create_question(session_id: str, text: str) -> str:
    question_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO questions (id, session_id, conversation_id, text, created_at) "
            "VALUES (?, ?, NULL, ?, ?)",
            (question_id, session_id, text, now),
        )
    return question_id


def get_question(question_id: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    return dict(row) if row else None


def create_answer(
    question_id: str, text: str, confidence: float | None = None, sources: list[dict] | None = None
) -> str:
    answer_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO answers (id, question_id, text, confidence, sources, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (answer_id, question_id, text, confidence, json.dumps(sources or []), now),
        )
    return answer_id


def get_answer(answer_id: str) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM answers WHERE id = ?", (answer_id,)).fetchone()
    return dict(row) if row else None


# --- Settings (System Memory tier, §10) ---

def set_setting(key: str, value: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, now),
        )


def get_setting(key: str) -> str | None:
    with db_session() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


# --- Listing / browsing (§7 Frontend Responsibilities need real lists, not just by-id lookups) ---

def list_documents(project_id: str | None = None, limit: int = 50) -> list[dict]:
    with db_session() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM documents WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(row) for row in rows]


def list_concepts(limit: int = 50) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM concepts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def list_projects(limit: int = 50) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_conversation_history(session_id: str) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT q.id AS question_id, q.text AS question_text, q.created_at AS asked_at,
                   a.id AS answer_id, a.text AS answer_text, a.confidence AS confidence
            FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id
            WHERE q.session_id = ?
            ORDER BY q.created_at ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]



# --- Session summaries (real counts only -- §10 "Sessions as knowledge objects") ---

def get_session_summary(session_id: str) -> dict:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT q.id AS question_id, a.id AS answer_id, a.sources AS sources
            FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id
            WHERE q.session_id = ?
            """,
            (session_id,),
        ).fetchall()

    message_count = len(rows)
    verified_count = 0
    sources_seen: dict[str, dict] = {}
    concepts_seen: set[str] = set()

    for row in rows:
        if row["answer_id"] is not None:
            verified_count += 1
        if row["sources"]:
            for source in json.loads(row["sources"]):
                key = source.get("document_id") or source.get("url") or source.get("title")
                if key:
                    sources_seen[key] = source
                if source.get("concept_id"):
                    concepts_seen.add(source["concept_id"])

    return {
        "message_count": message_count,
        "verified_count": verified_count,
        "source_count": len(sources_seen),
        "concept_count": len(concepts_seen),
    }


# --- Concept graph (real nodes + real edges only -- §8) ---

def get_concept_graph() -> dict:
    with db_session() as conn:
        concept_rows = conn.execute("SELECT * FROM concepts").fetchall()
        edge_rows = conn.execute(
            "SELECT * FROM relationships WHERE source_type = 'concept' OR target_type = 'concept'"
        ).fetchall()
    return {
        "nodes": [dict(row) for row in concept_rows],
        "edges": [dict(row) for row in edge_rows],
    }
