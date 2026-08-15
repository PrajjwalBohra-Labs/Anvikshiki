from app.services.knowledge.comparison import compare_chunks
from app.services.knowledge.retrieval import RetrievedChunk


def _chunk(doc_id, title, text, score=0.8):
    return RetrievedChunk(
        chunk_id=f"c-{doc_id}", document_id=doc_id, document_title=title,
        chunk_text=text, score=score, semantic_score=score, keyword_score=0.0,
        metadata={}, source_type="local",
    )


def test_identical_content_from_two_sources_is_agreement():
    chunks = [
        _chunk("d1", "Doc A", "the sky is blue and clear today"),
        _chunk("d2", "Doc B", "the sky is blue and clear today"),
    ]
    comparisons = compare_chunks(chunks)
    assert len(comparisons) == 1
    assert comparisons[0]["relation"] == "agreement"


def test_unrelated_content_from_two_sources_is_divergence():
    chunks = [
        _chunk("d1", "Doc A", "quantum mechanics governs subatomic particles"),
        _chunk("d2", "Doc B", "sourdough bread requires a live starter culture"),
    ]
    comparisons = compare_chunks(chunks)
    assert len(comparisons) == 1
    assert comparisons[0]["relation"] == "divergence"


def test_single_source_produces_no_comparisons():
    chunks = [_chunk("d1", "Doc A", "some text")]
    assert compare_chunks(chunks) == []
