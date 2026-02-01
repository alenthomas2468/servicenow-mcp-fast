"""
Centralized HTTP client for ServiceNow API requests.

This module provides a unified interface for making HTTP requests with
automatic SSL certificate configuration for private network instances.
"""

import logging
from typing import Any, Dict, Optional, Union

import requests

from servicenow_mcp.application import get_config

logger = logging.getLogger(__name__)


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


def get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """
    Make a GET request with SSL certificate configuration.
    
    Args:
        url: The URL to request.
        headers: Optional headers to include.
        params: Optional query parameters.
        timeout: Request timeout in seconds.
    
    Returns:
        requests.Response: The response object.
    """
    return requests.get(
        url,
        headers=headers,
        params=params,
        timeout=timeout,
        verify=_get_ssl_verify(),
    )


def post(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """
    Make a POST request with SSL certificate configuration.
    
    Args:
        url: The URL to request.
        headers: Optional headers to include.
        json: Optional JSON body.
        data: Optional form data.
        timeout: Request timeout in seconds.
    
    Returns:
        requests.Response: The response object.
    """
    return requests.post(
        url,
        headers=headers,
        json=json,
        data=data,
        timeout=timeout,
        verify=_get_ssl_verify(),
    )


def put(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """
    Make a PUT request with SSL certificate configuration.
    
    Args:
        url: The URL to request.
        headers: Optional headers to include.
        json: Optional JSON body.
        timeout: Request timeout in seconds.
    
    Returns:
        requests.Response: The response object.
    """
    return requests.put(
        url,
        headers=headers,
        json=json,
        timeout=timeout,
        verify=_get_ssl_verify(),
    )


def patch(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> requests.Response:
    """
    Make a PATCH request with SSL certificate configuration.
    
    Args:
        url: The URL to request.
        headers: Optional headers to include.
        json: Optional JSON body.
        timeout: Request timeout in seconds.
    
    Returns:
        requests.Response: The response object.
    """
    return requests.patch(
        url,
        headers=headers,
        json=json,
        timeout=timeout,
        verify=_get_ssl_verify(),
    )


def delete(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> requests.Response:
    """
    Make a DELETE request with SSL certificate configuration.
    
    Args:
        url: The URL to request.
        headers: Optional headers to include.
        timeout: Request timeout in seconds.
    
    Returns:
        requests.Response: The response object.
    """
    return requests.delete(
        url,
        headers=headers,
        timeout=timeout,
        verify=_get_ssl_verify(),
    )
