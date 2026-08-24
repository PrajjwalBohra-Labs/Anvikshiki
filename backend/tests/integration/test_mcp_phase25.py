import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.mcp.server import AnvikshikiMcpServer

@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    monkeypatch.setattr("backend.app.core.config.settings.STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_mcp_tools_execution():
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # Seed test corpus
        source = SourceModel(title="Yoga Sutras", author="Patanjali", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="mcp_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(
            document_id=doc.id,
            page_number=2,
            content="Yoga is the restriction of the fluctuations of consciousness (chitta-vritti-nirodha)."
        )
        session.add(passage)
        await session.commit()
        source_id = source.id

    # Test MCP Search Tool
    search_results = await AnvikshikiMcpServer.tool_search_corpus(query="fluctuations of consciousness", top_k=1)
    assert len(search_results) == 1
    assert "chitta-vritti-nirodha" in search_results[0]["content"]
    assert "Yoga Sutras" in search_results[0]["citation"]

    # Test MCP Argument Synthesis Tool
    arg_result = await AnvikshikiMcpServer.tool_synthesize_argument(query="consciousness restriction")
    assert arg_result["pramana_type"] == "anumana"
    assert arg_result["overall_status"] == "supported"

    # Test MCP Provenance Tracing Tool
    lineage = await AnvikshikiMcpServer.tool_trace_provenance(source_id=source_id)
    assert len(lineage) == 1
    assert lineage[0]["title"] == "Yoga Sutras"