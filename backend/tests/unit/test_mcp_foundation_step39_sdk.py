import json
import sys

import httpx
import pytest
from jsonschema.exceptions import SchemaError
from mcp.client import Client
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from backend.app.infrastructure.mcp.server import AnvikshikiMCPServer


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}},
        "required": ["query"],
    }


@pytest.mark.asyncio
async def test_official_mcp_sdk_initializes_lists_schema_and_calls_tool() -> None:
    server = AnvikshikiMCPServer()

    async def echo(query: str) -> dict[str, str]:
        return {"query": query}

    server.register_tool("echo", "Echoes a query.", _schema(), echo)

    async with Client(server.protocol_server, mode="legacy") as client:
        tools = await client.list_tools()
        result = await client.call_tool("echo", {"query": "Nyaya"})

    assert tools.tools[0].name == "echo"
    assert tools.tools[0].input_schema["additionalProperties"] is False
    assert result.is_error is False
    assert json.loads(result.content[0].text) == {"query": "Nyaya"}


@pytest.mark.asyncio
async def test_protocol_rejects_invalid_arguments_without_leaking_details() -> None:
    server = AnvikshikiMCPServer()

    async def echo(query: str) -> str:
        return query

    server.register_tool("echo", "Echoes a query.", _schema(), echo)

    async with Client(server.protocol_server, mode="legacy") as client:
        result = await client.call_tool("echo", {"unexpected": "secret"})

    assert result.is_error is True
    assert result.content[0].text == "Invalid tool input."
    assert "secret" not in result.content[0].text


@pytest.mark.asyncio
async def test_permission_and_authentication_boundaries_fail_closed() -> None:
    denied = AnvikshikiMCPServer(permission_policy=lambda _tool, _args: False)
    denied.register_tool("echo", "Echoes.", _schema(), lambda query: query)
    denied_result = await denied.execute_tool("echo", {"query": "Nyaya"})
    assert denied_result == {
        "success": False,
        "error": "Permission denied for tool 'echo'.",
    }

    authenticated = AnvikshikiMCPServer(require_user_context=True)
    authenticated.register_tool("echo", "Echoes.", _schema(), lambda query: query)
    unauthenticated_result = await authenticated.execute_tool("echo", {"query": "Nyaya"})
    assert unauthenticated_result == {
        "success": False,
        "error": "Authentication is required.",
    }


def test_registration_rejects_invalid_schema_and_tool_name() -> None:
    server = AnvikshikiMCPServer()
    with pytest.raises(ValueError):
        server.register_tool("bad name", "Invalid.", _schema(), lambda query: query)
    with pytest.raises(SchemaError):
        server.register_tool("invalid_schema", "Invalid.", {"type": "not-a-type"}, lambda: None)


@pytest.mark.asyncio
async def test_streamable_http_app_is_constructible_with_sdk() -> None:
    server = AnvikshikiMCPServer()
    app = server.streamable_http_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
    assert response.status_code in {404, 405}


@pytest.mark.asyncio
async def test_stdio_entrypoint_performs_real_mcp_handshake() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.app.infrastructure.mcp"],
        cwd="C:/anvikshiki",
    )
    async with stdio_client(parameters) as (read_stream, write_stream), ClientSession(
        read_stream, write_stream
    ) as client:
        initialized = await client.initialize()
        tools = await client.list_tools()
    assert initialized.server_info.name == "anvikshiki"
    assert initialized.protocol_version
    assert tools.tools == []
