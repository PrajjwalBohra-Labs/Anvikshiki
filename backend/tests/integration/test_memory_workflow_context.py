from typing import Any, AsyncGenerator, Dict, Optional
from uuid import uuid4

import pytest
from sqlalchemy import delete

from backend.app.application.orchestration.research_workflow import ResearchWorkflowEngine
from backend.app.infrastructure.ai.local_model_adapter import BaseModelAdapter
from backend.app.infrastructure.database.models import (
    DurableGraphCheckpointModel,
    EpistemicPositionModel,
    UserModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine


@pytest.fixture
async def sqlite_schema():
    assert engine.dialect.name == "sqlite"
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


class CapturingLLMAdapter(BaseModelAdapter):
    def __init__(self) -> None:
        super().__init__(model_name="test-capturing-llm")
        self.prompt = ""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        self.prompt = prompt
        return {"content": "context captured", "model": self.model_name}

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        yield "context captured"


@pytest.mark.asyncio
async def test_persisted_epistemic_position_enters_workflow_as_separate_context(sqlite_schema) -> None:
    marker = uuid4().hex
    thread_id = f"memory-context-{marker}"
    user_id = f"memory-user-{marker}"
    adapter = CapturingLLMAdapter()

    async with AsyncSessionLocal() as session:
        user = UserModel(username=user_id)
        session.add(user)
        await session.flush()
        position = EpistemicPositionModel(
            user_id=user.id,
            claim_statement="The stored position is context, not source evidence.",
            position="tentative",
            confidence=0.7,
            supporting_evidence_payload=[],
            counterarguments_payload=[],
            status="tentative",
        )
        session.add(position)
        await session.commit()
        persisted_user_id = user.id

    workflow = ResearchWorkflowEngine(llm_adapter=adapter)
    result = await workflow.execute_research(
        query=f"{marker} memory context check",
        user_id=persisted_user_id,
        thread_id=thread_id,
    )

    assert result["final_response"] == "context captured"
    assert '"user_epistemic_positions"' in adapter.prompt
    assert "The stored position is context, not source evidence." in adapter.prompt
    assert '"passages": []' in adapter.prompt

    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(DurableGraphCheckpointModel).where(
                DurableGraphCheckpointModel.thread_id == thread_id
            )
        )
        await session.execute(delete(EpistemicPositionModel).where(EpistemicPositionModel.user_id == persisted_user_id))
        await session.execute(delete(UserModel).where(UserModel.id == persisted_user_id))
        await session.commit()
