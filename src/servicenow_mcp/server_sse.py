"""
ServiceNow MCP Server - Remote Entry Point (Streamable HTTP / SSE)

Runs the MCP server over a network transport so remote AI clients
(Claude Desktop, claude.ai connectors, MCP Inspector) can connect.

Environment variables:
    MCP_TRANSPORT   "http" (Streamable HTTP, default, recommended) or "sse" (legacy)
    MCP_HOST        Interface to bind (default 0.0.0.0 — required for Docker/EC2)
    PORT            Port to listen on (default 8080)
    MCP_AUTH_TOKEN  If set, clients must send "Authorization: Bearer <token>".
                    If unset, the endpoint is UNAUTHENTICATED — do not expose
                    an unauthenticated server to the internet.
"""

import logging
import os
import sys

from servicenow_mcp.config_loader import create_config_and_auth
from servicenow_mcp.application import initialize, mcp

# Import the tools package so every tool module registers with the MCP instance
import servicenow_mcp.tools  # noqa: F401

logger = logging.getLogger(__name__)


def _configure_endpoint_auth():
    """Protect the MCP endpoint itself with a bearer token if configured.

    BLOCKER overcome: the original server had no auth on the HTTP/SSE endpoint
    at all. Once bound to 0.0.0.0 for EC2 (see ServerConfig.host), that meant
    anyone who found the URL could call every ServiceNow tool using this
    server's credentials. StaticTokenVerifier is the minimal fix for the demo;
    docs/DEPLOYMENT_EC2.md (local-only) covers upgrading to real OAuth
    (fastmcp.server.auth.providers.*) for a production rollout.
    """
    auth_token = os.environ.get("MCP_AUTH_TOKEN")
    if auth_token:
        from fastmcp.server.auth import StaticTokenVerifier

        mcp.auth = StaticTokenVerifier(
            tokens={
                auth_token: {
                    "client_id": "servicenow-mcp-client",
                    "scopes": ["servicenow:full"],
                }
            }
        )
        logger.info("Bearer token authentication ENABLED for the MCP endpoint")
    else:
        logger.warning(
            "MCP_AUTH_TOKEN not set - the MCP endpoint is UNAUTHENTICATED. "
            "Anyone who can reach this port can operate on your ServiceNow instance."
        )


def main():
    try:
        # Initialize configuration and auth
        config, auth_manager = create_config_and_auth()

        # Initialize global state
        initialize(auth_manager, config)

        _configure_endpoint_auth()

        # BLOCKER overcome: this used to be hardcoded to transport="sse", which
        # is the deprecated MCP transport. Streamable HTTP ("http") is the
        # current spec and is what claude.ai / Claude Desktop remote connectors
        # expect; SSE is kept only for backward compatibility with older clients.
        transport = os.environ.get("MCP_TRANSPORT", "http").lower()
        if transport not in ("http", "sse"):
            raise ValueError(f"Unsupported MCP_TRANSPORT: {transport} (use 'http' or 'sse')")

        logger.info(
            f"Starting ServiceNow MCP server ({transport}) for instance {config.instance_url} "
            f"on {config.host}:{config.port}"
        )

        # Run the server (Streamable HTTP serves at /mcp, SSE at /sse)
        mcp.run(transport=transport, host=config.host, port=config.port)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
