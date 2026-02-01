"""
Centralized HTTP client for ServiceNow API requests.

This module provides a unified interface for making HTTP requests with
automatic SSL certificate configuration for private network instances.
"""

import logging
from typing import Any, Dict, Literal, Optional, Union

import requests

from servicenow_mcp.application import get_config

logger = logging.getLogger(__name__)

# Type alias for supported HTTP methods
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


def _get_ssl_verify() -> Union[bool, str]:
    """
    Get the SSL verification setting based on configuration.
    
    Returns:
        Union[bool, str]: Path to .crt file if configured, otherwise True for default SSL verification.
    """
    try:
        config = get_config()
        if config.ssl_cert_path:
            logger.debug(f"Using SSL certificate: {config.ssl_cert_path}")
            return config.ssl_cert_path
    except RuntimeError:
        # Config not initialized yet (e.g., during auth token fetch before full init)
        pass
    return True


def request(
    method: HttpMethod,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """
    Make an HTTP request with SSL certificate configuration.
    
    This is the core request function that all HTTP methods use internally.
    
    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        url: The URL to request.
        headers: Optional headers to include.
        params: Optional query parameters.
        json: Optional JSON body.
        data: Optional form data.
        timeout: Request timeout in seconds.
    
    Returns:
        requests.Response: The response object.
    """
    return requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        json=json,
        data=data,
        timeout=timeout,
        verify=_get_ssl_verify(),
    )


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
