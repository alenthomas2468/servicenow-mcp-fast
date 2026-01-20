"""
Logging utility for the ServiceNow MCP server.
Provides functionality to intercept and log HTTP requests and responses.
"""

import json
import logging
import requests
from typing import Any, Dict, Optional
from requests.structures import CaseInsensitiveDict

logger = logging.getLogger("servicenow_mcp.http")

def _redact_headers(headers: CaseInsensitiveDict) -> Dict[str, str]:
    """Redact sensitive headers."""
    redacted = dict(headers)
    for key in redacted:
        if key.lower() in ("authorization", "x-servicenow-api-key", "cookie"):
            redacted[key] = "[REDACTED]"
    return redacted

def _safe_json_parse(text: str) -> Any:
    """Attempt to parse JSON safely, returning original text if not JSON."""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text

def setup_request_logging():
    """
    Monkey-patch requests.Session.request to log detailed request/response info.
    This captures all requests made by the requests library.
    """
    original_request = requests.Session.request

    def logged_request(self, method, url, *args, **kwargs):
        # Log Request
        try:
            log_data = {
                "url": url,
                "method": method,
                "headers": _redact_headers(CaseInsensitiveDict(kwargs.get("headers", {}))),
            }
            
            # Helper to check for json or data in kwargs
            if "json" in kwargs:
                log_data["body"] = kwargs["json"]
            elif "data" in kwargs:
                 log_data["body"] = _safe_json_parse(kwargs["data"])
            
            logger.info(f"Request: {json.dumps(log_data, indent=2)}")
        except Exception as e:
            logger.warning(f"Failed to log request: {e}")

        # Execute Request
        response = original_request(self, method, url, *args, **kwargs)

        # Log Response
        try:
            log_data = {
                "status_code": response.status_code,
                "url": response.url,
                "headers": _redact_headers(response.headers),
                "body": _safe_json_parse(response.text),
            }
            logger.info(f"Response: {json.dumps(log_data, indent=2)}")
        except Exception as e:
            logger.warning(f"Failed to log response: {e}")

        return response

    # Apply patch
    requests.Session.request = logged_request
