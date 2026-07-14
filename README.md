# TINA ServiceNow MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/built%20with-FastMCP-6e56cf)](https://gofastmcp.com/)
[![Transport](https://img.shields.io/badge/transport-stdio%20%7C%20Streamable%20HTTP-green)](#remote-deployment-streamable-http)
[![Deploy](https://img.shields.io/badge/deploy-Docker%20%2B%20Caddy%20on%20EC2-orange)](#remote-deployment-streamable-http)

A production-quality **Model Context Protocol (MCP)** server for ServiceNow, built with `fastmcp`. It exposes **63 tools across 13 modules**, letting AI clients (Claude Desktop, claude.ai, Claude Code, MCP Inspector) manage ServiceNow records through natural language.

Developed as an SIT ICT3902C Capstone Project in collaboration with Singtel, targeting **TINA** (Telco Intelligent Network Automation) — a heavily customized ServiceNow platform for network service management. The server runs against both a production TINA instance (local stdio) and a ServiceNow Personal Developer Instance (remote HTTP).

## What It Can Do

**Standard ServiceNow (ITSM / platform):**

| Module | Tools | Capabilities |
|---|---|---|
| Incidents | 6 | Create, update, resolve, comment, list, fetch by number |
| Users & Groups | 9 | Create/update users, manage groups and membership, assign roles |
| Stories | 5 | Create/update stories, manage dependencies |
| Workflows | 8 | List, inspect, create, update, activate/deactivate, versions |
| Knowledge Base | 9 | Knowledge bases, categories, article CRUD and publishing |
| Script Includes | 4 | List, get, create, update server-side scripts |
| Generic Tables | 2 | Query **any** table; introspect schema via `sys_dictionary` |

**TINA-specific (custom network CMDB tables):**

| Module | Tools | Capabilities |
|---|---|---|
| Network Elements | 4 | Network Element CI records |
| VRFs | 4 | Virtual Routing and Forwarding CI records |
| PE Router RFS Instances / Orders | 3 + 3 | Provider-edge router resource-facing services |
| eLite IPVPN CFS Instances / Orders | 3 + 3 | Customer-facing IPVPN service instances and orders |

The generic table tools mean the server is not limited to the modules above — any ServiceNow table can be queried and its schema inspected on the fly.

## Architecture

```
src/servicenow_mcp/
├── auth/
│   ├── auth_manager.py     # How the server talks to ServiceNow (basic/OAuth/API key,
│   │                       # plus per-user delegated tokens)
│   └── endpoint_auth.py    # How clients talk to THIS server (static bearer token
│                           # and/or ServiceNow OAuth per-user sign-in)
├── tools/                  # 63 MCP tool implementations across 13 modules
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
├── utils/
│   ├── http_client.py      # Pooled HTTP client: retries with backoff, SSL config,
│   │                       # structured JSON errors, PDI hibernation detection
│   ├── helpers.py          # Shared request/response helpers
│   ├── config.py           # Configuration models
│   └── logging_utils.py
├── application.py          # FastMCP application setup + per-request auth routing
├── server.py               # Local entry point (stdio)
└── server_sse.py           # Remote entry point (Streamable HTTP / SSE)
```

### Two Independent Auth Layers

1. **Endpoint auth** (client → MCP server): static bearer token for header-capable clients, and/or ServiceNow OAuth per-user sign-in for claude.ai / Claude Desktop custom connectors.
2. **Upstream auth** (MCP server → ServiceNow): Basic, OAuth, or API key — with per-user delegated identity so OAuth-signed-in users act as themselves in ServiceNow, not as a shared service account.

Both modes can be enabled simultaneously. See [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md).

### HTTP Layer Hardening

The upstream HTTP client is production-hardened with connection pooling, automatic retry with exponential backoff, OAuth token self-healing on 401, structured JSON error responses, and detection of hibernated developer instances (so clients get an actionable message instead of a cryptic HTML error). Details in [`docs/HTTP_HARDENING_CHANGES.md`](docs/HTTP_HARDENING_CHANGES.md).

## Quick Start (Local, stdio)

1.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    ```
    Windows (cmd):
    ```cmd
    .venv\Scripts\activate
    ```
    Linux/macOS:
    ```bash
    source .venv/bin/activate
    ```
2.  Install the package:
    ```bash
    pip install -e .
    ```
3.  Configure credentials:
    ```bash
    cp .env.example .env   # then fill in your ServiceNow instance URL and credentials
    ```
4.  Run the server:

    Windows (cmd):
    ```cmd
    .venv\Scripts\python.exe src\servicenow_mcp\server.py
    ```
    Linux/macOS:
    ```bash
    .venv/bin/python src/servicenow_mcp/server.py
    ```

## Quick Start (Docker, remote HTTP)

```bash
# Build and run the Streamable HTTP server + Caddy TLS reverse proxy
cd deploy
docker compose up -d --build
```

The compose stack runs two containers:

- **mcp** — this server on plain HTTP :8080 (never exposed directly; Claude clients require HTTPS for remote MCP)
- **caddy** — reverse proxy terminating TLS with automatic Let's Encrypt certificates ([`deploy/Caddyfile`](deploy/Caddyfile))

A complete AWS EC2 free-tier walkthrough — including DNS via DuckDNS, client setup for Claude Desktop / claude.ai / Claude Code, and the scaling story — is in [`docs/DEPLOYMENT_EC2.md`](docs/DEPLOYMENT_EC2.md).

## Configuration

Copy `.env.example` to `.env` and fill in your ServiceNow credentials. All options are documented inline in the example file.

### SSL Configuration

The server supports flexible SSL verification to handle corporate networks, proxies, and self-signed certificates.

**1. Default Secure Mode (Recommended)**
SSL verification is enabled by default. For a custom corporate CA, set:
```properties
SERVICENOW_SSL_CERT_PATH=C:\path\to\your\corporate-ca.crt
```

**2. Disable SSL Verification (Testing Only)**
```properties
SERVICENOW_DISABLE_SSL_VERIFY=true
```

> **Note:** If `SERVICENOW_DISABLE_SSL_VERIFY` is unset or `false`, the server defaults to secure verification (using `SERVICENOW_SSL_CERT_PATH` if provided, or system defaults).

## Remote Deployment (Streamable HTTP)

The server runs as a remote MCP server over Streamable HTTP so cloud AI clients (Claude Desktop, claude.ai, Claude Code) can connect:

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

### Connecting Claude

- **claude.ai / Claude Desktop** — add a custom connector pointing at `https://<your-domain>/mcp` (OAuth sign-in flow, per-user identity)
- **Claude Code / header-capable clients** — connect with `Authorization: Bearer <MCP_AUTH_TOKEN>`

## Debugging with MCP Inspector

The [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is a browser-based tool for interactively testing MCP servers.

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

A convenience script is provided for Windows: `.\inspector.ps1`

## Design Notes & Lessons Learned

- **Schema introspection**: `GlideTableDescriptor` behaves inconsistently across ServiceNow environments (returned zero records on some instances). The schema tool queries `sys_dictionary` directly instead, which is reliable everywhere.
- **Pagination header overflow**: list tools with large `sysparm_fields` on field-heavy tables can return HTTP 400 when `limit < 31`, because ServiceNow's pagination `Link` header exceeds size limits. The tools enforce safe limits / suppress the pagination header.
- **Transport choice**: Streamable HTTP was chosen over the deprecated SSE transport for remote deployments; SSE remains available as a legacy fallback.
- **Reference**: the [echelon-ai-labs/servicenow-mcp](https://github.com/echelon-ai-labs/servicenow-mcp) project was used for structural reference only. This server was rebuilt from scratch on FastMCP, with Streamable HTTP transport and an independent endpoint-authentication layer as key differentiators.

## Roadmap (Future Work)

- **Autoscaling**: a horizontal-scaling design (stateless HTTP workers behind a load balancer) is documented but intentionally not implemented in the current single-instance EC2 deployment.
- **Additional tooling**: ~18 further tools are planned across CMDB relationship traversal, incident intelligence, change/problem management, and TINA-specific service-assurance workflows.

## Documentation

- [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md) — the two auth layers, per-user OAuth flow, and serving additional ServiceNow instances
- [`docs/DEPLOYMENT_EC2.md`](docs/DEPLOYMENT_EC2.md) — complete AWS EC2 free-tier deployment guide (Docker + Caddy with automatic HTTPS), client setup, and the scaling story
- [`docs/HTTP_HARDENING_CHANGES.md`](docs/HTTP_HARDENING_CHANGES.md) — connection pooling, retries, structured errors, hibernation detection

## Acknowledgements

Developed as part of the Singapore Institute of Technology ICT3902C Integrated Work Study Programme Capstone Project, in collaboration with Singtel.
