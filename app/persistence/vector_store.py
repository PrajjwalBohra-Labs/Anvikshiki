"""
Vector store (§23): a plain SQLite table storing embeddings as JSON
arrays, with similarity search computed in pure Python. Deliberately
NOT Chroma/FAISS/pgvector — chroma-hnswlib has no prebuilt Windows
wheel and needs MSVC Build Tools to compile, which is exactly what
§4 "No Native Build Steps" and the Step-0 amendment rule out. This
store lives in its own SQLite file, separate from the relational DB,
so it can be swapped independently later (§17 replaceability).
"""

import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    chunk_text TEXT NOT NULL,
    embedding TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);
"""


def _ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    _ensure_parent_dir(settings.vector_store_path)
    conn = sqlite3.connect(settings.vector_store_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_vector_store() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_embedding(
    document_id: str,
    chunk_text: str,
    embedding: list[float],
    metadata: dict | None = None,
) -> str:
    chunk_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO chunk_embeddings "
            "(id, document_id, chunk_text, embedding, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                chunk_id,
                document_id,
                chunk_text,
                json.dumps(embedding),
                json.dumps(metadata or {}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return chunk_id


def get_embedding(chunk_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM chunk_embeddings WHERE id = ?", (chunk_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_dict(row) if row else None


def get_all_chunks() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM chunk_embeddings").fetchall()
    finally:
        conn.close()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "chunk_text": row["chunk_text"],
        "embedding": json.loads(row["embedding"]),
        "metadata": json.loads(row["metadata"]),
        "created_at": row["created_at"],
    }


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Embedding dimension mismatch")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Pure-Python cosine similarity ranking — no compiled ANN index."""
    scored = []
    for chunk in get_all_chunks():
        score = cosine_similarity(query_embedding, chunk["embedding"])
        scored.append({**chunk, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
