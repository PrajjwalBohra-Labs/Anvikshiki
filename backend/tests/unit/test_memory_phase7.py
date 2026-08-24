import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.infrastructure.database.session import Base
from backend.app.application.use_cases.memory_service import MemoryService

@pytest.fixture
async def async_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await test_engine.dispose()

@pytest.mark.asyncio
async def test_epistemic_memory_lifecycle(async_db_session: AsyncSession):
    memory = MemoryService(async_db_session)
    user_id = "researcher_1"
    claim = "Pratyaksha is inherently error-free in pristine sensory conditions."

    # 1. Record Initial Epistemic Position
    initial_record = await memory.record_or_update_epistemic_position(
        user_id=user_id,
        claim_statement=claim,
        position="tentative_acceptance",
        confidence=0.85,
        supporting_evidence=["Direct sensory contact without impairment"],
        status="under_investigation"
    )
    await async_db_session.commit()
    assert initial_record.id is not None
    assert initial_record.user_position == "tentative_acceptance"
    assert initial_record.confidence == 0.85

    # 2. Update Position After Counterarguments Explored
    updated_record = await memory.record_or_update_epistemic_position(
        user_id=user_id,
        claim_statement=claim,
        position="qualified_skepticism",
        confidence=0.55,
        counterarguments=["Optical illusions and cognitive top-down biases demonstrate inherent perceptual fallibility."],
        status="active_debate"
    )
    await async_db_session.commit()
    assert updated_record.id == initial_record.id
    assert updated_record.user_position == "qualified_skepticism"
    assert updated_record.confidence == 0.55

    # 3. Retrieve Epistemic History
    history = await memory.get_user_epistemic_history(user_id)
    assert len(history) == 1
    assert history[0].status == "active_debate"

@pytest.mark.asyncio
async def test_cognitive_observation_recording(async_db_session: AsyncSession):
    memory = MemoryService(async_db_session)
    obs = await memory.record_cognitive_observation(
        user_id="researcher_1",
        pattern_name="CORRELATION_CAUSATION_CONFLATION",
        description="User assumed functional MRI correlation proves philosophical physicalism directly.",
        evidence_dialogue_turn="Turn 4: 'fMRI lights up, so thoughts are purely physical.'",
        confidence=0.8
    )
    await async_db_session.commit()
    assert obs.id is not None
    assert obs.pattern_name == "CORRELATION_CAUSATION_CONFLATION"