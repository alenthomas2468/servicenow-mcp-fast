# ServiceNow MCP Server — HTTP Layer Hardening

**Commit:** `a5cc4a1` — *feat: harden HTTP layer with pooling, retries, and structured errors*

**Files changed:**
- `src/servicenow_mcp/utils/http_client.py`
- `src/servicenow_mcp/auth/auth_manager.py`
- `src/servicenow_mcp/utils/helpers.py`

**Scope guarantee:** internal changes only. All ~60 MCP tool signatures and their success JSON responses are unchanged, so nothing changes for any connected MCP client (Claude Desktop, claude.ai, Cursor, MCP Inspector, etc.). The SSL behavior for private instances — `SERVICENOW_SSL_CERT_PATH` (TINA's corporate CA certificate) and `SERVICENOW_DISABLE_SSL_VERIFY` — is preserved exactly.

---

## Problems before this change

1. **A new TCP + TLS connection was opened for every single API call.** `http_client.request()` called `requests.request(...)` directly, which creates and tears down a connection each time. Against a remote ServiceNow instance this adds a full TCP + TLS handshake (typically 50–150 ms) to *every* tool call.
2. **No retry anywhere.** One transient 429 (rate limit), 502/503/504 (gateway hiccup), or dropped connection failed the whole MCP tool call.
3. **Expired OAuth tokens were fatal.** The token was fetched once and cached forever. `refresh_token()` existed but nothing ever called it — after expiry (typically 30 min), every request returned 401 until the server was restarted.
4. **OAuth token requests had no timeout** and bypassed the central HTTP client, so they ignored the `SERVICENOW_DISABLE_SSL_VERIFY` setting and could hang indefinitely.
5. **Error responses were unstructured and lossy.** Success responses were JSON, but errors were plain strings like `Failed to create incident: 403 Client Error`. Worse, `raise_for_status()` discarded the response body — which is where ServiceNow puts the actual reason ("Insufficient rights", "ACL denied on incident", invalid field name, etc.).
6. **A hibernating PDI produced misleading errors.** The developer instance answers API calls with an HTML wake-up page (often HTTP 200). Parsing it as JSON failed with an opaque error, or worse, `resolve_record_id()` swallowed it and reported a real incident as "not found".

---

## Change 1 — Connection pooling (`http_client.py`)

A single module-level `requests.Session` is created at import time and used by every request:

```python
def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        backoff_factor=0.5,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=_RETRYABLE_METHODS,
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

_session = _build_session()
```

- TCP/TLS connections are now reused across tool calls (keep-alive), removing the per-call handshake cost.
- Pool sized at 10 connection pools × 20 connections, comfortable for the multi-client HTTP deployment.
- The debug request-logging feature (`logging_utils.setup_request_logging`) monkey-patches `requests.Session.request` at the **class** level, so the pooled session picks it up automatically — no conflict.

## Change 2 — Automatic retry with backoff

Mounted on the shared session (see code above):

| Setting | Value | Rationale |
|---|---|---|
| `total` | 3 attempts | Covers transient blips without long stalls |
| `backoff_factor` | 0.5 | Waits 0.5 s / 1 s / 2 s between attempts |
| `status_forcelist` | 429, 502, 503, 504 | Rate limits and gateway errors — the retryable class |
| `allowed_methods` | GET, HEAD, OPTIONS, PUT, PATCH, DELETE | **POST is deliberately excluded** so a retried "create incident" can never produce a duplicate record |
| `respect_retry_after_header` | true | Honors ServiceNow's own `Retry-After` on 429 |
| `raise_on_status` | false | After retries are exhausted the response is returned, so the existing per-tool error handling still runs |

Connection-level failures (connect errors) retry for all methods, which is safe because the request never reached the server.

## Change 3 — OAuth self-healing

**3a. One-shot 401 refresh-and-replay (`http_client.request`):**
```python
response = _session.request(**kwargs)

if response.status_code == 401 and retry_auth:
    refreshed_headers = _refresh_oauth_headers(headers)
    if refreshed_headers is not None:
        kwargs["headers"] = refreshed_headers
        response = _session.request(**kwargs)
```
- Only activates when the server's auth type is OAuth; basic/API-key setups return the 401 untouched.
- The token request itself is issued with `retry_auth=False`, so a rejected token request can never recurse into another refresh (infinite-loop guard).
- Exactly one replay — if the fresh token is also rejected, the 401 surfaces normally.

**3b. Proactive expiry tracking (`auth_manager.py`):**
- `_store_token()` records `expires_in` from the token response and computes `token_expires_at = now + expires_in − 60` (refresh 60 s early so a token can't die mid-request).
- `get_headers()` now checks `_token_is_expired()` and re-fetches before sending, so most requests never hit the 401 path at all.
- Missing/invalid `expires_in` is tolerated (falls back to refresh-on-401 behavior).

**3c. Token request hygiene (`auth_manager.py`):**
- Token requests now go through the central `http_client` — they gain the connection pool, the retry policy, and a **30-second timeout** (previously unbounded).
- SSL: if an explicit cert path was passed to `AuthManager` (TINA's corporate CA), it is forwarded as an explicit `verify` override — behavior identical to before. If not, the server config decides (custom cert / disabled / system default), which means the token call now honors `SERVICENOW_DISABLE_SSL_VERIFY` for the first time.

## Change 4 — Structured error responses (`helpers.py`)

`format_error_response()` now returns JSON in the same shape as success responses, and preserves ServiceNow's own error body:

Before:
```
Failed to update incident: 403 Client Error: Forbidden for url: ...
```

After:
```json
{
  "success": false,
  "message": "Failed to update incident",
  "error": "403 Client Error: Forbidden for url: ...",
  "status_code": 403,
  "servicenow_error": {
    "message": "Insufficient rights",
    "detail": "ACL denied on incident"
  }
}
```

Because every tool already routes errors through this one helper (directly or via the `servicenow_api_call` decorator), all ~60 tools got structured errors without touching a single tool module. An LLM client can now read *why* a call failed and correct itself (fix a field name, pick a different record, tell the user about missing permissions) instead of guessing.

## Change 5 — Hibernating PDI detection (`http_client.py`, `helpers.py`)

New exception raised centrally after every response:

```python
class InstanceHibernatingError(requests.RequestException):
    def __init__(self):
        super().__init__(
            "ServiceNow instance is hibernating (developer PDIs sleep when idle). "
            "Wake it at https://developer.servicenow.com and retry."
        )
```

- Detection: response `Content-Type` is HTML **and** the first 4 KB contain "hibernat" (case-insensitive) — the signature of the PDI wake-up page, which arrives with HTTP 200 and previously caused a confusing JSON parse failure.
- It subclasses `requests.RequestException`, so every existing `except requests.RequestException` handler in the tools formats it into the structured error JSON automatically.
- `resolve_record_id()` explicitly re-raises it instead of swallowing it, so a hibernating instance is no longer misreported as "Incident not found".

## Constraint preserved — TINA corporate certificate

The organization certificate for the corporate instance (TINA) was the original reason the centralized `http_client` exists. The SSL decision flow is byte-for-byte the same:

1. `SERVICENOW_DISABLE_SSL_VERIFY=true` → verification disabled (with warning) — dev only.
2. `SERVICENOW_SSL_CERT_PATH` set and file exists → that CA bundle verifies every request (TINA case).
3. Neither → the `requests` default CA bundle (public instances / PDI).

New: `http_client.request()` accepts an explicit `verify` override parameter, used only by the OAuth token fetch to preserve its pre-existing explicit-cert behavior.

---

## Verification (no live instance required)

Per project convention, verification ran at the MCP layer with dummy credentials and mocked HTTP responses — nothing touched TINA or the (hibernating) PDI. **16/16 checks passed:**

1. All tool modules import; 50+ tools register on the FastMCP instance
2. Retry adapter mounted with total=3 and 429/502/503/504 in the force list
3. POST excluded from retry; GET included
4. Hibernation HTML page raises `InstanceHibernatingError` with the wake-up URL in the message
5. Hibernation error formats as actionable structured JSON
6. `resolve_record_id` re-raises hibernation instead of returning "not found"
7. A 401 triggers token refresh and exactly one replay
8. The replayed request carries the fresh `Authorization` header
9. `retry_auth=False` performs a single call — no recursion on token-endpoint 401
10. Error JSON contains `status_code` and the `servicenow_error` body
11. Token expiry stored ~29 minutes ahead for `expires_in=1800`
12. Expired token detected by `_token_is_expired()`
13. Missing `expires_in` tolerated (no expiry, no false "expired")
14. Explicit cert path (TINA case) passed through to the session verbatim
15. `disable_ssl_verify` config flag passed through as `verify=False`
16. Default case sends no `verify` kwarg (requests default CA bundle)

## Impact summary

| Area | Before | After |
|---|---|---|
| Latency | TLS handshake on every call | Connections pooled and reused |
| Transient failures | Immediate tool-call failure | Up to 3 retries with backoff |
| Duplicate-create risk | n/a | POST never retried |
| OAuth token expiry | Fatal until server restart | Proactive refresh + 401 self-heal |
| Token request | No timeout, ignored SSL-disable flag | 30 s timeout, full SSL config honored |
| Error responses | Plain string, ServiceNow reason lost | Structured JSON with status + ServiceNow error body |
| Hibernating PDI | Opaque JSON error / false "not found" | Clear "wake it at developer.servicenow.com" message |
| MCP client compatibility | — | Unchanged (internal only) |
| TINA corporate cert | — | Behavior preserved exactly |
