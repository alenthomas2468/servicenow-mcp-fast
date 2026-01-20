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
