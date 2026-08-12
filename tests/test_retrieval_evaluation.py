"""
Retrieval Evaluation (§31). Unlike the correctness tests in
test_retrieval.py (does retrieve() behave correctly on toy input),
this measures retrieval QUALITY against a small labeled query set --
the kind of check that catches "ranking formula got quietly worse"
regressions that correctness tests alone wouldn't notice.
"""

import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.knowledge.retrieval import retrieve

MIN_ACCEPTABLE_ACCURACY = 0.8


class TopicEmbeddingAdapter(LLMAdapter):
    """Embeds toward whichever topic keyword the query contains --
    lets us build a genuinely discriminating labeled test set without
    a live Ollama instance."""

    _TOPIC_VECTORS = {
        "storage": [1.0, 0.0, 0.0, 0.0],
        "reasoning": [0.0, 1.0, 0.0, 0.0],
        "memory": [0.0, 0.0, 1.0, 0.0],
        "security": [0.0, 0.0, 0.0, 1.0],
    }

    def embed(self, text: str) -> list[float]:
        lowered = text.lower()
        for topic, vector in self._TOPIC_VECTORS.items():
            if topic in lowered:
                return vector
        return [0.25, 0.25, 0.25, 0.25]

    def generate(self, prompt, **kwargs):
        raise NotImplementedError

    def stream(self, prompt, **kwargs):
        raise NotImplementedError

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


@pytest.fixture
def labeled_corpus():
    adapter = TopicEmbeddingAdapter()
    docs = {}
    for topic, text in {
        "storage": "The relational store and vector store are both SQLite-backed for zero-compilation deployment.",
        "reasoning": "The reasoning engine implements the full pipeline from problem to conclusion without generating prose.",
        "memory": "Memory tiers split into in-process and persistent stores across seven distinct tiers.",
        "security": "API key authentication and rate limiting protect every endpoint except the health check.",
    }.items():
        doc_id = relational_db.create_document(f"{topic.title()} Doc", f"path/{topic}.txt", f"hash-{topic}")
        vector_store.insert_embedding(doc_id, text, adapter.embed(text))
        docs[topic] = doc_id
    return docs, adapter


LABELED_QUERIES = [
    ("How does storage work in this system?", "storage"),
    ("Explain the reasoning pipeline", "reasoning"),
    ("What are the memory tiers?", "memory"),
    ("How is the API secured?", "security"),
]


def test_retrieval_quality_meets_minimum_accuracy_on_labeled_queries(labeled_corpus):
    docs, adapter = labeled_corpus
    correct = 0

    for query, expected_topic in LABELED_QUERIES:
        results = retrieve(query, top_k=1, llm_adapter=adapter)
        if results and results[0].document_id == docs[expected_topic]:
            correct += 1

    accuracy = correct / len(LABELED_QUERIES)
    assert accuracy >= MIN_ACCEPTABLE_ACCURACY, (
        f"Retrieval accuracy {accuracy:.0%} fell below the {MIN_ACCEPTABLE_ACCURACY:.0%} floor "
        f"on the labeled query set -- likely a ranking regression."
    )
