"""
Shared FastMCP server instance and global state.
"""

from fastmcp import FastMCP
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig
from servicenow_mcp.utils.logging_utils import setup_request_logging

# Initialize FastMCP instance
mcp = FastMCP("ServiceNow")

# Global state
_auth_manager: AuthManager = None
_server_config: ServerConfig = None

def initialize(auth_manager: AuthManager, server_config: ServerConfig):
    """
    Initialize the global state.
    
    Args:
        auth_manager: Authentication manager instance.
        server_config: Server configuration instance.
    """
    global _auth_manager, _server_config
    _auth_manager = auth_manager
    _server_config = server_config

    if server_config.debug:
        setup_request_logging()

def _delegated_auth_manager() -> AuthManager:
    """Return a per-user AuthManager when the request came in through the
    endpoint's ServiceNow OAuth, else None.

    The endpoint auth (auth/endpoint_auth.py) tags OAuth sessions with a
    marker claim and puts the user's ServiceNow access token on the request
    context; here that token is wrapped so the tool call runs as the user.
    Static-token and stdio sessions have no marker and fall through to the
    shared service account.
    """
    if _server_config is None:
        return None
    try:
        from fastmcp.server.dependencies import get_access_token

        token = get_access_token()
    except Exception:
        return None
    if token is None:
        return None
    claims = getattr(token, "claims", None) or {}
    from servicenow_mcp.auth.endpoint_auth import SERVICENOW_OAUTH_CLAIM

    if claims.get("mode") != SERVICENOW_OAUTH_CLAIM:
        return None

    from servicenow_mcp.auth.auth_manager import DelegatedAuthManager

    return DelegatedAuthManager(
        token.token, _server_config.instance_url, _server_config.ssl_cert_path
    )


def get_auth_manager() -> AuthManager:
    """Get the authentication manager for the current request.

    Per-user delegated auth (ServiceNow OAuth sessions) takes precedence;
    everything else uses the global service-account manager.
    """
    delegated = _delegated_auth_manager()
    if delegated is not None:
        return delegated
    if _auth_manager is None:
        raise RuntimeError("AuthManager not initialized. Call initialize() first.")
    return _auth_manager

def get_config() -> ServerConfig:
    """Get the global server configuration."""
    if _server_config is None:
        raise RuntimeError("ServerConfig not initialized. Call initialize() first.")
    return _server_config

# Make mcp available for import
__all__ = ["mcp", "initialize", "get_auth_manager", "get_config"]
