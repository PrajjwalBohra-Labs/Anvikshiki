"""Entrypoint for the Anvikshiki MCP research-tool server."""

import asyncio

from backend.app.infrastructure.mcp.research_tools import create_mcp_research_server


def main() -> None:
    asyncio.run(create_mcp_research_server().run_stdio())


if __name__ == "__main__":
    main()
