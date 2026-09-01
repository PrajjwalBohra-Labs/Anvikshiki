import json
from types import SimpleNamespace

import pytest
from mcp.client import Client

from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.mcp import research_tools
from backend.app.infrastructure.mcp.research_tools import register_mcp_research_tools
from backend.app.infrastructure.mcp.server import AnvikshikiMCPServer


def _passage() -> SimpleNamespace:
    source = SimpleNamespace(
        id="source-1",
        title="Nyaya Sutra",
        author="Gotama",
        historical_era=None,
        original_language="Sanskrit",
        source_type=SourceType.PRIMARY,
        reference_url=None,
    )
    document = SimpleNamespace(
        id="document-1",
        source_id=source.id,
        checksum_sha256="a" * 64,
        mime_type="text/plain",
        original_filename="nyaya.txt",
        total_pages=1,
        source=source,
    )
    return SimpleNamespace(
        id="passage-1",
        document_id=document.id,
        document_version_id=None,
        page_id=None,
        page_number=1,
        passage_order=0,
        content="Perception arises from sense-object contact.",
        extraction_method="text",
        section_heading=None,
        ocr_confidence=1.0,
        extraction_uncertainty=False,
        language="en",
        document=document,
        document_version=None,
        page=None,
    )


class _FakeCitationService:
    def __init__(self, _session):
        pass

    async def generate_citation(self, passage_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            passage_id=passage_id,
            citation_string="Nyaya Sutra, by Gotama, p. 1",
        )


class _FakeLexicalRetriever:
    def __init__(self, _session):
        pass

    async def search(self, **_kwargs):
        return [
            SimpleNamespace(
                passage=_passage(),
                score=1.0,
                lexical_score=1.0,
                semantic_score=None,
                hybrid_score=None,
                rerank_score=None,
            )
        ]


class _FakeExecuteResult:
    def __init__(self, passage):
        self.passage = passage

    def scalar_one_or_none(self):
        return self.passage


class _FakeSession:
    async def execute(self, _statement):
        return _FakeExecuteResult(_passage())


class _FakeProvenanceService:
    def __init__(self, _session):
        pass

    async def trace_passage(self, _passage_id):
        return {"nodes": [{"node_type": "PASSAGE"}], "edges": []}

    async def trace_lineage(self, _source_id):
        return [{"source_id": "source-1", "title": "Nyaya Sutra", "type": SourceType.PRIMARY}]


@pytest.mark.asyncio
async def test_step40_registers_only_historical_tools_with_closed_schemas(monkeypatch):
    monkeypatch.setattr(research_tools, "LexicalRetriever", _FakeLexicalRetriever)
    monkeypatch.setattr(research_tools, "CitationService", _FakeCitationService)

    server = AnvikshikiMCPServer()
    register_mcp_research_tools(server, session=object(), session_factory=None)

    tools = server.list_tools()
    assert [tool["name"] for tool in tools] == ["search_local_sources", "trace_citation"]
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)

    result = await server.execute_tool(
        "search_local_sources",
        {"query": "perception", "retrieval": "lexical", "top_k": 1},
    )
    assert result["success"] is True
    payload = result["result"]
    assert payload["total_results"] == 1
    assert payload["sources_found"][0]["passage_id"] == "passage-1"
    assert payload["sources_found"][0]["citation_string"] == "Nyaya Sutra, by Gotama, p. 1"
    assert payload["fabricated"] is False


@pytest.mark.asyncio
async def test_step40_rejects_missing_unexpected_and_invalid_arguments_before_execution():
    server = AnvikshikiMCPServer()
    register_mcp_research_tools(server, session=None, session_factory=None)

    missing = await server.execute_tool("search_local_sources", {})
    unexpected = await server.execute_tool(
        "search_local_sources", {"query": "perception", "secret": "hidden"}
    )
    invalid_mode = await server.execute_tool(
        "search_local_sources", {"query": "perception", "retrieval": "web"}
    )
    invalid_limit = await server.execute_tool(
        "search_local_sources", {"query": "perception", "top_k": 21}
    )

    assert [item["error"] for item in (missing, unexpected, invalid_mode, invalid_limit)] == [
        "Invalid tool input."
    ] * 4


@pytest.mark.asyncio
async def test_step40_citation_trace_preserves_source_lineage_and_sanitizes_values(monkeypatch):
    monkeypatch.setattr(research_tools, "CitationService", _FakeCitationService)
    monkeypatch.setattr(research_tools, "ProvenanceService", _FakeProvenanceService)

    server = AnvikshikiMCPServer()
    register_mcp_research_tools(server, session=_FakeSession(), session_factory=None)
    result = await server.execute_tool("trace_citation", {"citation_id": "passage-1"})

    assert result["success"] is True
    payload = result["result"]
    assert payload["traceable"] is True
    assert payload["source"]["source_type"] == "PRIMARY"
    assert payload["source_lineage"][0]["type"] == "PRIMARY"
    assert payload["provenance_graph"]["nodes"][0]["node_type"] == "PASSAGE"
    assert "storage_path" not in payload["document"]
    assert "embedding" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_step40_empty_citation_is_structured_and_permission_fails_closed(monkeypatch):
    class _EmptySession:
        async def execute(self, _statement):
            return _FakeExecuteResult(None)

    server = AnvikshikiMCPServer(permission_policy=lambda _tool, _args: False)
    register_mcp_research_tools(server, session=_EmptySession(), session_factory=None)
    denied = await server.execute_tool("trace_citation", {"citation_id": "missing"})
    assert denied == {
        "success": False,
        "error": "Permission denied for tool 'trace_citation'.",
    }

    allowed_server = AnvikshikiMCPServer()
    register_mcp_research_tools(allowed_server, session=_EmptySession(), session_factory=None)
    missing = await allowed_server.execute_tool("trace_citation", {"citation_id": "missing"})
    assert missing == {
        "success": True,
        "result": {
            "citation_id": "missing",
            "traceable": False,
            "fabricated": False,
            "provenance_graph": {"nodes": [], "edges": []},
        },
    }


@pytest.mark.asyncio
async def test_step40_official_sdk_invokes_registered_tool(monkeypatch):
    monkeypatch.setattr(research_tools, "LexicalRetriever", _FakeLexicalRetriever)
    monkeypatch.setattr(research_tools, "CitationService", _FakeCitationService)

    server = AnvikshikiMCPServer()
    register_mcp_research_tools(server, session=object(), session_factory=None)
    async with Client(server.protocol_server, mode="legacy") as client:
        tools = await client.list_tools()
        result = await client.call_tool(
            "search_local_sources", {"query": "perception", "retrieval": "lexical"}
        )

    assert {tool.name for tool in tools.tools} == {"search_local_sources", "trace_citation"}
    assert result.is_error is False
    assert json.loads(result.content[0].text)["sources_found"][0]["passage_id"] == "passage-1"


@pytest.mark.asyncio
async def test_step40_downstream_failure_is_sanitized(monkeypatch):
    class _BrokenLexicalRetriever:
        def __init__(self, _session):
            pass

        async def search(self, **_kwargs):
            raise RuntimeError("database password and internal path")

    monkeypatch.setattr(research_tools, "LexicalRetriever", _BrokenLexicalRetriever)
    server = AnvikshikiMCPServer()
    register_mcp_research_tools(server, session=object(), session_factory=None)

    result = await server.execute_tool(
        "search_local_sources", {"query": "perception", "retrieval": "lexical"}
    )
    assert result == {"success": False, "error": "Tool execution failed."}
