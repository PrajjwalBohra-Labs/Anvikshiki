import pytest
from backend.app.infrastructure.mcp.server import AnvikshikiMCPServer

@pytest.mark.asyncio
async def test_mcp_server_registration_and_execution():
    server = AnvikshikiMCPServer()

    # Define mock tool handler
    def mock_search_handler(query: str, limit: int = 5):
        return {"query": query, "matches": [f"Result for {query} ({i})" for i in range(limit)]}

    server.register_tool(
        name="search_local_sources",
        description="Searches local authoritative primary texts.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"}
            },
            "required": ["query"]
        },
        handler=mock_search_handler
    )

    # 1. Verify Tool Schemas / Listing
    tools = server.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "search_local_sources"
    assert "inputSchema" in tools[0]

    # 2. Verify Successful Tool Execution
    exec_result = await server.execute_tool("search_local_sources", {"query": "Nyaya", "limit": 2})
    assert exec_result["success"] is True
    assert len(exec_result["result"]["matches"]) == 2

    # 3. Verify Error Handling for Unregistered Tools
    bad_result = await server.execute_tool("non_existent_tool", {})
    assert bad_result["success"] is False
    assert "not registered" in bad_result["error"]