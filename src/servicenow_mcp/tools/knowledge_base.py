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

    api_url = f"{config.api_url}/table/kb_knowledge_base"

    # Build request data
    data = {
        "title": title,
        "workflow_publish": publish_workflow,
        "workflow_retire": retire_workflow,
    }

    if description:
        data["description"] = description
    if owner:
        data["owner"] = owner
    if managers:
        data["kb_managers"] = managers

    # Make request
    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        output = {
            "success": True,
            "message": "Knowledge base created successfully",
            "kb_id": result.get("sys_id"),
            "kb_name": result.get("title"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to create knowledge base: {e}")
        return f"Failed to create knowledge base: {str(e)}"


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

    api_url = f"{config.api_url}/table/kb_knowledge_base"

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
        response = requests.get(
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
                    
                # Safely extract values
                kb_id = kb_item.get("sys_id", "")
                title = kb_item.get("title", "")
                description = kb_item.get("description", "")
                
                # Extract nested values safely
                owner = ""
                if isinstance(kb_item.get("owner"), dict):
                    owner = kb_item["owner"].get("display_value", "")
                
                managers = ""
                if isinstance(kb_item.get("kb_managers"), dict):
                    managers = kb_item["kb_managers"].get("display_value", "")
                
                is_active = False
                if kb_item.get("active") == "true":
                    is_active = True
                
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
        return f"Failed to list knowledge bases: {str(e)}"


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

    api_url = f"{config.api_url}/table/kb_category"

    # Build request data
    data = {
        "label": title,
        "kb_knowledge_base": knowledge_base,
        "active": str(active).lower(),
    }

    if description:
        data["description"] = description
    if parent_category:
        data["parent"] = parent_category
    if parent_table:
        data["parent_table"] = parent_table
    
    # Make request
    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        
        output = {
            "success": True,
            "message": "Category created successfully",
            "category_id": result.get("sys_id"),
            "category_name": result.get("label"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to create category: {e}")
        return f"Failed to create category: {str(e)}"


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

    api_url = f"{config.api_url}/table/kb_knowledge"

    # Build request data
    data = {
        "short_description": short_description, # Servicenow typically uses short_description as title
        "text": text,
        "kb_knowledge_base": knowledge_base,
        "kb_category": category,
        "article_type": article_type,
    }
    
    # If title is passed explicitly and differs from short_description, note that 
    # we mapped short_description param to short_description field. 
    # If the user meant 'title' param to be the main title, we use that.
    # The original code mapped params.title -> short_description if present.
    # We will favor the 'title' param if it's considered the main title.
    # Actually, let's treat 'short_description' param as the primary short_description.
    # If 'title' varies, we might overwrite, but typically they are the same in SN usage here.
    if title:
        data["short_description"] = title

    if keywords:
        data["keywords"] = keywords

    # Make request
    try:
        response = requests.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        output = {
            "success": True,
            "message": "Article created successfully",
            "article_id": result.get("sys_id"),
            "article_title": result.get("short_description"),
            "workflow_state": result.get("workflow_state"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to create article: {e}")
        return f"Failed to create article: {str(e)}"


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

    api_url = f"{config.api_url}/table/kb_knowledge/{article_id}"

    # Build request data
    data = {}

    if title:
        data["short_description"] = title
    if text:
        data["text"] = text
    if short_description:
        data["short_description"] = short_description
    if category:
        data["kb_category"] = category
    if keywords:
        data["keywords"] = keywords

    # Make request
    try:
        response = requests.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        output = {
            "success": True,
            "message": "Article updated successfully",
            "article_id": article_id,
            "article_title": result.get("short_description"),
            "workflow_state": result.get("workflow_state"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to update article: {e}")
        return f"Failed to update article: {str(e)}"


@mcp.tool()
def publish_article(
    article_id: str = Field(..., description="ID of the article to publish"),
    workflow_state: str = Field("published", description="The workflow state to set"),
    workflow_version: Optional[str] = Field(None, description="The workflow version to use"),
) -> str:
    """Publish a knowledge article."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/kb_knowledge/{article_id}"

    # Build request data
    data = {
        "workflow_state": workflow_state,
    }

    if workflow_version:
        data["workflow_version"] = workflow_version

    # Make request
    try:
        response = requests.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        output = {
            "success": True,
            "message": "Article published successfully",
            "article_id": article_id,
            "article_title": result.get("short_description"),
            "workflow_state": result.get("workflow_state"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to publish article: {e}")
        return f"Failed to publish article: {str(e)}"


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

    api_url = f"{config.api_url}/table/kb_knowledge"

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
        response = requests.get(
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
                    
                # Safely extract values
                article_id = article_item.get("sys_id", "")
                title = article_item.get("short_description", "")
                
                # Extract nested values safely
                kb_name = ""
                if isinstance(article_item.get("kb_knowledge_base"), dict):
                    kb_name = article_item["kb_knowledge_base"].get("display_value", "")
                
                cat_name = ""
                if isinstance(article_item.get("kb_category"), dict):
                    cat_name = article_item["kb_category"].get("display_value", "")
                
                wf_state = ""
                if isinstance(article_item.get("workflow_state"), dict):
                    wf_state = article_item["workflow_state"].get("display_value", "")
                
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
        return f"Failed to list articles: {str(e)}"


@mcp.tool()
def get_article(
    article_id: str = Field(..., description="ID of the article to get"),
) -> str:
    """Get a specific knowledge article by ID."""
    config = get_config()
    auth_manager = get_auth_manager()

    api_url = f"{config.api_url}/table/kb_knowledge/{article_id}"

    # Build query parameters
    query_params = {
        "sysparm_display_value": "true",
    }

    # Make request
    try:
        response = requests.get(
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

        # Extract values safely
        article_id = result.get("sys_id", "")
        title = result.get("short_description", "")
        text = result.get("text", "")
        
        # Extract nested values safely
        knowledge_base = ""
        if isinstance(result.get("kb_knowledge_base"), dict):
            knowledge_base = result["kb_knowledge_base"].get("display_value", "")
        
        category = ""
        if isinstance(result.get("kb_category"), dict):
            category = result["kb_category"].get("display_value", "")
        
        workflow_state = ""
        if isinstance(result.get("workflow_state"), dict):
            workflow_state = result["workflow_state"].get("display_value", "")
        
        author = ""
        if isinstance(result.get("author"), dict):
            author = result["author"].get("display_value", "")
        
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
        return f"Failed to get article: {str(e)}"


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

    api_url = f"{config.api_url}/table/kb_category"

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
        response = requests.get(
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
                    
                # Safely extract values
                category_id = category_item.get("sys_id", "")
                title = category_item.get("label", "")
                description = category_item.get("description", "")
                
                # Extract knowledge base
                kb_val = ""
                kb_field = category_item.get("kb_knowledge_base")
                if isinstance(kb_field, dict):
                    kb_val = kb_field.get("display_value", "")
                elif isinstance(kb_field, str):
                    kb_val = kb_field
                
                # Extract parent category
                parent_val = ""
                parent_field = category_item.get("parent")
                if isinstance(parent_field, dict):
                    parent_val = parent_field.get("display_value", "")
                elif isinstance(parent_field, str):
                    parent_val = parent_field
                
                # Convert active to boolean
                is_active = False
                active_field = category_item.get("active")
                if isinstance(active_field, str):
                    is_active = active_field.lower() == "true"
                elif isinstance(active_field, bool):
                    is_active = active_field
                
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
        return f"Failed to list categories: {str(e)}"
