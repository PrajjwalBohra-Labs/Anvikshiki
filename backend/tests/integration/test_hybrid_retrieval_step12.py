import asyncio
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import RuntimeProfile, settings
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.infrastructure.llm.embedding_client import LocalEmbeddingClient
from backend.app.infrastructure.rag.lexical_retriever import ScoredPassage
from backend.app.infrastructure.rag.reranker import (
    AdvancedRetriever,
    LocalRerankerClient,
)
from backend.app.infrastructure.rag.retriever import HybridRetriever, RetrievalOutcome
from backend.app.main import app


def _passage(identifier: str, order: int, content: str = "documentary text"):
    return SimpleNamespace(id=identifier, passage_order=order, content=content)


@pytest.fixture
async def api_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_search_api_selects_all_retrieval_modes(api_database):
    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Mode test source")
        session.add(source)
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256="step12-mode-checksum",
            mime_type="text/plain",
        )
        session.add(document)
        await session.flush()
        passage = PassageModel(
            document_id=document.id,
            content="Direct perception is a pratyaksha example.",
            embedding=await LocalEmbeddingClient().get_embedding("direct perception"),
            page_number=1,
            passage_order=0,
        )
        session.add(passage)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for mode in ("lexical", "semantic", "hybrid"):
            response = await client.get(
                "/api/v1/search/",
                params={"query": "direct perception", "retrieval": mode},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["total_results"] == 1
            result = payload["results"][0]
            assert result["retrieval_method"] == mode
            assert result["passage_id"] == passage.id
            if mode == "lexical":
                assert result["lexical_score"] is not None
            elif mode == "semantic":
                assert result["semantic_score"] is not None
            else:
                assert result["lexical_score"] is not None
                assert result["semantic_score"] is not None
                assert result["hybrid_score"] is not None
                assert result["rerank_score"] is not None


@pytest.mark.asyncio
async def test_hybrid_unions_candidates_and_retains_branch_contributions():
    first = _passage("passage-a", 0, "anumana evidence")
    lexical_only = _passage("passage-b", 1, "lexical evidence")
    semantic_only = _passage("passage-c", 2, "semantic evidence")
    retriever = HybridRetriever(session=None, embedding_client=object())

    async def lexical(*args, **kwargs):
        return RetrievalOutcome(
            results=[
                ScoredPassage(first, 4.0, retrieval_method="lexical", lexical_score=4.0),
                ScoredPassage(lexical_only, 2.0, retrieval_method="lexical", lexical_score=2.0),
            ],
            lexical_count=2,
        )

    async def semantic(*args, **kwargs):
        return RetrievalOutcome(
            results=[
                ScoredPassage(first, 0.9, retrieval_method="semantic", semantic_score=0.9),
                ScoredPassage(semantic_only, 0.8, retrieval_method="semantic", semantic_score=0.8),
            ],
            semantic_count=2,
        )

    retriever.lexical_retrieve = lexical
    retriever.semantic_retrieve = semantic
    outcome = await retriever.hybrid_retrieve_with_metadata(
        "anumana", top_k=3, rrf_k=1
    )

    assert outcome.status == "complete"
    assert [item.passage.id for item in outcome.results] == [
        "passage-a",
        "passage-b",
        "passage-c",
    ]
    assert len({item.passage.id for item in outcome.results}) == 3
    both = outcome.results[0]
    assert both.lexical_score == 4.0
    assert both.semantic_score == 0.9
    assert both.lexical_rank == 1
    assert both.semantic_rank == 1
    assert both.normalized_lexical_score == pytest.approx(1.0)
    assert both.normalized_semantic_score == pytest.approx(1.0)
    assert both.hybrid_score == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_hybrid_ties_use_stable_passage_order_and_surviving_branch():
    early = _passage("z-id", 0)
    late = _passage("a-id", 1)
    retriever = HybridRetriever(session=None, embedding_client=object())

    async def lexical(*args, **kwargs):
        return RetrievalOutcome(results=[ScoredPassage(early, 1.0)])

    async def semantic(*args, **kwargs):
        return RetrievalOutcome(results=[ScoredPassage(late, 1.0)])

    retriever.lexical_retrieve = lexical
    retriever.semantic_retrieve = semantic
    outcome = await retriever.hybrid_retrieve_with_metadata("query", top_k=2, rrf_k=60)
    assert [item.passage.id for item in outcome.results] == ["z-id", "a-id"]

    async def failed_semantic(*args, **kwargs):
        raise RuntimeError("semantic service unavailable")

    retriever.semantic_retrieve = failed_semantic
    degraded = await retriever.hybrid_retrieve_with_metadata("query", top_k=2)
    assert degraded.status == "degraded"
    assert [item.passage.id for item in degraded.results] == ["z-id"]
    assert degraded.warnings == ["semantic retrieval unavailable (RuntimeError)."]


@pytest.mark.asyncio
async def test_both_hybrid_branches_failed_returns_no_fabricated_candidates():
    retriever = HybridRetriever(session=None, embedding_client=object())

    async def failed_lexical(*args, **kwargs):
        raise RuntimeError("database unavailable")

    async def failed_semantic(*args, **kwargs):
        raise RuntimeError("model unavailable")

    retriever.lexical_retrieve = failed_lexical
    retriever.semantic_retrieve = failed_semantic
    outcome = await retriever.hybrid_retrieve_with_metadata("query", top_k=2)
    assert outcome.status == "failed"
    assert outcome.results == []
    assert len(outcome.warnings) == 2


@pytest.mark.asyncio
async def test_reranker_preserves_hybrid_scores(monkeypatch):
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", RuntimeProfile.TEST)
    passage = _passage("passage-a", 0, "anumana is inference")
    candidate = ScoredPassage(
        passage,
        score=1.4,
        retrieval_method="hybrid",
        lexical_score=3.0,
        semantic_score=0.8,
        normalized_lexical_score=1.0,
        normalized_semantic_score=0.9,
        hybrid_score=1.4,
    )
    results = await LocalRerankerClient().rerank("anumana", [candidate], top_k=1)
    assert results[0].rerank_score == results[0].score
    assert results[0].hybrid_score == 1.4
    assert results[0].lexical_score == 3.0
    assert results[0].semantic_score == 0.8


@pytest.mark.asyncio
async def test_reranker_failure_returns_fused_candidates_as_degraded():
    passage = _passage("passage-a", 0, "anumana is inference")
    fused = ScoredPassage(
        passage,
        score=1.0,
        retrieval_method="hybrid",
        hybrid_score=1.0,
    )

    class BrokenReranker:
        async def rerank(self, *args, **kwargs):
            raise RuntimeError("reranker unavailable")

    retriever = AdvancedRetriever(
        session=None, embedding_client=object(), reranker_client=BrokenReranker()
    )

    async def candidates(*args, **kwargs):
        return RetrievalOutcome(results=[fused])

    retriever.hybrid_retrieve_with_metadata = candidates
    outcome = await retriever.retrieve_and_rerank_with_metadata("anumana", top_k=1)
    assert outcome.status == "degraded"
    assert outcome.results[0].hybrid_score == 1.0
    assert outcome.results[0].rerank_score is None
    assert outcome.warnings == ["reranker retrieval unavailable (RuntimeError)."]


@pytest.mark.asyncio
async def test_reranker_timeout_is_degraded_without_fabricated_score():
    passage = _passage("passage-timeout", 0, "anumana is inference")
    fused = ScoredPassage(
        passage, score=1.0, retrieval_method="hybrid", hybrid_score=1.0
    )

    class TimedOutReranker:
        async def rerank(self, *args, **kwargs):
            raise asyncio.TimeoutError()

    retriever = AdvancedRetriever(
        session=None, embedding_client=object(), reranker_client=TimedOutReranker()
    )

    async def candidates(*args, **kwargs):
        return RetrievalOutcome(results=[fused])

    retriever.hybrid_retrieve_with_metadata = candidates
    outcome = await retriever.retrieve_and_rerank_with_metadata("anumana", top_k=1)
    assert outcome.status == "degraded"
    assert outcome.results[0].rerank_score is None
    assert "TimeoutError" in outcome.warnings[0]


@pytest.mark.asyncio
async def test_reranker_can_be_disabled_without_losing_fused_candidates(monkeypatch):
    monkeypatch.setattr(settings, "RERANKER_ENABLED", False)
    monkeypatch.setattr(settings, "RERANKER_CANDIDATE_MULTIPLIER", 3)
    passages = [_passage(f"passage-{index}", index) for index in range(3)]
    fused = [ScoredPassage(item, 1.0, retrieval_method="hybrid", hybrid_score=1.0) for item in passages]
    requested_pool = []

    class FailingReranker:
        async def rerank(self, *args, **kwargs):
            raise AssertionError("disabled reranker must not be called")

    retriever = AdvancedRetriever(
        session=None, embedding_client=object(), reranker_client=FailingReranker()
    )

    async def candidates(*args, **kwargs):
        requested_pool.append(kwargs["top_k"])
        return RetrievalOutcome(results=fused)

    retriever.hybrid_retrieve_with_metadata = candidates
    outcome = await retriever.retrieve_and_rerank_with_metadata("query", top_k=1)
    assert requested_pool == [3]
    assert outcome.status == "complete"
    assert [item.passage.id for item in outcome.results] == ["passage-0"]
    assert outcome.results[0].rerank_score is None
    assert outcome.results[0].hybrid_score == 1.0
