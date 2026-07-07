"""
ServiceNow MCP Server - Stdio Entry Point
"""

import logging
import sys

from servicenow_mcp.config_loader import create_config_and_auth
from servicenow_mcp.application import initialize, mcp

# Import the tools package so every tool module registers with the MCP instance
import servicenow_mcp.tools  # noqa: F401

logger = logging.getLogger(__name__)

def main():
    try:
        # Initialize configuration and auth
        config, auth_manager = create_config_and_auth()
        
        # Initialize global state
        initialize(auth_manager, config)
        
        logger.info(f"Starting ServiceNow MCP server (Stdio) for instance: {config.instance_url}")
        
        # Run the server
        mcp.run(transport="stdio")
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
