# Authentication Architecture

This server has **two independent authentication layers**. Confusing them is
the most common source of setup errors, so name them explicitly:

| Layer | Question it answers | Where it's configured |
|-------|--------------------|----------------------|
| **Endpoint auth** | Who may talk to *this MCP server*? | `MCP_AUTH_TOKEN`, `SERVICENOW_OAUTH_CLIENT_ID/SECRET`, `MCP_PUBLIC_URL` |
| **ServiceNow auth** | Which ServiceNow identity does a *tool call* run as? | `SERVICENOW_AUTH_TYPE` + credentials (`SERVICENOW_USERNAME/PASSWORD`, ...) |

Code map: endpoint auth lives in `src/servicenow_mcp/auth/endpoint_auth.py`;
ServiceNow auth in `src/servicenow_mcp/auth/auth_manager.py`; the routing
between them in `application.py::get_auth_manager()`.

---

## Endpoint auth modes

All modes are selected purely by environment variables — no code changes.

### 1. Static bearer token (`MCP_AUTH_TOKEN`)

Every request must carry `Authorization: Bearer <token>`. Works with any MCP
client that can send headers: Claude Code, Cursor, MCP Inspector, LangChain,
plain HTTP scripts. Tool calls run as the **shared service account** from
`SERVICENOW_USERNAME`/`SERVICENOW_PASSWORD`.

### 2. ServiceNow OAuth (per-user sign-in)

Set `SERVICENOW_OAUTH_CLIENT_ID`, `SERVICENOW_OAUTH_CLIENT_SECRET`, and
`MCP_PUBLIC_URL`. The server then exposes a full OAuth authorization server
(FastMCP `OAuthProxy`) with dynamic client registration — which is exactly
what claude.ai and Claude Desktop custom connectors require. Connecting users
are redirected to **ServiceNow's own login page**, and every tool call they
make runs with **their** ServiceNow account, roles, and ACLs.

```
Claude client          MCP server (OAuthProxy)              ServiceNow
     │  register (DCR)      │                                   │
     │──────────────────────>                                   │
     │  /authorize           │   302 to /oauth_auth.do          │
     │──────────────────────>│──────────────────────────────────>
     │                       │        user logs in, code back   │
     │                       │<──────────────────────────────────
     │                       │   code -> token (/oauth_token.do)│
     │                       │──────────────────────────────────>
     │   FastMCP JWT         │   stores encrypted SN token      │
     │<──────────────────────│                                   │
     │  tool call (JWT)      │   validated, swapped for the     │
     │──────────────────────>│   user's SN token, API call      │
     │                       │──────────────────────────────────>
```

Details worth knowing:

- The client never sees the ServiceNow token. It gets a JWT minted by this
  server; on every request the JWT is swapped for the stored (encrypted)
  ServiceNow token, which is validated against the instance (60 s cache) and
  refreshed transparently when it expires.
- OAuth state persists in the `mcp_oauth_state` Docker volume, so users stay
  signed in across container rebuilds.
- One-time instance setup: an Application Registry record ("OAuth API
  endpoint for external clients") whose redirect URL is
  `<MCP_PUBLIC_URL>/auth/callback` — see `DEPLOYMENT_EC2.md` Step 7.

### 3. Both at once (the deployed configuration)

Set all of the above and the server runs FastMCP's `MultiAuth`: either
credential works on the same `/mcp` endpoint. This is the recommended
configuration — header-capable clients keep the simple token, interactive
connectors get real sign-in, and the two identity models coexist:

| Client | Credential | Runs in ServiceNow as |
|--------|-----------|----------------------|
| Claude Code / scripts / IDEs | `Authorization: Bearer` header | service account |
| claude.ai / Claude Desktop connector | ServiceNow OAuth sign-in | the signed-in user |

### 4. Neither (unauthenticated)

Only for local development. Never expose an unauthenticated server publicly —
it would hand the service account to anyone who finds the URL.

---

## How per-user delegation works internally

Every tool module gets its ServiceNow credentials from one function:
`application.py::get_auth_manager()`. On each call it checks the request
context (FastMCP's `get_access_token()`):

- Request authenticated via ServiceNow OAuth → the token carries a marker
  claim; the call gets a `DelegatedAuthManager` wrapping *that user's*
  ServiceNow access token.
- Anything else (static token, stdio) → the global `AuthManager` with the
  service-account credentials.

Because all ~100 tools already route through this single function, per-user
identity required **zero changes to tool code**.

---

## Connecting to a different ServiceNow instance

The design binds **one deployment to one instance**: `SERVICENOW_INSTANCE_URL`
is global, the OAuth endpoints are derived from it, and every tool call
targets it. You cannot point a single deployment at two instances — but you
don't need to. The server is stateless and cheap; the pattern is **one MCP
server (container) per instance**, and one EC2 box can host several.

### Adding a second instance with basic auth (simplest)

Add a second service to `deploy/docker-compose.yml` with its own env file and
route a second domain to it in the Caddyfile:

```yaml
  mcp-other:
    build: ..
    restart: unless-stopped
    env_file: .env.other        # its own instance URL + credentials + token
    expose: ["8080"]
```

```
{$DOMAIN} {
	reverse_proxy mcp:8080
}
{$OTHER_DOMAIN} {
	reverse_proxy mcp-other:8080
}
```

`.env.other` needs only `SERVICENOW_INSTANCE_URL`, `SERVICENOW_AUTH_TYPE=basic`,
`SERVICENOW_USERNAME/PASSWORD`, and a *different* `MCP_AUTH_TOKEN`. Register a
second DuckDNS subdomain pointing at the same Elastic IP; Caddy fetches the
extra certificate automatically. Connect with:

```bash
claude mcp add other-instance --scope user --transport http \
  https://<other-domain>/mcp --header "Authorization: Bearer <its-token>"
```

### Adding a second instance with per-user OAuth

Same second service, plus that instance's own Application Registry record
(redirect URL `https://<other-domain>/auth/callback`) and its own
`SERVICENOW_OAUTH_CLIENT_ID/SECRET` + `MCP_PUBLIC_URL=https://<other-domain>`
in `.env.other`. In claude.ai each instance appears as its own connector with
its own sign-in. An OAuth client registered on instance A cannot authorize
users for instance B — ServiceNow OAuth apps are per-instance, which is why
each deployment needs its own record.

### Why not true multi-tenancy?

Letting one endpoint serve many instances (e.g. each user typing their own
instance URL) would require: per-session instance resolution in every tool,
an OAuth app on every target instance, upstream endpoints chosen per request
(FastMCP's `OAuthProxy` binds one upstream at startup), and a token store
keyed by instance. That's a redesign, not a configuration change — and the
per-deployment pattern above delivers the same capability with the
infrastructure doing the isolation.

---

## ServiceNow auth types (service-account side)

Unchanged from before, selected by `SERVICENOW_AUTH_TYPE`:

- `basic` — username/password (the deployed default)
- `oauth` — client-credentials/password grant handled by `AuthManager`, with
  proactive expiry tracking and one-shot 401 refresh (see
  `HTTP_HARDENING_CHANGES.md`)
- `api_key` — static header
- `noauth` — for instances fronted by something else

For private/corporate instances, `SERVICENOW_SSL_CERT_PATH` (custom CA) and
`SERVICENOW_DISABLE_SSL_VERIFY` apply to all ServiceNow calls, including OAuth
token validation.
