import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import file_store, relational_db, vector_store
from app.services.knowledge.ingestion import IngestionError, ingest_document


class FakeEmbeddingAdapter(LLMAdapter):
    """Deterministic fake — avoids depending on a live Ollama instance
    for the automated test suite. Real embeddings are exercised in the
    manual smoke test."""

    def generate(self, prompt, **kwargs):
        raise NotImplementedError

    def stream(self, prompt, **kwargs):
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        return [float(len(text) % 7), float(len(text) % 3), 1.0]

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


def test_ingest_document_creates_document_concept_and_chunks():
    content = ("Anvikshiki is a modular cognitive architecture. " * 40).encode("utf-8")
    result = ingest_document(
        "sample.txt", content, title="Sample Doc", llm_adapter=FakeEmbeddingAdapter()
    )

    assert result.chunk_count > 0
    assert len(result.chunk_ids) == result.chunk_count

    document = relational_db.get_document(result.document_id)
    assert document["title"] == "Sample Doc"

    concept = relational_db.get_concept(result.concept_id)
    assert concept["name"] == "Sample Doc"

    relationships = relational_db.get_relationships_for("concept", result.concept_id)
    assert any(r["relationship_type"] == "derived_from" for r in relationships)

    first_chunk = vector_store.get_embedding(result.chunk_ids[0])
    assert first_chunk is not None
    assert first_chunk["document_id"] == result.document_id


def test_raw_file_is_written_immutably():
    content = b"immutable content check"
    result = ingest_document("note.txt", content, llm_adapter=FakeEmbeddingAdapter())
    assert file_store.read_file(result.file_path) == content


def test_ingest_rejects_empty_document():
    with pytest.raises(IngestionError):
        ingest_document("empty.txt", b"", llm_adapter=FakeEmbeddingAdapter())


def test_ingest_rejects_unsupported_format():
    with pytest.raises(IngestionError):
        ingest_document("file.xyz", b"some content", llm_adapter=FakeEmbeddingAdapter())


def test_chunking_overlaps_and_covers_full_text():
    from app.services.knowledge.ingestion import _chunk_text

    text = "x" * 2500
    chunks = _chunk_text(text, chunk_size=1000, overlap=100)

    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == 2500
    assert chunks[1].char_start == chunks[0].char_end - 100
