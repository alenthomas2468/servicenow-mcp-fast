"""
Centralized HTTP client for ServiceNow API requests.

This module provides a unified interface for making HTTP requests with:
- A shared connection pool (one Session, TCP/TLS reuse across all tool calls)
- Automatic retry with backoff for transient failures (429, 502, 503, 504)
- Automatic SSL certificate configuration for private network instances
- Detection of hibernating developer (PDI) instances
- A one-shot OAuth token refresh when a request comes back 401
"""

import logging
from typing import Any, Dict, Literal, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Type alias for supported HTTP methods
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]

# Methods safe to retry after the request may already have reached the server.
# POST is excluded so a retried create can never produce duplicate records.
_RETRYABLE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE"})


class InstanceHibernatingError(requests.RequestException):
    """Raised when ServiceNow answers with a hibernation page instead of the API."""

    def __init__(self):
        super().__init__(
            "ServiceNow instance is hibernating (developer PDIs sleep when idle). "
            "Wake it at https://developer.servicenow.com and retry."
        )


def _build_session() -> requests.Session:
    """Create the shared Session with connection pooling and retry policy."""
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


def _get_ssl_verify(url: str = None) -> Union[bool, str, None]:
    """
    Get the SSL verification setting based on configuration.

    Returns None (use requests default), False (disable), or certificate path.

    Args:
        url: The URL being requested (not used, kept for API compatibility).

    Returns:
        Union[bool, str, None]: False to disable, path to .crt if configured, None for default.
    """
    import os

    try:
        from servicenow_mcp.application import get_config
        config = get_config()

        # Check if SSL verification is explicitly disabled
        if config.disable_ssl_verify:
            logger.warning("SSL verification is DISABLED - connection is not secure!")
            return False

        # If custom SSL cert is configured, use it for all requests
        if config.ssl_cert_path and config.ssl_cert_path.strip():
            cert_path = config.ssl_cert_path.strip()
            if os.path.exists(cert_path):
                logger.debug(f"Using custom SSL certificate: {cert_path}")
                return cert_path
            else:
                logger.warning(f"SSL certificate file not found: {cert_path}")

        # No custom cert - return None to use requests library default
        return None

    except RuntimeError:
        # Config not initialized yet
        return None
    except Exception as e:
        logger.warning(f"Error getting SSL config: {e}")
        return None


def _raise_if_hibernating(response: requests.Response) -> None:
    """Raise InstanceHibernatingError if the response is a PDI hibernation page.

    A hibernating PDI answers API calls with an HTML wake-up page (often with
    status 200), which otherwise surfaces as an opaque JSON parse error.
    """
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return
    if b"hibernat" in response.content[:4096].lower():
        raise InstanceHibernatingError()


def _refresh_oauth_headers(original_headers: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """After a 401, refresh the OAuth token and return updated headers.

    Returns None when the server is not using OAuth (or is not initialized),
    meaning the 401 should be returned to the caller as-is.
    """
    try:
        from servicenow_mcp.application import get_auth_manager
        from servicenow_mcp.utils.config import AuthType

        auth_manager = get_auth_manager()
        if auth_manager.config.type != AuthType.OAUTH:
            return None

        logger.info("Received 401 - refreshing OAuth token and retrying once")
        auth_manager.refresh_token()
        headers = dict(original_headers or {})
        headers.update(auth_manager.get_headers())
        return headers
    except RuntimeError:
        # Auth manager not initialized
        return None
    except Exception as e:
        logger.warning(f"OAuth token refresh after 401 failed: {e}")
        return None


def request(
    method: HttpMethod,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    verify: Union[bool, str, None] = None,
    retry_auth: bool = True,
) -> requests.Response:
    """
    Make an HTTP request with pooling, retries, and SSL certificate configuration.

    This is the core request function that all HTTP methods use internally.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        url: The URL to request.
        headers: Optional headers to include.
        params: Optional query parameters.
        json: Optional JSON body.
        data: Optional form data.
        timeout: Request timeout in seconds.
        verify: Explicit SSL verify override (cert path or False). None means
            use the server configuration (custom cert / disabled / default).
        retry_auth: Whether a 401 triggers a one-shot OAuth token refresh and
            replay. Must be False for the token request itself.

    Returns:
        requests.Response: The response object.

    Raises:
        InstanceHibernatingError: If the instance answers with a hibernation page.
    """
    if verify is None:
        verify = _get_ssl_verify(url)

    # Build request kwargs
    kwargs = {
        "method": method,
        "url": url,
        "headers": headers,
        "params": params,
        "json": json,
        "data": data,
        "timeout": timeout,
    }

    # Only add verify if we have a custom cert path or an explicit override
    # Otherwise let requests use its default behavior
    if verify is not None:
        kwargs["verify"] = verify

    response = _session.request(**kwargs)

    if response.status_code == 401 and retry_auth:
        refreshed_headers = _refresh_oauth_headers(headers)
        if refreshed_headers is not None:
            kwargs["headers"] = refreshed_headers
            response = _session.request(**kwargs)

    _raise_if_hibernating(response)
    return response


def get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """Make a GET request with SSL certificate configuration."""
    return request("GET", url, headers=headers, params=params, timeout=timeout)


def post(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """Make a POST request with SSL certificate configuration."""
    return request("POST", url, headers=headers, json=json, data=data, timeout=timeout)


def put(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """Make a PUT request with SSL certificate configuration."""
    return request("PUT", url, headers=headers, json=json, timeout=timeout)


def patch(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """Make a PATCH request with SSL certificate configuration."""
    return request("PATCH", url, headers=headers, json=json, timeout=timeout)


def delete(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> requests.Response:
    """Make a DELETE request with SSL certificate configuration."""
    return request("DELETE", url, headers=headers, timeout=timeout)
