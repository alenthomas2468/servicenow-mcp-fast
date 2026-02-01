# ServiceNow FastMCP Server

A Model Context Protocol (MCP) server for ServiceNow, built with `fastmcp`.

## Overview

This server allows LLMs to interact with ServiceNow instances to manage:
- Incidents
- Users and Groups
- Stories
- Workflows
- Knowledge Base Articles
- Script Includes

## Architecture

The project follows a clean, modular architecture:

```
src/servicenow_mcp/
├── auth/               # Authentication handling (Basic, OAuth, API Key)
├── tools/              # MCP tool implementations
│   ├── incident_tools.py
│   ├── user_tools.py
│   ├── story_tools.py
│   ├── workflow_tools.py
│   ├── knowledge_base.py
│   └── script_include_tools.py
├── utils/              # Shared utilities
│   ├── http_client.py  # Centralized HTTP client with SSL support
│   ├── helpers.py      # Common helper functions
│   ├── config.py       # Configuration models
│   └── logging_utils.py
├── application.py      # FastMCP application setup
├── server.py           # Main server entry point
└── server_sse.py       # SSE server variant
```

### Utility Modules

#### `http_client.py`
Centralized HTTP client providing:
- Unified interface for all HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Automatic SSL certificate configuration for private network instances
- Consistent timeout and error handling

#### `helpers.py`
Common helper functions to reduce code duplication:
- `build_request_data()` - Build request payloads from required/optional fields
- `resolve_record_id()` - Resolve ServiceNow identifiers to sys_ids
- `format_success_response()` / `format_error_response()` - Standardized response formatting
- `format_list_response()` - Pagination-aware list responses
- `extract_display_value()` - Safely extract display values from ServiceNow fields
- `is_sys_id()` - Check if a string is a valid ServiceNow sys_id

## Installation

1.  Create a virtual environment:
    ```bash
    python -m venv .venv
    ```
2.  Activate the virtual environment.
3.  Install the package:
    ```bash
    pip install -e .
    ```

## Configuration

Copy `.env.example` to `.env` and fill in your ServiceNow credentials.

## Usage

Run the server:
```bash
python src/servicenow_mcp/server.py
```

## Debugging with MCP Inspector

The [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is a browser-based tool for testing and debugging your MCP server. It connects to your server and allows you to interactively call tools.

### Running the Inspector

Use `npx` to run the inspector, pointing it at the server entry point:

```powershell
# On Windows (PowerShell)
$env:PYTHONPATH = "src"
npx @modelcontextprotocol/inspector python src/servicenow_mcp/server.py
```

```bash
# On Linux/macOS
PYTHONPATH=src npx @modelcontextprotocol/inspector python src/servicenow_mcp/server.py
```

This will:
1.  Start your ServiceNow MCP server.
2.  Open a browser window with the Inspector UI.
3.  Allow you to view available tools and call them interactively.

### Using the Helper Script (Windows)

For convenience, a `inspector.ps1` script is provided:

```powershell
.\inspector.ps1
```
