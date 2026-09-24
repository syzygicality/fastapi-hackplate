import logging

from mcp.server import MCPServer

logger = logging.getLogger(__name__)

mcp: MCPServer | None = None


def init_mcp(name: str) -> MCPServer:
    global mcp
    mcp = MCPServer(name=name)
    logger.info("MCP server initialized.")
    return mcp


def get_mcp() -> MCPServer:
    if mcp is None:
        raise RuntimeError("MCP server not initialized, check mcp_server_enabled")
    return mcp
