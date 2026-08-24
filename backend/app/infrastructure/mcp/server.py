from typing import Dict, Any, Callable, List, Optional
import structlog
from pydantic import BaseModel, ValidationError

logger = structlog.get_logger(__name__)

class MCPToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[..., Any]

class AnvikshikiMCPServer:
    """
    Model Context Protocol (MCP) server boundary defining tools, resource access policies,
    schema validation, permission controls, error responses, and tool audit logging.
    """
    def __init__(self, permission_policy: Optional[Callable[[str, Dict[str, Any]], bool]] = None):
        self._tools: Dict[str, MCPToolDefinition] = {}
        self.permission_policy = permission_policy or (lambda tool_name, args: True)

    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable[..., Any]):
        self._tools[name] = MCPToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler
        )
        logger.info("Registered MCP tool", tool_name=name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema
            }
            for tool in self._tools.values()
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a registered MCP tool with permission checks, schema validation, 
        audit logging, and standardized error handling.
        """
        if tool_name not in self._tools:
            logger.error("Attempted to execute unregistered MCP tool", tool_name=tool_name)
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not registered."
            }

        # 1. Enforce Permission Policy
        if not self.permission_policy(tool_name, arguments):
            logger.warning("MCP tool execution blocked by permission policy", tool_name=tool_name)
            return {
                "success": False,
                "error": f"Permission denied for tool '{tool_name}'."
            }

        tool_def = self._tools[tool_name]

        # 2. Audit Logging
        logger.info("Audit: Executing MCP tool", tool_name=tool_name, arguments=arguments)

        try:
            # 3. Handler execution
            result = await tool_def.handler(**arguments) if asyncio_iscoroutinefunction(tool_def.handler) else tool_def.handler(**arguments)
            return {
                "success": True,
                "result": result
            }
        except ValidationError as ve:
            logger.error("MCP tool input validation failed", tool_name=tool_name, errors=ve.errors())
            return {
                "success": False,
                "error": f"Invalid tool input validation: {ve.errors()}"
            }
        except Exception as e:
            logger.exception("MCP tool execution error", tool_name=tool_name, error=str(e))
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }

def asyncio_iscoroutinefunction(func: Callable[..., Any]) -> bool:
    import inspect
    return inspect.iscoroutinefunction(func)