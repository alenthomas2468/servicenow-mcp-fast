"""
ServiceNow MCP Server - SSE Entry Point
"""

import logging
import sys

from servicenow_mcp.config_loader import create_config_and_auth
from servicenow_mcp.application import initialize, mcp

# Import tools so they register with the MCP instance
import servicenow_mcp.tools.incident_tools
import servicenow_mcp.tools.workflow_tools
import servicenow_mcp.tools.user_tools
import servicenow_mcp.tools.story_tools
import servicenow_mcp.tools.script_include_tools
import servicenow_mcp.tools.knowledge_base

logger = logging.getLogger(__name__)

def main():
    try:
        # Initialize configuration and auth
        config, auth_manager = create_config_and_auth()
        
        # Initialize global state
        initialize(auth_manager, config)
        
        logger.info(f"Starting ServiceNow MCP server (SSE) for instance: {config.instance_url}")
        
        # Run the server
        mcp.run(transport="sse")
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
