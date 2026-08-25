import pytest
import json
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from backend.app.main import app
from backend.app.infrastructure.database.session import engine, Base, AsyncSessionLocal
from backend.app.infrastructure.database.models import (
    UserModel, SourceModel, DocumentModel, PassageModel, DurableGraphCheckpointModel
)
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter
from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.application.use_cases.hybrid_retrieval import HybridRetrievalService

class DynamicMockLLMAdapter(BaseModelAdapter):
    """Isolated LLM test adapter matching production BaseModelAdapter contract."""
    def __init__(self):
        super().__init__(model_name="mock-scholar-7b")
        self.invocation_count = 0

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 512, temperature: float = 0.7):
        self.invocation_count += 1
        return {
            "content": f"Synthesized analysis based on verified textual evidence for prompt: '{prompt[:50]}...'",
            "model": self.model_name,
            "tokens_used": 42
        }

    async def stream_generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 512, temperature: float = 0.7):
        yield "Chunk"

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_full_production_research_execution(setup_test_env):
    async with AsyncSessionLocal() as session:
        # 1. Seed Real Database Records
        user = UserModel(username="inquiry_researcher")
        session.add(user)
        await session.flush()

        source = SourceModel(title="Nyāya Sūtras", author="Akṣapāda Gotama", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        doc = DocumentModel(source_id=source.id, checksum_sha256="sha_nyaya_real_999", mime_type="text/plain")
        session.add(doc)
        await session.flush()

        passage = PassageModel(
            document_id=doc.id,
            page_number=4,
            content="Pratyakṣa (direct perception) is non-erroneous cognition arising from sense-object contact."
        )
        session.add(passage)
        await session.commit()

        # 2. Test Real Hybrid Retrieval
        retrieval_service = HybridRetrievalService(session)
        evidence = await retrieval_service.retrieve_evidence("perception", domain="Epistemology")
        assert len(evidence) > 0
        assert evidence[0]["passage_id"] == passage.id
        assert evidence[0]["source_title"] == "Nyāya Sūtras"

        # 3. Test Dynamic LangGraph Execution with LLM Adapter
        mock_llm = DynamicMockLLMAdapter()
        workflow_engine = ResearchWorkflowEngine(session, llm_adapter=mock_llm)
        thread_id = "test_thread_scholarly_001"

        result = await workflow_engine.execute_research(
            query="What defines valid perception in Nyaya?",
            user_id=user.id,
            domain="Epistemology",
            thread_id=thread_id
        )

        assert result["validation_status"] in ["APPROVED", "BLOCKED_OR_DOWNGRADED"]
        assert len(result["retrieved_passages"]) > 0
        assert result["retrieved_passages"][0]["passage_id"] == passage.id
        assert len(result["extracted_claims"]) > 0
        assert result["extracted_claims"][0]["passage_id"] == passage.id
        assert len(result["objections"]) > 0
        assert mock_llm.invocation_count == 1
        assert "Synthesized analysis" in result["final_response"]

        # 4. Test Durable LangGraph Checkpointer Persistence
        chk_stmt = select(DurableGraphCheckpointModel).where(DurableGraphCheckpointModel.thread_id == thread_id)
        chk_res = await session.execute(chk_stmt)
        persisted_checkpoints = chk_res.scalars().all()
        assert len(persisted_checkpoints) > 0

        # Simulate backend process restart with fresh engine instance
        recreated_engine = ResearchWorkflowEngine(session, llm_adapter=mock_llm)
        restored_tuple = await recreated_engine.checkpointer.aget_tuple({"configurable": {"thread_id": thread_id}})
        assert restored_tuple is not None
        assert restored_tuple.checkpoint["id"] == persisted_checkpoints[-1].checkpoint_id

        # 5. Test Genuine Real-Time SSE Streaming
        events_received = []
        async for event in workflow_engine.stream_research_events("Perception in Nyaya", user.id, thread_id="stream_thread_01"):
            events_received.append(event)

        event_names = [e["event"] for e in events_received]
        assert "research_started" in event_names
        assert "coordinator_event" in event_names
        assert "retrieval_event" in event_names
        assert "specialist_analysis_event" in event_names
        assert "challenger_event" in event_names
        assert "validator_event" in event_names
        assert "research_completed" in event_names

        # 6. Test FastAPI HTTP & SSE End-to-End
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            sse_http_res = await client.post(
                "/api/v1/research/run/stream",
                json={"user_id": user.id, "query": "What defines valid perception?"}
            )
            assert sse_http_res.status_code == 200
            assert "text/event-stream" in sse_http_res.headers["content-type"]
            assert "research_started" in sse_http_res.text
            assert "research_completed" in sse_http_res.text
