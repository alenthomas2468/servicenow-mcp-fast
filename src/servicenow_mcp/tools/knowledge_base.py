"""
Knowledge base tools for the ServiceNow MCP server.

This module provides tools for managing knowledge bases, categories, and articles in ServiceNow.
"""

import logging
from typing import Any, Dict, Optional
import json

import requests
from pydantic import Field

from servicenow_mcp.application import mcp, get_auth_manager, get_config
from servicenow_mcp.utils import http_client
from servicenow_mcp.utils.helpers import (
    build_request_data,
    resolve_record_id,
    format_success_response,
    format_error_response,
    format_kb_response,
    format_list_response,
    is_sys_id,
    extract_display_value,
    parse_bool_field
)

# Table constants
KB_KNOWLEDGE_BASE_TABLE = "kb_knowledge_base"
KB_CATEGORY_TABLE = "kb_category"
KB_KNOWLEDGE_TABLE = "kb_knowledge"

logger = logging.getLogger(__name__)

@mcp.tool()
def create_knowledge_base(
    title: str = Field(..., description="Title of the knowledge base"),
    description: Optional[str] = Field(None, description="Description of the knowledge base"),
    owner: Optional[str] = Field(None, description="The specified admin user or group"),
    managers: Optional[str] = Field(None, description="Users who can manage this knowledge base"),
    publish_workflow: str = Field("Knowledge - Instant Publish", description="Publication workflow"),
    retire_workflow: str = Field("Knowledge - Instant Retire", description="Retirement workflow"),
) -> str:
    """Create a new knowledge base in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_KNOWLEDGE_BASE_TABLE}"

    # Build request data
    data = build_request_data(
        required_fields={"title": title},
        optional_fields={
            "description": description,
            "owner": owner,
            "kb_managers": managers,
        }
    )
    data.update({
        "workflow_publish": publish_workflow,
        "workflow_retire": retire_workflow,
    })

    # Make request
    try:
        response = http_client.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        return format_success_response(
            "Knowledge base created successfully",
            kb_id=result.get("sys_id"),
            title=result.get("title"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create knowledge base: {e}")
        return format_error_response("create knowledge base", e)


@mcp.tool()
def list_knowledge_bases(
    limit: int = Field(10, description="Maximum number of knowledge bases to return"),
    offset: int = Field(0, description="Offset for pagination"),
    active: Optional[bool] = Field(None, description="Filter by active status"),
    query: Optional[str] = Field(None, description="Search query for knowledge bases"),
) -> str:
    """List knowledge bases with filtering options."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_KNOWLEDGE_BASE_TABLE}"

    # Build query parameters
    query_params = {
        "sysparm_limit": str(limit),
        "sysparm_offset": str(offset),
        "sysparm_display_value": "true",
    }

    # Build query string
    query_parts = []
    if active is not None:
        query_parts.append(f"active={str(active).lower()}")
    if query:
        query_parts.append(f"titleLIKE{query}^ORdescriptionLIKE{query}")

    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)

    # Make request
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        # Get the JSON response 
        json_response = response.json()
        
        # Safely extract the result
        if isinstance(json_response, dict) and "result" in json_response:
            result = json_response.get("result", [])
        else:
            return "Unexpected response format"

        # Transform the results - create a simpler structure
        knowledge_bases = []
        
        # Handle either string or list
        if isinstance(result, list):
            for kb_item in result:
                if not isinstance(kb_item, dict):
                    continue
                    
                # Safely extract values using helpers
                kb_id = kb_item.get("sys_id", "")
                title = kb_item.get("title", "")
                description = kb_item.get("description", "")
                owner = extract_display_value(kb_item.get("owner"))
                managers = extract_display_value(kb_item.get("kb_managers"))
                is_active = parse_bool_field(kb_item.get("active"))
                
                created = kb_item.get("sys_created_on", "")
                updated = kb_item.get("sys_updated_on", "")
                
                knowledge_bases.append({
                    "id": kb_id,
                    "title": title,
                    "description": description,
                    "owner": owner,
                    "managers": managers,
                    "active": is_active,
                    "created": created,
                    "updated": updated,
                })

        output = {
            "success": True,
            "message": f"Found {len(knowledge_bases)} knowledge bases",
            "knowledge_bases": knowledge_bases,
            "count": len(knowledge_bases),
            "limit": limit,
            "offset": offset,
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to list knowledge bases: {e}")
        return format_error_response("list knowledge bases", e)


@mcp.tool()
def create_category(
    title: str = Field(..., description="Title of the category"),
    knowledge_base: str = Field(..., description="The knowledge base to create the category in"),
    description: Optional[str] = Field(None, description="Description of the category"),
    parent_category: Optional[str] = Field(None, description="Parent category (if creating a subcategory). Sys_id refering to the parent category or sys_id of the parent table."),
    parent_table: Optional[str] = Field(None, description="Parent table (if creating a subcategory). Sys_id refering to the table where the parent category is defined."),
    active: bool = Field(True, description="Whether the category is active"),
) -> str:
    """Create a new category in a knowledge base."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_CATEGORY_TABLE}"

    # Build request data
    data = build_request_data(
        required_fields={"label": title, "kb_knowledge_base": knowledge_base},
        optional_fields={
            "description": description,
            "parent": parent_category,
            "parent_table": parent_table,
            "active": active,
        }
    )
    
    # Make request
    try:
        response = http_client.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        
        return format_success_response(
            "Category created successfully",
            category_id=result.get("sys_id"),
            category_name=result.get("label"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create category: {e}")
        return format_error_response("create category", e)


@mcp.tool()
def create_article(
    title: str = Field(..., description="Title of the article"),
    text: str = Field(..., description="The main body text for the article. Field supports html formatting and wiki markup based on the article_type. HTML is the default."),
    short_description: str = Field(..., description="Short description of the article"),
    knowledge_base: str = Field(..., description="The knowledge base to create the article in"),
    category: str = Field(..., description="Category for the article"),
    keywords: Optional[str] = Field(None, description="Keywords for search"),
    article_type: str = Field("html", description="The type of article. Options are 'text' or 'wiki'."),
) -> str:
    """Create a new knowledge article."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_KNOWLEDGE_TABLE}"

    # Build request data  
    data = build_request_data(
        required_fields={
            "short_description": title,  # ServiceNow uses short_description as title
            "text": text,
            "kb_knowledge_base": knowledge_base,
            "kb_category": category,
        },
        optional_fields={
            "keywords": keywords,
            "article_type": article_type,
        }
    )

    # Make request
    try:
        response = http_client.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return format_success_response(
            "Article created successfully",
            article_id=result.get("sys_id"),
            article_title=result.get("short_description"),
            workflow_state=result.get("workflow_state"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create article: {e}")
        return format_error_response("create article", e)


@mcp.tool()
def update_article(
    article_id: str = Field(..., description="ID of the article to update"),
    title: Optional[str] = Field(None, description="Updated title of the article"),
    text: Optional[str] = Field(None, description="Updated main body text for the article"),
    short_description: Optional[str] = Field(None, description="Updated short description"),
    category: Optional[str] = Field(None, description="Updated category for the article"),
    keywords: Optional[str] = Field(None, description="Updated keywords for search"),
) -> str:
    """Update an existing knowledge article."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_KNOWLEDGE_TABLE}/{article_id}"

    # Build request data
    data = build_request_data(
        required_fields={},
        optional_fields={
            "short_description": title or short_description,
            "text": text,
            "kb_category": category,
            "keywords": keywords,
        }
    )

    # Make request
    try:
        response = http_client.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return format_success_response(
            "Article updated successfully",
            article_id=article_id,
            article_title=result.get("short_description"),
            workflow_state=result.get("workflow_state"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to update article: {e}")
        return format_error_response("update article", e)


@mcp.tool()
def publish_article(
    article_id: str = Field(..., description="ID of the article to publish"),
    workflow_state: str = Field("published", description="The workflow state to set"),
    workflow_version: Optional[str] = Field(None, description="The workflow version to use"),
) -> str:
    """Publish a knowledge article."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_KNOWLEDGE_TABLE}/{article_id}"

    # Build request data
    data = build_request_data(
        required_fields={"workflow_state": workflow_state},
        optional_fields={"workflow_version": workflow_version},
    )

    # Make request
    try:
        response = http_client.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        actual_state = result.get("workflow_state")

        # A knowledge workflow / business rule can veto the transition: ServiceNow
        # answers 200 but hands back the unchanged state. Without this check the
        # tool would report a publish that never happened.
        if actual_state and actual_state.lower() != workflow_state.lower():
            return format_error_response(
                "publish article",
                RuntimeError(
                    f"ServiceNow accepted the request but left the article in "
                    f"'{actual_state}' instead of '{workflow_state}'. Publication on this "
                    f"knowledge base is governed by a knowledge workflow/approval, so the "
                    f"state cannot be set directly through the Table API - publish it from "
                    f"the ServiceNow UI or drive the approval flow."
                ),
            )

        return format_success_response(
            "Article published successfully",
            article_id=article_id,
            article_title=result.get("short_description"),
            workflow_state=actual_state,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to publish article: {e}")
        return format_error_response("publish article", e)


@mcp.tool()
def list_articles(
    limit: int = Field(10, description="Maximum number of articles to return"),
    offset: int = Field(0, description="Offset for pagination"),
    knowledge_base: Optional[str] = Field(None, description="Filter by knowledge base"),
    category: Optional[str] = Field(None, description="Filter by category"),
    query: Optional[str] = Field(None, description="Search query for articles"),
    workflow_state: Optional[str] = Field(None, description="Filter by workflow state"),
) -> str:
    """List knowledge articles with filtering options."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_KNOWLEDGE_TABLE}"

    # Build query parameters
    query_params = {
        "sysparm_limit": str(limit),
        "sysparm_offset": str(offset),
        "sysparm_display_value": "all",
    }

    # Build query string
    query_parts = []
    if knowledge_base:
        query_parts.append(f"kb_knowledge_base.sys_id={knowledge_base}")
    if category:
        query_parts.append(f"kb_category.sys_id={category}")
    if workflow_state:
        query_parts.append(f"workflow_state={workflow_state}")
    if query:
        query_parts.append(f"short_descriptionLIKE{query}^ORtextLIKE{query}")

    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)
    
    # Make request
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        # Get the JSON response
        json_response = response.json()
        
        # Safely extract the result
        if isinstance(json_response, dict) and "result" in json_response:
            result = json_response.get("result", [])
        else:
            return "Unexpected response format"

        # Transform the results
        articles = []
        
        # Handle either string or list
        if isinstance(result, list):
            for article_item in result:
                if not isinstance(article_item, dict):
                    continue
                    
                # Safely extract values using helpers
                article_id = article_item.get("sys_id", "")
                title = article_item.get("short_description", "")
                kb_name = extract_display_value(article_item.get("kb_knowledge_base"))
                cat_name = extract_display_value(article_item.get("kb_category"))
                wf_state = extract_display_value(article_item.get("workflow_state"))
                
                created = article_item.get("sys_created_on", "")
                updated = article_item.get("sys_updated_on", "")
                
                articles.append({
                    "id": article_id,
                    "title": title,
                    "knowledge_base": kb_name,
                    "category": cat_name,
                    "workflow_state": wf_state,
                    "created": created,
                    "updated": updated,
                })

        output = {
            "success": True,
            "message": f"Found {len(articles)} articles",
            "articles": articles,
            "count": len(articles),
            "limit": limit,
            "offset": offset,
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to list articles: {e}")
        return format_error_response("list articles", e)


@mcp.tool()
def get_article(
    article_id: str = Field(..., description="ID of the article to get"),
) -> str:
    """Get a specific knowledge article by ID."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_KNOWLEDGE_TABLE}/{article_id}"

    # Build query parameters
    query_params = {
        "sysparm_display_value": "true",
    }

    # Make request
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        # Get the JSON response
        json_response = response.json()
        
        # Safely extract the result
        if isinstance(json_response, dict) and "result" in json_response:
            result = json_response.get("result", {})
        else:
             return "Unexpected response format"

        if not result or not isinstance(result, dict):
            return f"Article with ID {article_id} not found"

        # Extract values safely using helpers
        article_id = result.get("sys_id", "")
        title = result.get("short_description", "")
        text = result.get("text", "")
        knowledge_base = extract_display_value(result.get("kb_knowledge_base"))
        category = extract_display_value(result.get("kb_category"))
        workflow_state = extract_display_value(result.get("workflow_state"))
        author = extract_display_value(result.get("author"))
        
        keywords = result.get("keywords", "")
        article_type = result.get("article_type", "")
        views = result.get("view_count", "0")
        created = result.get("sys_created_on", "")
        updated = result.get("sys_updated_on", "")

        article = {
            "id": article_id,
            "title": title,
            "text": text,
            "knowledge_base": knowledge_base,
            "category": category,
            "workflow_state": workflow_state,
            "created": created,
            "updated": updated,
            "author": author,
            "keywords": keywords,
            "article_type": article_type,
            "views": views,
        }

        output = {
            "success": True,
            "message": "Article retrieved successfully",
            "article": article,
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to get article: {e}")
        return format_error_response("get article", e)


@mcp.tool()
def list_categories(
    limit: int = Field(10, description="Maximum number of categories to return"),
    offset: int = Field(0, description="Offset for pagination"),
    knowledge_base: Optional[str] = Field(None, description="Filter by knowledge base ID"),
    parent_category: Optional[str] = Field(None, description="Filter by parent category ID"),
    active: Optional[bool] = Field(None, description="Filter by active status"),
    query: Optional[str] = Field(None, description="Search query for categories"),
) -> str:
    """List categories in a knowledge base."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/{KB_CATEGORY_TABLE}"

    # Build query parameters
    query_params = {
        "sysparm_limit": str(limit),
        "sysparm_offset": str(offset),
        "sysparm_display_value": "all",
    }

    # Build query string
    query_parts = []
    if knowledge_base:
        query_parts.append(f"kb_knowledge_base.sys_id={knowledge_base}")
    if parent_category:
        query_parts.append(f"parent.sys_id={parent_category}")
    if active is not None:
        query_parts.append(f"active={str(active).lower()}")
    if query:
        query_parts.append(f"labelLIKE{query}^ORdescriptionLIKE{query}")

    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)

    # Make request
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        # Get the JSON response
        json_response = response.json()
        
        # Safely extract the result
        if isinstance(json_response, dict) and "result" in json_response:
            result = json_response.get("result", [])
        else:
             return "Unexpected response format"

        # Transform the results
        categories = []
        
        # Handle either string or list
        if isinstance(result, list):
            for category_item in result:
                if not isinstance(category_item, dict):
                    continue
                    
                # Safely extract values using helpers
                category_id = category_item.get("sys_id", "")
                title = category_item.get("label", "")
                description = category_item.get("description", "")
                kb_val = extract_display_value(category_item.get("kb_knowledge_base"))
                parent_val = extract_display_value(category_item.get("parent"))
                is_active = parse_bool_field(category_item.get("active"))
                
                created = category_item.get("sys_created_on", "")
                updated = category_item.get("sys_updated_on", "")
                
                categories.append({
                    "id": category_id,
                    "title": title,
                    "description": description,
                    "knowledge_base": kb_val,
                    "parent_category": parent_val,
                    "active": is_active,
                    "created": created,
                    "updated": updated,
                })

        output = {
            "success": True,
            "message": f"Found {len(categories)} categories",
            "categories": categories,
            "count": len(categories),
            "limit": limit,
            "offset": offset,
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to list categories: {e}")
        return format_error_response("list categories", e)
