import pytest

from backend.app.application.use_cases.argument_service import (
    ArgumentReconstructionService,
)
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import Base, engine


@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_argument_reconstruction_and_linkage(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup Source and Passage
        source = SourceModel(title="Nyaya Sutra", author="Gotama", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="arg_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(document_id=doc.id, content="Sound is produced and is non-eternal.")
        session.add(passage)
        await session.commit()

        # 2. Test Argument Reconstruction
        service = ArgumentReconstructionService(session)
        argument = await service.create_argument(
            title="Non-eternality of Sound",
            conclusion="Sound is non-eternal.",
            premises=[
                "Sound has origin.",
                "Whatever has origin is non-eternal, just like a pot."
            ],
            objections=[
                {"objection": "Sound is eternal as it is heard even after utterance.", "reply": "Hearing is the manifestation of existing sound, not its creation."}
            ],
            assumptions=["Perception is valid."]
        )

        assert argument.id is not None
        assert argument.title == "Non-eternality of Sound"

        # 3. Test Premise Evidence Linkage & Unsupported Premise Detection
        unsupported = await service.detect_unsupported_premises(argument.id)
        assert len(unsupported) == 2  # Initially both unsupported

        # Link first premise to passage
        premises_list = unsupported
        await service.link_premise_evidence(premises_list[0].id, passage.id)

        # Re-check unsupported premises
        remaining_unsupported = await service.detect_unsupported_premises(argument.id)
        assert len(remaining_unsupported) == 1

        # 4. Test Argument Serialization
        serialized = await service.serialize_argument(argument.id)
        assert serialized["conclusion"] == "Sound is non-eternal."
        assert len(serialized["premises"]) == 2
        assert len(serialized["objections"]) == 1
        assert len(serialized["assumptions"]) == 1