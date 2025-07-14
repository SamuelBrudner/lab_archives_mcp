"""
LabArchives MCP Server Data Models

This module defines the canonical Pydantic data models, type definitions, and transformation 
utilities for representing MCP resources, resource content, and protocol responses in the 
LabArchives MCP Server. This module provides the schema layer for all MCP protocol operations,
including resource listing, content retrieval, and JSON-LD semantic enrichment.

The models implement the Model Context Protocol (MCP) specification for standardized AI-to-data
integration, enabling seamless connection between Claude Desktop and LabArchives electronic
lab notebook data. All models are designed for robust serialization, auditability, and 
seamless integration with the protocol, resource, and handler layers.

Key Components:
- MCPResource: Basic resource representation for listing operations
- MCPResourceContent: Detailed content representation for reading operations  
- MCPResourceListResponse: Response model for resources/list MCP requests
- MCPResourceReadResponse: Response model for resources/read MCP requests
- MCP_JSONLD_CONTEXT: Standard JSON-LD context for semantic enrichment
- labarchives_to_mcp_resource: Transformation utility for API model conversion

Features:
- Strict type validation and serialization through Pydantic v2
- MCP protocol compliance with JSON-RPC 2.0 compatibility
- Hierarchical resource navigation with URI scheme support
- Metadata preservation from LabArchives API responses
- Optional JSON-LD context for semantic enrichment
- Comprehensive audit trail support through structured logging
- Enterprise-grade error handling and validation

All models follow the stateless design pattern and support concurrent request processing
while maintaining data integrity and security through validated transformations.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field  # pydantic>=2.11.7

# Import LabArchives API models for transformation
from src.cli.api.models import NotebookMetadata, PageMetadata, EntryContent


# Standard MCP JSON-LD context for semantic enrichment
MCP_JSONLD_CONTEXT = {
    "@context": {
        "@vocab": "https://schema.org/",
        "labarchives": "https://labarchives.com/schema/",
        "Notebook": "labarchives:Notebook",
        "Page": "labarchives:Page", 
        "Entry": "labarchives:Entry",
        "created": {
            "@id": "dateCreated",
            "@type": "DateTime"
        },
        "modified": {
            "@id": "dateModified", 
            "@type": "DateTime"
        },
        "author": {
            "@id": "creator",
            "@type": "Person"
        },
        "content": {
            "@id": "text",
            "@type": "Text"
        }
    }
}


class MCPResource(BaseModel):
    """
    Represents an MCP-compliant resource for listing and navigation operations.
    
    This model provides the foundational structure for all MCP resources exposed by the
    LabArchives MCP Server. It implements the MCP resource specification with support
    for hierarchical navigation, metadata preservation, and protocol compliance.
    
    Used primarily in resources/list responses to provide clients with discoverable
    resource information including URIs, names, descriptions, and optional metadata.
    The model supports both individual resources and hierarchical collections.
    
    Attributes:
        uri: Unique resource identifier following the labarchives:// URI scheme
        name: Human-readable resource display name for client presentation
        description: Optional detailed description of the resource content
        mimeType: Optional MIME type hint for resource content format
        metadata: Optional dictionary containing additional resource metadata
        
    Examples:
        Notebook resource:
        {
            "uri": "labarchives://notebook/nb_123456",
            "name": "Protein Analysis Lab Notebook",
            "description": "Research notebook for protein structure analysis experiments",
            "mimeType": "application/json",
            "metadata": {
                "owner": "researcher@university.edu",
                "created": "2024-01-15T10:30:00Z",
                "page_count": 24
            }
        }
        
        Page resource:
        {
            "uri": "labarchives://notebook/nb_123456/page/page_789012",
            "name": "Experiment 1: Protein Purification Protocol",
            "description": "Detailed protocol for protein purification procedure",
            "mimeType": "application/json",
            "metadata": {
                "author": "researcher@university.edu",
                "created": "2024-01-16T09:15:00Z",
                "entry_count": 8
            }
        }
    """
    
    uri: str = Field(
        description="Unique resource identifier following the labarchives:// URI scheme",
        example="labarchives://notebook/nb_123456",
        min_length=1,
        max_length=500
    )
    
    name: str = Field(
        description="Human-readable resource display name for client presentation",
        example="Protein Analysis Lab Notebook",
        min_length=1,
        max_length=500
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Optional detailed description of the resource content",
        example="Research notebook for protein structure analysis experiments",
        max_length=2000
    )
    
    mimeType: Optional[str] = Field(
        default=None,
        description="Optional MIME type hint for resource content format",
        example="application/json",
        max_length=100
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional dictionary containing additional resource metadata",
        example={
            "owner": "researcher@university.edu",
            "created": "2024-01-15T10:30:00Z",
            "page_count": 24
        }
    )

    def dict(self, **kwargs) -> Dict[str, Any]:
        """
        Serializes the MCPResource to a dictionary for JSON output.
        
        Converts the MCPResource instance to a dictionary representation suitable
        for JSON serialization and MCP protocol transmission. Excludes None values
        to maintain clean protocol messages.
        
        Args:
            **kwargs: Additional arguments passed to Pydantic's dict() method
            
        Returns:
            Dict[str, Any]: Dictionary representation of the MCPResource with
                          None values excluded for clean protocol messages
                          
        Examples:
            >>> resource = MCPResource(
            ...     uri="labarchives://notebook/nb_123456",
            ...     name="Test Notebook"
            ... )
            >>> resource.dict()
            {
                "uri": "labarchives://notebook/nb_123456",
                "name": "Test Notebook"
            }
        """
        return super().dict(exclude_none=True, **kwargs)

    class Config:
        """Pydantic model configuration for MCPResource."""
        json_schema_extra = {
            "example": {
                "uri": "labarchives://notebook/nb_123456",
                "name": "Protein Analysis Lab Notebook",
                "description": "Research notebook for protein structure analysis experiments",
                "mimeType": "application/json",
                "metadata": {
                    "owner": "researcher@university.edu",
                    "created": "2024-01-15T10:30:00Z",
                    "page_count": 24
                }
            }
        }


class MCPResourceContent(BaseModel):
    """
    Represents the content and metadata for a specific MCP resource.
    
    This model encapsulates the detailed content of LabArchives resources including
    notebooks, pages, and entries, with support for optional JSON-LD semantic context.
    Used in resources/read responses to provide comprehensive resource information
    optimized for AI consumption and processing.
    
    The model supports structured content representation with preserved metadata
    and optional semantic enrichment through JSON-LD context. This enables AI
    applications to understand both the raw content and its semantic meaning within
    the research context.
    
    Attributes:
        content: Structured dictionary containing the resource content and data
        context: Optional JSON-LD context for semantic enrichment of content
        metadata: Dictionary containing comprehensive resource metadata
        
    Examples:
        Notebook content:
        {
            "content": {
                "id": "nb_123456",
                "name": "Protein Analysis Lab Notebook",
                "description": "Research notebook for protein structure analysis",
                "owner": "researcher@university.edu",
                "pages": [
                    {
                        "id": "page_789012",
                        "title": "Experiment 1: Protocol",
                        "entry_count": 8
                    }
                ]
            },
            "context": {
                "@context": {
                    "@vocab": "https://schema.org/",
                    "labarchives": "https://labarchives.com/schema/"
                }
            },
            "metadata": {
                "resource_type": "notebook",
                "created": "2024-01-15T10:30:00Z",
                "last_modified": "2024-11-20T14:22:35Z",
                "total_pages": 24
            }
        }
        
        Entry content:
        {
            "content": {
                "id": "entry_345678",
                "title": "Experimental Procedure",
                "entry_type": "text",
                "content": "1. Prepare protein sample in buffer solution...",
                "author": "researcher@university.edu"
            },
            "metadata": {
                "resource_type": "entry",
                "page_id": "page_789012",
                "created": "2024-01-16T10:30:00Z",
                "version": 3
            }
        }
    """
    
    content: Dict[str, Any] = Field(
        description="Structured dictionary containing the resource content and data",
        example={
            "id": "nb_123456",
            "name": "Protein Analysis Lab Notebook",
            "description": "Research notebook for protein structure analysis",
            "owner": "researcher@university.edu"
        }
    )
    
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional JSON-LD context for semantic enrichment of content",
        example=MCP_JSONLD_CONTEXT
    )
    
    metadata: Dict[str, Any] = Field(
        description="Dictionary containing comprehensive resource metadata",
        example={
            "resource_type": "notebook",
            "created": "2024-01-15T10:30:00Z",
            "last_modified": "2024-11-20T14:22:35Z",
            "total_pages": 24
        }
    )

    def dict(self, **kwargs) -> Dict[str, Any]:
        """
        Serializes the MCPResourceContent to a dictionary for JSON output.
        
        Converts the MCPResourceContent instance to a dictionary representation
        suitable for JSON serialization and MCP protocol transmission. Excludes
        None values to maintain clean protocol messages while preserving all
        essential content and metadata.
        
        Args:
            **kwargs: Additional arguments passed to Pydantic's dict() method
            
        Returns:
            Dict[str, Any]: Dictionary representation of the MCPResourceContent
                          with None values excluded for clean protocol messages
                          
        Examples:
            >>> content = MCPResourceContent(
            ...     content={"id": "nb_123", "name": "Test"},
            ...     metadata={"type": "notebook"}
            ... )
            >>> content.dict()
            {
                "content": {"id": "nb_123", "name": "Test"},
                "metadata": {"type": "notebook"}
            }
        """
        return super().dict(exclude_none=True, **kwargs)

    class Config:
        """Pydantic model configuration for MCPResourceContent."""
        json_schema_extra = {
            "example": {
                "content": {
                    "id": "nb_123456",
                    "name": "Protein Analysis Lab Notebook",
                    "description": "Research notebook for protein structure analysis",
                    "owner": "researcher@university.edu"
                },
                "context": MCP_JSONLD_CONTEXT,
                "metadata": {
                    "resource_type": "notebook",
                    "created": "2024-01-15T10:30:00Z",
                    "last_modified": "2024-11-20T14:22:35Z",
                    "total_pages": 24
                }
            }
        }


class MCPResourceListResponse(BaseModel):
    """
    Response model for MCP resources/list requests.
    
    This model represents the standardized response format for MCP resources/list
    operations, containing a list of discoverable resources and optional metadata.
    Implements the MCP protocol specification for resource listing with support
    for hierarchical navigation and comprehensive resource discovery.
    
    Used by the MCP server to respond to client requests for available resources,
    enabling AI applications to discover and navigate LabArchives notebook
    structures. The response includes all accessible resources within the
    configured scope limitations.
    
    Attributes:
        resources: List of MCPResource objects representing discoverable resources
        metadata: Optional dictionary containing response metadata and pagination info
        
    Examples:
        Basic resource list response:
        {
            "resources": [
                {
                    "uri": "labarchives://notebook/nb_123456",
                    "name": "Protein Analysis Lab Notebook",
                    "description": "Research notebook for protein structure analysis"
                },
                {
                    "uri": "labarchives://notebook/nb_789012",
                    "name": "Cell Culture Experiments",
                    "description": "Documentation of cell culture protocols"
                }
            ],
            "metadata": {
                "total_count": 2,
                "scope": "all_notebooks",
                "timestamp": "2024-11-20T10:30:00Z"
            }
        }
        
        Hierarchical page list response:
        {
            "resources": [
                {
                    "uri": "labarchives://notebook/nb_123456/page/page_001",
                    "name": "Introduction and Overview",
                    "description": "Project introduction and methodology overview"
                },
                {
                    "uri": "labarchives://notebook/nb_123456/page/page_002",  
                    "name": "Experiment 1: Protein Purification",
                    "description": "Detailed protocol for protein purification procedure"
                }
            ],
            "metadata": {
                "total_count": 2,
                "parent_notebook": "nb_123456",
                "scope": "notebook_pages"
            }
        }
    """
    
    resources: List[MCPResource] = Field(
        description="List of MCPResource objects representing discoverable resources",
        example=[
            {
                "uri": "labarchives://notebook/nb_123456",
                "name": "Protein Analysis Lab Notebook",
                "description": "Research notebook for protein structure analysis"
            },
            {
                "uri": "labarchives://notebook/nb_789012",
                "name": "Cell Culture Experiments",
                "description": "Documentation of cell culture protocols"
            }
        ]
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional dictionary containing response metadata and pagination info",
        example={
            "total_count": 2,
            "scope": "all_notebooks",
            "timestamp": "2024-11-20T10:30:00Z"
        }
    )

    def dict(self, **kwargs) -> Dict[str, Any]:
        """
        Serializes the MCPResourceListResponse to a dictionary for JSON output.
        
        Converts the MCPResourceListResponse instance to a dictionary representation
        suitable for JSON serialization and MCP protocol transmission. Ensures all
        nested MCPResource objects are properly serialized while excluding None
        values for clean protocol messages.
        
        Args:
            **kwargs: Additional arguments passed to Pydantic's dict() method
            
        Returns:
            Dict[str, Any]: Dictionary representation of the MCPResourceListResponse
                          with proper nested serialization and None exclusion
                          
        Examples:
            >>> response = MCPResourceListResponse(
            ...     resources=[
            ...         MCPResource(uri="labarchives://notebook/nb_123", name="Test")
            ...     ]
            ... )
            >>> response.dict()
            {
                "resources": [
                    {"uri": "labarchives://notebook/nb_123", "name": "Test"}
                ]
            }
        """
        return super().dict(exclude_none=True, **kwargs)

    class Config:
        """Pydantic model configuration for MCPResourceListResponse."""
        json_schema_extra = {
            "example": {
                "resources": [
                    {
                        "uri": "labarchives://notebook/nb_123456",
                        "name": "Protein Analysis Lab Notebook",
                        "description": "Research notebook for protein structure analysis"
                    },
                    {
                        "uri": "labarchives://notebook/nb_789012",
                        "name": "Cell Culture Experiments",
                        "description": "Documentation of cell culture protocols"
                    }
                ],
                "metadata": {
                    "total_count": 2,
                    "scope": "all_notebooks",
                    "timestamp": "2024-11-20T10:30:00Z"
                }
            }
        }


class MCPResourceReadResponse(BaseModel):
    """
    Response model for MCP resources/read requests.
    
    This model represents the standardized response format for MCP resources/read
    operations, containing detailed resource content and metadata. Implements the
    MCP protocol specification for resource reading with support for comprehensive
    content delivery and optional semantic enrichment.
    
    Used by the MCP server to respond to client requests for specific resource
    content, enabling AI applications to access detailed LabArchives notebook
    content including pages, entries, and associated metadata. The response
    provides structured content optimized for AI consumption and processing.
    
    Attributes:
        resource: MCPResourceContent object containing detailed resource content
        metadata: Optional dictionary containing response metadata and processing info
        
    Examples:
        Notebook read response:
        {
            "resource": {
                "content": {
                    "id": "nb_123456",
                    "name": "Protein Analysis Lab Notebook",
                    "description": "Research notebook for protein structure analysis",
                    "owner": "researcher@university.edu",
                    "pages": [
                        {
                            "id": "page_789012",
                            "title": "Experiment 1: Protocol",
                            "entry_count": 8
                        }
                    ]
                },
                "context": {
                    "@context": {
                        "@vocab": "https://schema.org/",
                        "labarchives": "https://labarchives.com/schema/"
                    }
                },
                "metadata": {
                    "resource_type": "notebook", 
                    "created": "2024-01-15T10:30:00Z",
                    "total_pages": 24
                }
            },
            "metadata": {
                "request_uri": "labarchives://notebook/nb_123456",
                "processing_time": "1.234s",
                "timestamp": "2024-11-20T10:30:00Z"
            }
        }
        
        Entry read response:
        {
            "resource": {
                "content": {
                    "id": "entry_345678",
                    "title": "Experimental Procedure",
                    "entry_type": "text",
                    "content": "1. Prepare protein sample in buffer solution...",
                    "author": "researcher@university.edu"
                },
                "metadata": {
                    "resource_type": "entry",
                    "page_id": "page_789012",
                    "version": 3
                }
            },
            "metadata": {
                "request_uri": "labarchives://entry/entry_345678",
                "processing_time": "0.567s"
            }
        }
    """
    
    resource: MCPResourceContent = Field(
        description="MCPResourceContent object containing detailed resource content",
        example={
            "content": {
                "id": "nb_123456",
                "name": "Protein Analysis Lab Notebook",
                "description": "Research notebook for protein structure analysis"
            },
            "metadata": {
                "resource_type": "notebook",
                "created": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional dictionary containing response metadata and processing info",
        example={
            "request_uri": "labarchives://notebook/nb_123456",
            "processing_time": "1.234s",
            "timestamp": "2024-11-20T10:30:00Z"
        }
    )

    def dict(self, **kwargs) -> Dict[str, Any]:
        """
        Serializes the MCPResourceReadResponse to a dictionary for JSON output.
        
        Converts the MCPResourceReadResponse instance to a dictionary representation
        suitable for JSON serialization and MCP protocol transmission. Ensures the
        nested MCPResourceContent object is properly serialized while excluding
        None values for clean protocol messages.
        
        Args:
            **kwargs: Additional arguments passed to Pydantic's dict() method
            
        Returns:
            Dict[str, Any]: Dictionary representation of the MCPResourceReadResponse
                          with proper nested serialization and None exclusion
                          
        Examples:
            >>> content = MCPResourceContent(
            ...     content={"id": "nb_123", "name": "Test"},
            ...     metadata={"type": "notebook"}
            ... )
            >>> response = MCPResourceReadResponse(resource=content)
            >>> response.dict()
            {
                "resource": {
                    "content": {"id": "nb_123", "name": "Test"},
                    "metadata": {"type": "notebook"}
                }
            }
        """
        return super().dict(exclude_none=True, **kwargs)

    class Config:
        """Pydantic model configuration for MCPResourceReadResponse."""
        json_schema_extra = {
            "example": {
                "resource": {
                    "content": {
                        "id": "nb_123456",
                        "name": "Protein Analysis Lab Notebook",
                        "description": "Research notebook for protein structure analysis"
                    },
                    "metadata": {
                        "resource_type": "notebook",
                        "created": "2024-01-15T10:30:00Z"
                    }
                },
                "metadata": {
                    "request_uri": "labarchives://notebook/nb_123456",
                    "processing_time": "1.234s",
                    "timestamp": "2024-11-20T10:30:00Z"
                }
            }
        }


def labarchives_to_mcp_resource(
    labarchives_obj: Union[NotebookMetadata, PageMetadata, EntryContent],
    parent_uri: Optional[str] = None
) -> Union[MCPResource, MCPResourceContent]:
    """
    Converts LabArchives API models to MCP resource or content models.
    
    This function serves as the primary transformation utility for converting
    LabArchives API response models into MCP-compliant resource representations.
    It handles the mapping of LabArchives data structures to MCP protocol
    requirements while preserving hierarchical context and metadata.
    
    The function supports conversion of three primary LabArchives entities:
    - NotebookMetadata: Converted to MCPResource for listing operations
    - PageMetadata: Converted to MCPResource for hierarchical navigation
    - EntryContent: Converted to MCPResourceContent for detailed content delivery
    
    All conversions preserve essential metadata including timestamps, authorship,
    and content relationships while generating appropriate MCP resource URIs
    following the labarchives:// scheme.
    
    Args:
        labarchives_obj: LabArchives API model instance to convert
                        (NotebookMetadata, PageMetadata, or EntryContent)
        parent_uri: Optional parent resource URI for hierarchical context
                   construction, used for building nested resource URIs
                   
    Returns:
        Union[MCPResource, MCPResourceContent]: MCP-compliant resource model
            - MCPResource for notebook and page metadata (listing operations)
            - MCPResourceContent for entry content (reading operations)
            
    Raises:
        ValueError: If labarchives_obj is not a supported LabArchives model type
        TypeError: If required attributes are missing from the input object
        
    Examples:
        Convert notebook metadata to MCP resource:
        >>> notebook = NotebookMetadata(
        ...     id="nb_123456",
        ...     name="Protein Analysis Lab Notebook",
        ...     description="Research notebook for protein structure analysis",
        ...     owner="researcher@university.edu",
        ...     created_date=datetime.now(),
        ...     last_modified=datetime.now(),
        ...     folder_count=5,
        ...     page_count=24
        ... )
        >>> mcp_resource = labarchives_to_mcp_resource(notebook)
        >>> print(mcp_resource.uri)
        "labarchives://notebook/nb_123456"
        
        Convert page metadata with parent context:
        >>> page = PageMetadata(
        ...     id="page_789012",
        ...     notebook_id="nb_123456",
        ...     title="Experiment 1: Protein Purification Protocol",
        ...     created_date=datetime.now(),
        ...     last_modified=datetime.now(),
        ...     entry_count=8,
        ...     author="researcher@university.edu"
        ... )
        >>> mcp_resource = labarchives_to_mcp_resource(
        ...     page, 
        ...     parent_uri="labarchives://notebook/nb_123456"
        ... )
        >>> print(mcp_resource.uri)
        "labarchives://notebook/nb_123456/page/page_789012"
        
        Convert entry content to MCP resource content:
        >>> entry = EntryContent(
        ...     id="entry_345678",
        ...     page_id="page_789012",
        ...     entry_type="text",
        ...     title="Experimental Procedure",
        ...     content="1. Prepare protein sample in buffer solution...",
        ...     created_date=datetime.now(),
        ...     last_modified=datetime.now(),
        ...     author="researcher@university.edu",
        ...     version=3
        ... )
        >>> mcp_content = labarchives_to_mcp_resource(entry)
        >>> print(mcp_content.content["id"])
        "entry_345678"
    """
    # Validate input parameter
    if not isinstance(labarchives_obj, (NotebookMetadata, PageMetadata, EntryContent)):
        raise ValueError(
            f"Unsupported LabArchives object type: {type(labarchives_obj)}. "
            f"Expected NotebookMetadata, PageMetadata, or EntryContent."
        )
    
    # Handle NotebookMetadata conversion to MCPResource
    if isinstance(labarchives_obj, NotebookMetadata):
        # Generate notebook URI following labarchives:// scheme
        uri = f"labarchives://notebook/{labarchives_obj.id}"
        
        # Create comprehensive metadata dictionary
        metadata = {
            "resource_type": "notebook",
            "id": labarchives_obj.id,
            "owner": labarchives_obj.owner,
            "created": labarchives_obj.created_date.isoformat(),
            "modified": labarchives_obj.last_modified.isoformat(),
            "folder_count": labarchives_obj.folder_count,
            "page_count": labarchives_obj.page_count
        }
        
        # Return MCPResource for notebook listing
        return MCPResource(
            uri=uri,
            name=labarchives_obj.name,
            description=labarchives_obj.description,
            mimeType="application/json",
            metadata=metadata
        )
    
    # Handle PageMetadata conversion to MCPResource
    elif isinstance(labarchives_obj, PageMetadata):
        # Generate hierarchical page URI based on parent context
        if parent_uri:
            # Use parent URI as base for hierarchical construction
            uri = f"{parent_uri}/page/{labarchives_obj.id}"
        else:
            # Construct full hierarchical URI from notebook relationship
            uri = f"labarchives://notebook/{labarchives_obj.notebook_id}/page/{labarchives_obj.id}"
        
        # Create comprehensive metadata dictionary
        metadata = {
            "resource_type": "page",
            "id": labarchives_obj.id,
            "notebook_id": labarchives_obj.notebook_id,
            "folder_path": labarchives_obj.folder_path,
            "author": labarchives_obj.author,
            "created": labarchives_obj.created_date.isoformat(),
            "modified": labarchives_obj.last_modified.isoformat(),
            "entry_count": labarchives_obj.entry_count
        }
        
        # Return MCPResource for page listing
        return MCPResource(
            uri=uri,
            name=labarchives_obj.title,
            description=f"Page containing {labarchives_obj.entry_count} entries",
            mimeType="application/json",
            metadata=metadata
        )
    
    # Handle EntryContent conversion to MCPResourceContent
    elif isinstance(labarchives_obj, EntryContent):
        # Generate entry URI for content reading
        uri = f"labarchives://entry/{labarchives_obj.id}"
        
        # Create structured content dictionary for AI consumption
        content = {
            "id": labarchives_obj.id,
            "page_id": labarchives_obj.page_id,
            "entry_type": labarchives_obj.entry_type,
            "title": labarchives_obj.title,
            "content": labarchives_obj.content,
            "author": labarchives_obj.author,
            "created": labarchives_obj.created_date.isoformat(),
            "modified": labarchives_obj.last_modified.isoformat(),
            "version": labarchives_obj.version
        }
        
        # Create comprehensive metadata dictionary
        metadata = {
            "resource_type": "entry",
            "uri": uri,
            "page_id": labarchives_obj.page_id,
            "entry_type": labarchives_obj.entry_type,
            "version": labarchives_obj.version,
            "created": labarchives_obj.created_date.isoformat(),
            "modified": labarchives_obj.last_modified.isoformat(),
            "author": labarchives_obj.author,
            "additional_metadata": labarchives_obj.metadata
        }
        
        # Return MCPResourceContent with optional JSON-LD context
        return MCPResourceContent(
            content=content,
            context=MCP_JSONLD_CONTEXT,
            metadata=metadata
        )
    
    # This should never be reached due to initial validation
    raise ValueError(f"Unexpected object type: {type(labarchives_obj)}")


# Export all models and utilities for external use
__all__ = [
    "MCPResource",
    "MCPResourceContent", 
    "MCPResourceListResponse",
    "MCPResourceReadResponse",
    "labarchives_to_mcp_resource",
    "MCP_JSONLD_CONTEXT"
]