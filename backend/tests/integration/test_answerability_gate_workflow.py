import pytest

from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter
from backend.app.infrastructure.database.models import DocumentModel, PassageModel, SourceModel, UserModel
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.domain.models.enums import SourceType


QUESTION = "How perceptions changes with time but the experience remains stationary?"


class MetadataOnlyLLM(BaseModelAdapter):
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 512, temperature: float = 0.7):
        return {
            "content": "The passages are from the Philosophy Institute and were published in 2026. [P1]",
            "model": self.model_name,
            "tokens_used": 20,
        }

    async def stream_generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 512, temperature: float = 0.7):
        yield ""


@pytest.fixture
async def reasoning_schema():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_exact_metadata_false_approval_is_blocked(monkeypatch, reasoning_schema):
    async with AsyncSessionLocal() as session:
        user = UserModel(username="answerability_gate_user")
        source = SourceModel(title="Temporal Experience Study", author="A. Scholar", source_type=SourceType.PRIMARY)
        session.add_all([user, source])
        await session.flush()
        document = DocumentModel(source_id=source.id, checksum_sha256="answerability-gate-document", mime_type="text/plain")
        session.add(document)
        await session.flush()
        passage = PassageModel(
            document_id=document.id,
            content="Perception changes as sensory conditions vary, while temporal retention connects successive experiences.",
        )
        session.add(passage)
        await session.commit()

        async def retrieve_evidence(self, query, domain=None, source_type_filter=None, source_id_filter=None, top_k=5, owner_id=None):
            return [{
                "passage_id": passage.id,
                "document_id": document.id,
                "source_id": source.id,
                "source_title": source.title,
                "author": source.author,
                "content": passage.content,
                "source_type": "PRIMARY",
                "page_number": None,
                "relevance_score": 1.0,
                "rank": 1,
            }]

        monkeypatch.setattr("backend.app.application.orchestration.research_workflow.HybridRetrievalService.retrieve_evidence", retrieve_evidence)
        engine_instance = ResearchWorkflowEngine(session, llm_adapter=MetadataOnlyLLM(model_name="metadata-test"))
        result = await engine_instance.execute_research(
            query=QUESTION,
            user_id=user.id,
            domain="Philosophy",
            thread_id="answerability-gate-thread",
            depth="deep",
        )

    assert result["validation_status"] == "BLOCKED_OR_DOWNGRADED"
    assert result["validation_details"]["answerability"]["relevance"] == "FAIL"
    assert result["validation_details"]["answerability"]["question_coverage"] == "FAIL"
    assert "Philosophy Institute" not in result["final_response"]
