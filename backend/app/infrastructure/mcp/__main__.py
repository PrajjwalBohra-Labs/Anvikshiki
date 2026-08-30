"""Entrypoint for the foundation-only MCP stdio server."""

import asyncio

from backend.app.infrastructure.mcp.server import AnvikshikiMCPServer


def main() -> None:
    asyncio.run(AnvikshikiMCPServer().run_stdio())


if __name__ == "__main__":
    main()
