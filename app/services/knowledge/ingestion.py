"""
Document ingestion pipeline (§19 Document Ingestion):
Import -> Validation -> Parsing -> Cleaning -> Normalization ->
Chunking -> Metadata extraction -> Embedding -> Indexing -> Storage.

Raw documents are immutable once imported -- the file_store write
below is the only place original bytes are ever written.

Parsers are registered by file extension so new formats can be added
later without touching the pipeline itself (§33 Extensibility).

Publishes DocumentImported once per document and EmbeddingCreated
once per chunk (§25 Events). Clears the retrieval cache at the end
(§26 "cache invalidation occurs on document updates") -- coarse but
correct: any cached query result could now be stale once new chunks
exist.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from app.infrastructure.cache import retrieval_cache
from app.infrastructure.event_bus import EventBus, EventName, get_event_bus
from app.infrastructure.llm_adapter import LLMAdapter, get_llm_adapter
from app.persistence import file_store, relational_db, vector_store

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024  # 20 MB sanity limit, not a spec number
CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150


class IngestionError(Exception):
    """Raised when a document fails validation and cannot be ingested."""


@dataclass
class IngestedChunk:
    text: str
    chunk_index: int
    char_start: int
    char_end: int


@dataclass
class IngestionResult:
    document_id: str
    concept_id: str
    file_path: str
    chunk_ids: list[str] = field(default_factory=list)
    chunk_count: int = 0


def _parse_text(raw_bytes: bytes) -> str:
    return raw_bytes.decode("utf-8", errors="replace")


_PARSERS = {
    ".txt": _parse_text,
    ".md": _parse_text,
}


def _parser_for(filename: str):
    for ext, parser in _PARSERS.items():
        if filename.lower().endswith(ext):
            return parser
    raise IngestionError(f"No parser registered for {filename!r}. Supported: {list(_PARSERS)}")


def _validate(filename: str, raw_bytes: bytes) -> None:
    if not raw_bytes:
        raise IngestionError("Document is empty")
    if len(raw_bytes) > MAX_DOCUMENT_BYTES:
        raise IngestionError(f"Document exceeds max size of {MAX_DOCUMENT_BYTES} bytes")
    _parser_for(filename)


def _clean_and_normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list[IngestedChunk]:
    if not text:
        return []

    chunks: list[IngestedChunk] = []
    start = 0
    index = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(
            IngestedChunk(text=text[start:end], chunk_index=index, char_start=start, char_end=end)
        )
        index += 1
        if end >= text_length:
            break
        start = end - overlap

    return chunks


def ingest_document(
    filename: str,
    raw_bytes: bytes,
    title: str | None = None,
    project_id: str | None = None,
    category: str = "notes",
    llm_adapter: LLMAdapter | None = None,
    event_bus: EventBus | None = None,
) -> IngestionResult:
    """Runs the full §19 ingestion pipeline for one document."""

    llm_adapter = llm_adapter or get_llm_adapter()
    event_bus = event_bus or get_event_bus()

    _validate(filename, raw_bytes)
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    file_path = file_store.save_file(category, filename, raw_bytes)

    raw_text = _parser_for(filename)(raw_bytes)
    clean_text = _clean_and_normalize(raw_text)
    if not clean_text:
        raise IngestionError("Document contains no extractable text")

    document_id = relational_db.create_document(
        title=title or filename, file_path=file_path, content_hash=content_hash, project_id=project_id
    )

    concept_id = relational_db.create_concept(
        name=title or filename, description=f"Concept derived from document '{title or filename}'"
    )
    relational_db.create_relationship(
        source_type="concept", source_id=concept_id, target_type="document",
        target_id=document_id, relationship_type="derived_from",
    )

    event_bus.publish(EventName.DOCUMENT_IMPORTED, {"document_id": document_id, "title": title or filename})

    chunks = _chunk_text(clean_text)

    chunk_ids: list[str] = []
    for chunk in chunks:
        embedding = llm_adapter.embed(chunk.text)
        chunk_id = vector_store.insert_embedding(
            document_id=document_id,
            chunk_text=chunk.text,
            embedding=embedding,
            metadata={
                "chunk_index": chunk.chunk_index,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "concept_id": concept_id,
            },
        )
        chunk_ids.append(chunk_id)
        event_bus.publish(EventName.EMBEDDING_CREATED, {"chunk_id": chunk_id, "document_id": document_id})

    retrieval_cache.clear()  # §26: cache invalidation on document updates

    return IngestionResult(
        document_id=document_id,
        concept_id=concept_id,
        file_path=file_path,
        chunk_ids=chunk_ids,
        chunk_count=len(chunk_ids),
    )
