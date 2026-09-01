import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.rag.lexical_retriever import LexicalRetriever
from backend.app.core.config import settings

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_lexical_search_and_filtering(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # --- Seed Data ---
        src_primary = SourceModel(title="Primary Text", source_type=SourceType.PRIMARY)
        src_scholarly = SourceModel(title="Scholarly Article", source_type=SourceType.SCHOLARLY_SECONDARY)
        session.add_all([src_primary, src_scholarly])
        await session.flush()
        
        doc_p = DocumentModel(source_id=src_primary.id, checksum_sha256="hash1", mime_type="text/plain")
        doc_s = DocumentModel(source_id=src_scholarly.id, checksum_sha256="hash2", mime_type="text/plain")
        session.add_all([doc_p, doc_s])
        await session.flush()
        
        # Passage 1: Contains 'pratyaksha' multiple times (High score)
        p1 = PassageModel(document_id=doc_p.id, language="sa", content="Pratyaksha is direct perception. Pratyaksha is infallible.")
        # Passage 2: Contains 'pratyaksha' once (Lower score)
        p2 = PassageModel(document_id=doc_s.id, language="en", content="The text discusses pratyaksha and inference.")
        # Passage 3: Irrelevant
        p3 = PassageModel(document_id=doc_s.id, language="en", content="This passage is about anumana (inference) only.")
        
        session.add_all([p1, p2, p3])
        await session.commit()
        
        retriever = LexicalRetriever(session)
        
        # --- Test 1: Basic Search and TF Ranking ---
        results = await retriever.search("pratyaksha")
        assert len(results) == 2
        # p1 should be ranked higher due to higher term frequency
        assert results[0].passage.id == p1.id
        assert results[0].score > results[1].score
        
        # --- Test 2: Source Type Filtering ---
        results_filtered = await retriever.search("pratyaksha", source_type=SourceType.SCHOLARLY_SECONDARY)
        assert len(results_filtered) == 1
        assert results_filtered[0].passage.id == p2.id
        
        # --- Test 3: Exact Phrase Bonus ---
        results_phrase = await retriever.search("direct perception")
        assert len(results_phrase) == 1
        assert results_phrase[0].passage.id == p1.id
        assert results_phrase[0].score > 5.0  # Should trigger exact phrase bonus
        
        # --- Test 4: Language Filtering ---
        results_lang = await retriever.search("pratyaksha", language="sa")
        assert len(results_lang) == 1
        assert results_lang[0].passage.id == p1.id

        # Filters preserve the documentary identity used by later provenance
        # and citation stages.
        results_document = await retriever.search("pratyaksha", document_id=doc_p.id)
        assert [item.passage.id for item in results_document] == [p1.id]
        results_source = await retriever.search("pratyaksha", source_id=src_primary.id)
        assert [item.passage.id for item in results_source] == [p1.id]
        assert await retriever.search("absent terminology") == []


@pytest.mark.asyncio
async def test_lexical_query_validation(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        retriever = LexicalRetriever(session)
        assert await retriever.search("   ") == []
        with pytest.raises(ValueError, match="exceeds"):
            await retriever.search("x" * (settings.LEXICAL_MAX_QUERY_LENGTH + 1))
        with pytest.raises(ValueError, match="between"):
            await retriever.search("term", limit=0)
