"""
Authentication manager for the ServiceNow MCP server.
"""

import base64
import logging
import time
from typing import Any, Dict, Optional, Union

from servicenow_mcp.utils import http_client
from servicenow_mcp.utils.config import AuthConfig, AuthType


logger = logging.getLogger(__name__)

# Timeout for OAuth token requests (seconds)
TOKEN_REQUEST_TIMEOUT = 30


class AuthManager:
    """
    Authentication manager for ServiceNow API.
    
    This class handles authentication with the ServiceNow API using
    different authentication methods.
    """
    
    def __init__(self, config: AuthConfig, instance_url: str = None, ssl_cert_path: Optional[str] = None):
        """
        Initialize the authentication manager.
        
        Args:
            config: Authentication configuration.
            instance_url: ServiceNow instance URL.
            ssl_cert_path: Optional path to SSL certificate for private network instances.
        """
        self.config = config
        self.instance_url = instance_url
        self.ssl_cert_path = ssl_cert_path
        self.token: Optional[str] = None
        self.token_type: Optional[str] = None
        self.token_expires_at: Optional[float] = None
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get the authentication headers for API requests.
        
        Returns:
            Dict[str, str]: Headers to include in API requests.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        if self.config.type == AuthType.BASIC:
            if not self.config.basic:
                raise ValueError("Basic auth configuration is required")
            
            auth_str = f"{self.config.basic.username}:{self.config.basic.password}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        
        elif self.config.type == AuthType.OAUTH:
            if not self.token or self._token_is_expired():
                self._get_oauth_token()

            headers["Authorization"] = f"{self.token_type} {self.token}"
        
        elif self.config.type == AuthType.API_KEY:
            if not self.config.api_key:
                raise ValueError("API key configuration is required")
            
            headers[self.config.api_key.header_name] = self.config.api_key.api_key
        
        return headers
    
    def _get_oauth_token(self):
        """
        Get an OAuth token from ServiceNow.
        
        Raises:
            ValueError: If OAuth configuration is missing or token request fails.
        """
        if not self.config.oauth:
            raise ValueError("OAuth configuration is required")
        oauth_config = self.config.oauth

        # Determine token URL
        token_url = oauth_config.token_url
        if not token_url:
            if not self.instance_url:
                raise ValueError("Instance URL is required for OAuth authentication")
            instance_parts = self.instance_url.split(".")
            if len(instance_parts) < 2:
                raise ValueError(f"Invalid instance URL: {self.instance_url}")
            instance_name = instance_parts[0].split("//")[-1]
            token_url = f"https://{instance_name}.service-now.com/oauth_token.do"

        # Prepare Authorization header
        auth_str = f"{oauth_config.client_id}:{oauth_config.client_secret}"
        auth_header = base64.b64encode(auth_str.encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Explicit cert override for private instances (e.g. corporate CA for TINA);
        # None falls back to the server config (custom cert / disabled / default).
        ssl_verify: Union[str, None] = self.ssl_cert_path if self.ssl_cert_path else None

        # Try client_credentials grant first
        data_client_credentials = {
            "grant_type": "client_credentials"
        }

        logger.info("Attempting client_credentials grant...")
        response = http_client.request(
            "POST",
            token_url,
            headers=headers,
            data=data_client_credentials,
            timeout=TOKEN_REQUEST_TIMEOUT,
            verify=ssl_verify,
            retry_auth=False,
        )

        logger.debug(f"client_credentials response status: {response.status_code}")
        logger.debug(f"client_credentials response body: {response.text}")

        if response.status_code == 200:
            self._store_token(response.json())
            return

        # Try password grant if client_credentials failed
        if oauth_config.username and oauth_config.password:
            data_password = {
                "grant_type": "password",
                "username": oauth_config.username,
                "password": oauth_config.password
            }

            logger.info("Attempting password grant...")
            response = http_client.request(
                "POST",
                token_url,
                headers=headers,
                data=data_password,
                timeout=TOKEN_REQUEST_TIMEOUT,
                verify=ssl_verify,
                retry_auth=False,
            )

            logger.debug(f"password grant response status: {response.status_code}")
            logger.debug(f"password grant response body: {response.text}")

            if response.status_code == 200:
                self._store_token(response.json())
                return

        raise ValueError("Failed to get OAuth token using both client_credentials and password grants.")

    def _store_token(self, token_data: Dict[str, Any]):
        """Store the access token and compute its expiry time."""
        self.token = token_data.get("access_token")
        self.token_type = token_data.get("token_type", "Bearer")

        expires_in = token_data.get("expires_in")
        try:
            # Refresh 60s before actual expiry to avoid using a token that
            # dies mid-request
            self.token_expires_at = time.time() + int(expires_in) - 60 if expires_in else None
        except (TypeError, ValueError):
            self.token_expires_at = None

    def _token_is_expired(self) -> bool:
        """Check whether the stored OAuth token has passed its expiry time."""
        return self.token_expires_at is not None and time.time() >= self.token_expires_at

    def refresh_token(self):
        """Refresh the OAuth token if using OAuth authentication."""
        if self.config.type == AuthType.OAUTH:
            self._get_oauth_token()


class DelegatedAuthManager(AuthManager):
    """AuthManager carrying a per-user ServiceNow token from the MCP OAuth flow.

    When a client connects through the endpoint's ServiceNow OAuth
    (see auth/endpoint_auth.py), each request arrives with that user's own
    ServiceNow access token. This manager wraps it so every tool call runs
    with the user's identity and ACLs instead of the shared service account.

    The token's lifecycle is owned by the endpoint's OAuthProxy (which holds
    the refresh token), so this manager must never try to refresh it.
    """

    def __init__(
        self,
        access_token: str,
        instance_url: str,
        ssl_cert_path: Optional[str] = None,
    ):
        from servicenow_mcp.utils.config import AuthConfig, OAuthConfig

        config = AuthConfig(
            type=AuthType.OAUTH,
            oauth=OAuthConfig(
                client_id="mcp-delegated",
                client_secret="",
                username="",
                password="",
            ),
        )
        super().__init__(config, instance_url, ssl_cert_path)
        self.token = access_token
        self.token_type = "Bearer"
        self.token_expires_at = None

    def _get_oauth_token(self):
        raise ValueError(
            "Delegated ServiceNow token was rejected - the MCP client must "
            "re-authenticate through the OAuth flow."
        )
