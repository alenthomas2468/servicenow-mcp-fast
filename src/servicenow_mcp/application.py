"""
Shared FastMCP server instance and global state.
"""

from fastmcp import FastMCP
from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

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

def get_auth_manager() -> AuthManager:
    """Get the global authentication manager."""
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
