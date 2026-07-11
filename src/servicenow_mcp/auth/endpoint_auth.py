"""
Authentication for the MCP endpoint itself.

This is the auth MCP clients use to reach THIS server, as opposed to
auth_manager.py, which is how this server talks to ServiceNow.

Modes (combinable, chosen by environment variables):

1. ServiceNow OAuth (SERVICENOW_OAUTH_CLIENT_ID + SERVICENOW_OAUTH_CLIENT_SECRET
   + MCP_PUBLIC_URL): claude.ai / Claude Desktop custom connectors show a
   ServiceNow sign-in when connecting. Each user authorizes with their own
   ServiceNow account, and every tool call then runs with THAT user's token
   and permissions (see DelegatedAuthManager / get_auth_manager()).
   Requires an "OAuth API endpoint for external clients" record in the
   instance's Application Registry whose redirect URL is
   <MCP_PUBLIC_URL>/auth/callback.

2. Static bearer token (MCP_AUTH_TOKEN): any client that can send an
   Authorization header (Claude Code, IDEs, scripts, LangChain, ...) keeps
   working exactly as before. These calls run as the shared service account
   from SERVICENOW_USERNAME/PASSWORD.

3. Neither set: the endpoint is UNAUTHENTICATED - local development only.

Both 1 and 2 set -> MultiAuth accepts either credential on the same endpoint,
which keeps the server compatible with the widest range of MCP clients.
"""

import logging
import os
import time
from typing import Optional, Union

import httpx
from fastmcp.server.auth import (
    AuthProvider,
    MultiAuth,
    OAuthProxy,
    StaticTokenVerifier,
    TokenVerifier,
)
from fastmcp.server.auth.auth import AccessToken

from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)

# Marker placed in AccessToken.claims so get_auth_manager() can tell a
# per-user ServiceNow OAuth session apart from a static-token session.
SERVICENOW_OAUTH_CLAIM = "servicenow-user-oauth"

# How long a successful upstream token validation is trusted before the next
# ServiceNow round-trip. Every MCP HTTP request re-verifies the token, so
# without this cache each tool call would cost an extra API request.
_VERIFY_CACHE_TTL = 60.0

# Probe endpoint used to validate a user token. Any REST call works: a valid
# token yields 200 (or 403 if the user lacks the table ACL - still proves the
# token is alive), an invalid/expired one yields 401.
_PROBE_PATH = "/api/now/table/sys_user"
_PROBE_PARAMS = {"sysparm_limit": "1", "sysparm_fields": "sys_id"}


class ServiceNowTokenVerifier(TokenVerifier):
    """Validates a ServiceNow OAuth access token by probing the REST API.

    Used as the OAuthProxy's upstream token verifier: after the proxy swaps
    the client's FastMCP JWT for the stored ServiceNow token, this class
    confirms the ServiceNow token is still valid and tags the result so the
    tool layer knows to impersonate the user.
    """

    def __init__(
        self,
        instance_url: str,
        ssl_verify: Union[bool, str, None] = None,
        cache_ttl: float = _VERIFY_CACHE_TTL,
    ):
        super().__init__()
        self.instance_url = instance_url.rstrip("/")
        self.cache_ttl = cache_ttl
        # httpx verify: True (default CAs), False (disabled), or a CA path
        self._ssl_verify = True if ssl_verify is None else ssl_verify
        self._cache: dict[str, tuple[float, AccessToken]] = {}

    def _cache_get(self, token: str) -> Optional[AccessToken]:
        entry = self._cache.get(token)
        if entry and entry[0] > time.monotonic():
            return entry[1]
        self._cache.pop(token, None)
        return None

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        cached = self._cache_get(token)
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(verify=self._ssl_verify, timeout=15) as client:
                response = await client.get(
                    f"{self.instance_url}{_PROBE_PATH}",
                    params=_PROBE_PARAMS,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
        except httpx.HTTPError as e:
            logger.warning(f"ServiceNow token validation request failed: {e}")
            return None

        # 401 = bad/expired token. 403 = valid token, user lacks the table
        # ACL - still authenticated. Anything HTML (e.g. a hibernating PDI's
        # wake-up page) is not proof of a valid token, so reject it.
        content_type = response.headers.get("Content-Type", "")
        is_json = "application/json" in content_type
        if response.status_code == 401 or not (
            is_json and response.status_code in (200, 403)
        ):
            logger.info(
                f"ServiceNow rejected user token (status {response.status_code})"
            )
            return None

        access_token = AccessToken(
            token=token,
            client_id="servicenow-user",
            scopes=["useraccount"],
            expires_at=None,  # upstream expiry is tracked by the OAuthProxy
            claims={"mode": SERVICENOW_OAUTH_CLAIM},
        )
        self._cache[token] = (time.monotonic() + self.cache_ttl, access_token)
        return access_token


def build_endpoint_auth(config: ServerConfig) -> Optional[AuthProvider]:
    """Assemble the endpoint auth provider from environment variables.

    Returns None when nothing is configured (unauthenticated endpoint).
    """
    static_token = os.environ.get("MCP_AUTH_TOKEN")
    oauth_client_id = os.environ.get("SERVICENOW_OAUTH_CLIENT_ID")
    oauth_client_secret = os.environ.get("SERVICENOW_OAUTH_CLIENT_SECRET")
    public_url = os.environ.get("MCP_PUBLIC_URL")

    static_verifier = None
    if static_token:
        static_verifier = StaticTokenVerifier(
            tokens={
                static_token: {
                    "client_id": "servicenow-mcp-client",
                    "scopes": ["servicenow:full"],
                }
            }
        )

    proxy = None
    if oauth_client_id or oauth_client_secret:
        if not (oauth_client_id and oauth_client_secret and public_url):
            raise ValueError(
                "ServiceNow OAuth needs all three of SERVICENOW_OAUTH_CLIENT_ID, "
                "SERVICENOW_OAUTH_CLIENT_SECRET and MCP_PUBLIC_URL "
                "(e.g. https://tina-mcp.duckdns.org)"
            )
        instance = config.instance_url.rstrip("/")
        ssl_verify: Union[bool, str, None] = None
        if config.disable_ssl_verify:
            ssl_verify = False
        elif config.ssl_cert_path:
            ssl_verify = config.ssl_cert_path
        proxy = OAuthProxy(
            upstream_authorization_endpoint=f"{instance}/oauth_auth.do",
            upstream_token_endpoint=f"{instance}/oauth_token.do",
            upstream_client_id=oauth_client_id,
            upstream_client_secret=oauth_client_secret,
            token_verifier=ServiceNowTokenVerifier(instance, ssl_verify=ssl_verify),
            base_url=public_url,
            redirect_path="/auth/callback",
            # The Application Registry record is created with
            # send_client_credentials_as=request_body_parameter
            token_endpoint_auth_method="client_secret_post",
            valid_scopes=["useraccount"],
        )
        logger.info(
            f"ServiceNow OAuth ENABLED for the MCP endpoint "
            f"(users sign in at {instance}, public URL {public_url})"
        )

    if static_verifier:
        logger.info("Static bearer token authentication ENABLED for the MCP endpoint")

    if proxy and static_verifier:
        return MultiAuth(server=proxy, verifiers=[static_verifier])
    if proxy:
        return proxy
    return static_verifier
