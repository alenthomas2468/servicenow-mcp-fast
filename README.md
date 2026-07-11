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
├── auth/
│   ├── auth_manager.py     # How the server talks to ServiceNow (basic/OAuth/API key,
│   │                       # plus per-user delegated tokens)
│   └── endpoint_auth.py    # How clients talk to THIS server (static bearer token
│                           # and/or ServiceNow OAuth per-user sign-in)
├── tools/              # MCP tool implementations
│   ├── incident_tools.py
│   ├── user_tools.py
│   ├── story_tools.py
│   ├── workflow_tools.py
│   ├── knowledge_base.py
│   ├── script_include_tools.py
│   ├── generic_table_tools.py
│   ├── network_element_tools.py
│   ├── vrf_tools.py
│   ├── pe_router_rfs_instance_tools.py / pe_router_rfs_order_tools.py
│   └── elite_ipvpn_cfs_instance_tools.py / elite_ipvpn_cfs_order_tools.py
├── utils/              # Shared utilities
│   ├── http_client.py  # Pooled HTTP client: retries, SSL config, hibernation detection
│   ├── helpers.py      # Common helper functions
│   ├── config.py       # Configuration models
│   └── logging_utils.py
├── application.py      # FastMCP application setup + per-request auth routing
├── server.py           # Local entry point (stdio)
└── server_sse.py       # Remote entry point (Streamable HTTP / SSE)
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
    on Windows cmd
    ```cmd
    .venv\Scripts\activate
    ```
    on Linux/macOS
    ```bash
    source .venv/bin/activate
    ```
3.  Install the package:
    ```bash
    pip install -e .
    ```


## Configuration

Copy `.env.example` to `.env` and fill in your ServiceNow credentials.

### SSL Configuration

The server supports flexible SSL verification settings to handle corporate networks, proxies, and self-signed certificates.

**1. Default Secure Mode (Recommended)**
By default, SSL verification is enabled. If you use a custom corporate certificate, set the path:
```properties
# Uses the provided certificate for verification
SERVICENOW_SSL_CERT_PATH=C:\path\to\your\corporate-ca.crt
```

**2. Disable SSL Verification (Testing Only)**
To disable SSL verification (e.g., for local testing or dev instances), you must explicitly set the variable to `true`.
```properties
# API requests will skip SSL verification
SERVICENOW_DISABLE_SSL_VERIFY=true
```

> **Note:** If `SERVICENOW_DISABLE_SSL_VERIFY` is not present, or set to `false`, the server will default to secure verification (using `SERVICENOW_SSL_CERT_PATH` if provided, or system defaults).

## Usage

Run the server:

Windows (cmd)
```cmd
.venv\Scripts\python.exe src\servicenow_mcp\server.py
```

Linux/macOS
```bash
.venv/bin/python src/servicenow_mcp/server.py
```

## Debugging with MCP Inspector

The [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is a browser-based tool for testing and debugging your MCP server. It connects to your server and allows you to interactively call tools.

### Running the Inspector

Use `npx` to run the inspector, pointing it at the server entry point:

```cmd
# On Windows (cmd)
.venv\Scripts\activate
set PYTHONPATH=src
npx @modelcontextprotocol/inspector python src/servicenow_mcp/server.py
```

```powershell
# On Windows (PowerShell)
. .venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
npx @modelcontextprotocol/inspector python src/servicenow_mcp/server.py
```

```bash
# On Linux/macOS
source .venv/bin/activate
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

## Remote Deployment (Streamable HTTP)

The server can run as a remote MCP server over Streamable HTTP so cloud AI
clients (Claude Desktop, claude.ai, Claude Code) can connect:

```bash
# Streamable HTTP on 0.0.0.0:8080 at /mcp, protected by a bearer token
MCP_AUTH_TOKEN=<random-secret> servicenow-mcp-http
```

Key environment variables:

| Variable         | Default | Purpose                                          |
|------------------|---------|--------------------------------------------------|
| `MCP_TRANSPORT`  | `http`  | `http` (Streamable HTTP) or `sse` (legacy)       |
| `MCP_HOST`       | `0.0.0.0` | Bind interface (keep 0.0.0.0 for Docker/EC2)   |
| `PORT`           | `8080`  | Listen port                                      |
| `MCP_AUTH_TOKEN` | unset   | Static bearer token for header-capable clients (Claude Code, IDEs, scripts). **Never expose the server publicly without endpoint auth.** |
| `SERVICENOW_OAUTH_CLIENT_ID` / `SERVICENOW_OAUTH_CLIENT_SECRET` | unset | Enable per-user ServiceNow OAuth sign-in for claude.ai / Claude Desktop custom connectors. Tool calls then run as the signed-in user. |
| `MCP_PUBLIC_URL` | unset   | Public HTTPS base URL of this server (required for OAuth) |

Both auth modes can be enabled at once — header clients use the token and act
as the service account; OAuth clients sign in and act as themselves.

Documentation:

- `docs/AUTHENTICATION.md` — the two auth layers, per-user OAuth flow,
  and how to serve additional ServiceNow instances
- `docs/DEPLOYMENT_EC2.md` — complete AWS EC2 free-tier deployment guide
  (Docker + Caddy with automatic HTTPS), client setup, and the scaling story
- `docs/HTTP_HARDENING_CHANGES.md` — connection pooling, retries, structured
  errors, hibernation detection
