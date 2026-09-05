"""MCP Foundation boundary.

This module keeps the small in-process registration API used by existing
Anvikshiki callers, while delegating protocol serving and capability
negotiation to the official MCP SDK.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Any

import mcp_types as types
import structlog
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JsonSchemaValidationError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ConfigDict, ValidationError

from backend.app.core.config import settings

logger = structlog.get_logger(__name__)


class MCPToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


class AnvikshikiMCPServer:
    """Secure registration and execution boundary for Anvikshiki MCP tools."""

    def __init__(
        self,
        permission_policy: Callable[[str, dict[str, Any]], bool] | None = None,
        *,
        require_user_context: bool = False,
    ):
        self._tools: dict[str, MCPToolDefinition] = {}
        self.permission_policy = permission_policy or (lambda _tool_name, _args: True)
        self.require_user_context = require_user_context
        self.protocol_server = Server(
            settings.MCP_SERVER_NAME,
            version=settings.MCP_SERVER_VERSION,
            description="Anvikshiki tool interoperability boundary.",
            instructions=(
                "Tools are explicitly registered by Anvikshiki services. "
                "Search and source authority are controlled by the application."
            ),
            on_list_tools=self._protocol_list_tools,
            on_call_tool=self._protocol_call_tool,
        )

    @staticmethod
    def _strict_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
        schema = dict(input_schema)
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        schema.setdefault("additionalProperties", False)
        Draft202012Validator.check_schema(schema)
        return schema

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        if not name or not name.strip() or len(name) > 128:
            raise ValueError("MCP tool names must contain 1-128 characters.")
        if not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("MCP tool names may contain only letters, numbers, '_' and '-'.")
        if not callable(handler):
            raise TypeError("MCP tool handler must be callable.")
        strict_schema = self._strict_schema(input_schema)
        definition = MCPToolDefinition(
            name=name,
            description=description,
            input_schema=strict_schema,
            handler=handler,
        )
        self._tools[name] = definition

        logger.info("mcp_tool_registered", tool_name=name)

    async def _protocol_list_tools(self, _context: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.input_schema,
                )
                for tool in self._tools.values()
            ]
        )

    async def _protocol_call_tool(
        self, _context: Any, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        result = await self.execute_tool(params.name, params.arguments or {})
        if not result["success"]:
            return types.CallToolResult(
                content=[types.TextContent(text=result["error"])], isError=True
            )
        value = result["result"]
        rendered = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
        return types.CallToolResult(content=[types.TextContent(text=rendered)])

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate, authorize, audit, and execute one registered tool."""
        if tool_name not in self._tools:
            logger.warning("mcp_tool_not_registered", tool_name=tool_name)
            return {"success": False, "error": f"Tool '{tool_name}' is not registered."}
        if self.require_user_context and not user_context:
            logger.warning("mcp_tool_authentication_required", tool_name=tool_name)
            return {"success": False, "error": "Authentication is required."}
        if not isinstance(arguments, dict):
            return {"success": False, "error": "Invalid tool arguments."}

        definition = self._tools[tool_name]
        try:
            Draft202012Validator(definition.input_schema).validate(arguments)
        except JsonSchemaValidationError:
            logger.warning("mcp_tool_input_rejected", tool_name=tool_name)
            return {"success": False, "error": "Invalid tool input."}

        try:
            allowed = self.permission_policy(tool_name, arguments)
        except Exception as exc:  # noqa: BLE001 - policy failures fail closed.
<<<<<<< HEAD
            logger.warning("mcp_permission_policy_failed", tool_name=tool_name, error_type=type(exc).__name__)
=======
            logger.warning(
                "mcp_permission_policy_failed",
                tool_name=tool_name,
                error_type=type(exc).__name__,
            )
>>>>>>> origin/main
            allowed = False
        if not allowed:
            logger.warning("mcp_tool_permission_denied", tool_name=tool_name)
            return {"success": False, "error": f"Permission denied for tool '{tool_name}'."}

        logger.info(
            "mcp_tool_audit",
            tool_name=tool_name,
            argument_keys=sorted(arguments),
            authenticated=bool(user_context),
        )
        try:
            result = definition.handler(**arguments)
            if inspect.isawaitable(result):
                result = await result
            return {"success": True, "result": result}
        except ValidationError:
            logger.warning("mcp_tool_validation_error", tool_name=tool_name)
            return {"success": False, "error": "Tool input was rejected."}
        except ValueError:
            logger.warning("mcp_tool_security_validation_error", tool_name=tool_name)
            return {"success": False, "error": "Security violation: tool input was rejected."}
<<<<<<< HEAD
        except Exception as exc:  # noqa: BLE001 - sanitized MCP failure boundary
            logger.error("mcp_tool_execution_error", tool_name=tool_name, error_type=type(exc).__name__)
=======
        except Exception as exc:  # noqa: BLE001 - tool boundary is sanitized.
            logger.error(
                "mcp_tool_execution_error",
                tool_name=tool_name,
                error_type=type(exc).__name__,
            )
>>>>>>> origin/main
            return {"success": False, "error": "Tool execution failed."}

    async def run_stdio(self) -> None:
        """Run the official SDK's stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await self.protocol_server.run(
                read_stream,
                write_stream,
                self.protocol_server.create_initialization_options(),
            )

    def streamable_http_app(self) -> Any:
        """Return the official SDK ASGI application for explicit embedding."""
        return self.protocol_server.streamable_http_app()
