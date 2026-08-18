import pytest

from app.infrastructure.llm_adapter import LLMAdapter
from app.persistence import relational_db, vector_store
from app.services.conversation.conversation_controller import handle_message
from app.services.memory.memory_engine import MemoryEngine


class GroundedAdapter(LLMAdapter):
    def generate(self, prompt, **kwargs):
        return "[Doc A] a grounded answer."

    def stream(self, prompt, **kwargs):
        yield self.generate(prompt)

    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def summarize(self, text, **kwargs):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _init_stores():
    relational_db.init_db()
    vector_store.init_vector_store()


def test_session_summary_counts_are_real_and_accurate():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    concept_id = relational_db.create_concept("Concept A", "desc")
    vector_store.insert_embedding(
        document_id, "a grounded fact.", [1.0, 0.0, 0.0], metadata={"concept_id": concept_id}
    )

    result = handle_message(
        "tell me the grounded fact", llm_adapter=GroundedAdapter(), memory_engine=MemoryEngine()
    )

    summary = relational_db.get_session_summary(result.session_id)
    assert summary["message_count"] == 1
    assert summary["verified_count"] == 1
    assert summary["source_count"] == 1
    assert summary["concept_count"] == 1


def test_session_summary_reflects_undelivered_turns_as_unverified():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    vector_store.insert_embedding(document_id, "a fact.", [1.0, 0.0, 0.0])

    class BadCitationAdapter(GroundedAdapter):
        def generate(self, prompt, **kwargs):
            return "[Nonexistent Source] fabricated."

    result = handle_message(
        "tell me the fact", llm_adapter=BadCitationAdapter(), memory_engine=MemoryEngine()
    )

    summary = relational_db.get_session_summary(result.session_id)
    assert summary["message_count"] == 1
    assert summary["verified_count"] == 0  # not delivered -- no sources persisted


def test_concept_graph_returns_real_nodes_and_edges():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    concept_id = relational_db.create_concept("Concept A", "desc")
    relational_db.create_relationship(
        source_type="concept", source_id=concept_id, target_type="document",
        target_id=document_id, relationship_type="derived_from",
    )

    graph = relational_db.get_concept_graph()
    assert any(n["id"] == concept_id for n in graph["nodes"])
    assert any(e["source_id"] == concept_id and e["relationship_type"] == "derived_from" for e in graph["edges"])


def test_concept_graph_includes_document_node_referenced_by_edge():
    document_id = relational_db.create_document("Doc A", "path/a.txt", "hash")
    concept_id = relational_db.create_concept("Concept A", "desc")
    relational_db.create_relationship(
        source_type="concept", source_id=concept_id, target_type="document",
        target_id=document_id, relationship_type="derived_from",
    )
    graph = relational_db.get_concept_graph()
    document_nodes = [n for n in graph["nodes"] if n["node_type"] == "document"]
    assert any(n["id"] == document_id for n in document_nodes)
