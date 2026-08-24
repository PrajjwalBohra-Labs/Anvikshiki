import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from backend.app.main import app
from backend.app.infrastructure.database.session import engine, Base, AsyncSessionLocal
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel, ClaimModel
from backend.app.domain.models.enums import SourceType
from backend.app.application.use_cases.document_ingestion import DocumentIngestionService
from backend.app.application.use_cases.hybrid_retrieval import HybridRetrievalService
from backend.app.application.use_cases.claim_extraction_service import ClaimExtractionService
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter
from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine

class ProductionTestLLMAdapter(BaseModelAdapter):
    def __init__(self):
        super().__init__(model_name="test-qwen2.5-7b")
        self.calls = 0

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 512, temperature: float = 0.7):
        self.calls += 1
        return {
            "content": f"Verified scholarly synthesis: Inquiry grounded in primary source evidence. Prompt: {prompt[:40]}...",
            "model": self.model_name
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
async def test_full_final_pipeline_e2e(setup_test_env):
    async with AsyncSessionLocal() as session:
        # 1. Ingest Raw Source -> Passages -> Auto-Vector Embeddings
        source = SourceModel(title="Nyāya Sūtras", author="Gotama", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        ingest_svc = DocumentIngestionService(session)
        doc = await ingest_svc.ingest_document(
            source_id=source.id,
            content="Perceptual knowledge is non-erroneous cognition produced through sensory contact with an object.",
            filename="nyaya_sutra.txt"
        )
        assert doc.id is not None

        # 2. Hybrid Retrieval with Cross-Encoder Rerank
        retrieval_svc = HybridRetrievalService(session)
        evidence = await retrieval_svc.retrieve_evidence("sensory contact perception", top_k=1)
        assert len(evidence) == 1
        assert "sensory contact" in evidence[0]["content"]
        assert evidence[0]["source_title"] == "Nyāya Sūtras"
        assert evidence[0]["embedding_model"] == "all-MiniLM-L6-v2@v1.0"

        # 3. Structured Claim Extraction & Provenance Linkage
        claim_svc = ClaimExtractionService(session)
        claims = await claim_svc.extract_claims_from_passage(
            passage_id=evidence[0]["passage_id"],
            passage_content=evidence[0]["content"],
            source_title=evidence[0]["source_title"],
            source_type=evidence[0]["source_type"]
        )
        assert len(claims) == 1
        assert claims[0].claim_type.name == "DIRECT_SOURCE_CLAIM"
        assert claims[0].provenance_id == evidence[0]["passage_id"]

        # 4. Live LangGraph Research Workflow Execution with Local LLM Adapter
        test_llm = ProductionTestLLMAdapter()
        engine_inst = ResearchWorkflowEngine(session_or_factory=AsyncSessionLocal, llm_adapter=test_llm)
        run_res = await engine_inst.execute_research("Perception validity in Indian epistemology", "user_101")
        assert run_res["validation_status"] in ["APPROVED", "BLOCKED_OR_DOWNGRADED"]
        assert len(run_res["retrieved_passages"]) > 0
        assert test_llm.calls == 1

        # 5. Live SSE Streaming & Active Health Check via FastAPI
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health_res = await client.get("/health")
            assert health_res.status_code == 200
            assert health_res.json()["status"] in ["healthy", "degraded"]

            sse_res = await client.post(
                "/api/v1/research/run/stream",
                json={"user_id": "user_101", "query": "Perception validity in Indian epistemology"}
            )
            assert sse_res.status_code == 200
            assert "text/event-stream" in sse_res.headers["content-type"]
            assert "research_started" in sse_res.text
            assert "research_completed" in sse_res.text