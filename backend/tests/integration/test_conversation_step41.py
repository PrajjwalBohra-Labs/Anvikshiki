import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import UserModel, ResearchRunModel
from backend.app.application.use_cases.conversation_service import ConversationService

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_conversation_persistence_and_context_linking(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup prerequisite user and research run
        user = UserModel(username="scholar_one")
        session.add(user)
        await session.flush()

        run = ResearchRunModel(query="What is epistemology?", status="COMPLETED")
        session.add(run)
        await session.commit()

        service = ConversationService(session)

        # 2. Create Conversation and add research/citation-linked message
        conv = await service.create_conversation(user_id=user.id, title="Epistemological Inquiry")
        assert conv.id is not None

        msg = await service.add_message(
            conversation_id=conv.id,
            role="assistant",
            content="Epistemology investigates the criteria of valid knowledge.",
            research_run_id=run.id,
            citations_payload=[{"passage_id": "pass_123", "source": "Nyaya Sutra"}]
        )
        assert msg.id is not None
        assert msg.research_run_id == run.id
        assert len(msg.citations_payload) == 1

        # 3. Retrieve conversation history
        history = await service.get_conversation_history(conv.id)
        assert history["title"] == "Epistemological Inquiry"
        assert len(history["messages"]) == 1
        assert history["messages"][0]["research_run_id"] == run.id
        assert history["messages"][0]["citations"][0]["source"] == "Nyaya Sutra"

        # 4. Test streaming generator support
        chunks = []
        async for chunk in service.stream_message_response("Hello streaming dialogue!", chunk_size=5):
            chunks.append(chunk)
        assert len(chunks) > 1
        assert "".join(chunks) == "Hello streaming dialogue!"