"""
Centralized HTTP client for ServiceNow API requests.

This module provides a unified interface for making HTTP requests with
automatic SSL certificate configuration for private network instances.
"""

import logging
from typing import Any, Dict, Literal, Optional, Union

import requests

logger = logging.getLogger(__name__)

# Type alias for supported HTTP methods
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


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
    ssl_verify = _get_ssl_verify(url)
    
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
    
    # Only add verify if we have a custom cert path
    # Otherwise let requests use its default behavior
    if ssl_verify is not None:
        kwargs["verify"] = ssl_verify
    
    return requests.request(**kwargs)


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
