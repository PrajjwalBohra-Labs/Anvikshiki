import pytest

from backend.app.application.use_cases.synthesis_validation_service import (
    SynthesisValidationService,
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
async def test_synthesis_validation_blocking_and_downgrading(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup valid passage reference
        source = SourceModel(title="Kavyadarsa", author="Dandin", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        doc = DocumentModel(source_id=source.id, checksum_sha256="synth_hash_111", mime_type="text/plain")
        session.add(doc)
        await session.flush()

        passage = PassageModel(document_id=doc.id, page_number=10, content="Poetic speech is adorned by figures of sound and sense.")
        session.add(passage)
        await session.commit()

        # 2. Run Synthesis Validation Service
        validator = SynthesisValidationService(session)

        # Test case including a valid claim, an overclaimed high-confidence statement, and a fabricated citation
        claims_input = [
            {
                "statement": "Poetry utilizes aesthetic figures of sense.",
                "passage_id": passage.id,
                "confidence": 0.90
            },
            {
                "statement": "This is an absolute and irrefutable universal truth of all literature.",
                "passage_id": passage.id,
                "confidence": 0.99  # Triggers overclaiming / confidence downgrade
            },
            {
                "statement": "Unsupported claim backed by fake citation.",
                "passage_id": "non-existent-passage-id",  # Triggers block due to fabricated citation
                "confidence": 0.90
            }
        ]

        result = await validator.validate_research_output(claims_input, research_scope="Sanskrit Poetics")

        # 3. Assertions & Checkpoints Verification
        assert result["status"] == "BLOCKED_OR_DOWNGRADED"
        assert result["is_safe_for_publication"] is False
        assert len(result["validated_claims"]) == 2
        assert len(result["blocked_claims"]) == 1
        assert "Fabricated or non-existent citation reference" in result["blocked_claims"][0]["reason"]
        assert len(result["warnings"]) > 0