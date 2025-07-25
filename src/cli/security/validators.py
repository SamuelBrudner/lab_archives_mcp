"""
LabArchives MCP Server - Centralized Security Validation Utilities

This module implements fail-secure scope validation functions that replace deferred validation
with immediate, synchronous access control enforcement. It provides centralized validation logic
for all resource access requests, ensuring that unauthorized data access is prevented through
comprehensive scope boundary enforcement.

Key Security Principles:
- Fail-secure validation: Any uncertainty or ambiguity results in access denial
- Immediate validation: All scope checks are performed synchronously before data access
- Comprehensive logging: All validation events are logged for audit and compliance
- Specific error types: Clear, descriptive errors replace generic "ScopeViolation" messages
- Defense-in-depth: Multi-layer validation chain with URI parsing, scope checking, and parent relationship validation

This module addresses critical security vulnerabilities identified in the security audit:
- Prevents unauthorized cross-notebook data access through entry-to-notebook validation
- Blocks information leakage when only folder scope is configured
- Ensures root-level pages are accessible when folder scope is empty or "/"
- Provides detailed audit trails for all access control decisions

All validation functions are designed to be invoked synchronously from ResourceManager.read_resource
before any data retrieval operations, ensuring that security controls are enforced at the earliest
possible point in the request processing pipeline.

Exports:
- validate_resource_scope(): Main validation function for general resource access
- validate_entry_notebook_ownership(): Prevents cross-notebook entry access
- validate_folder_scope_access(): Enforces folder-based access boundaries
- is_resource_in_scope(): Replacement for deferred validation function
"""

from typing import Optional, Dict, Any, Tuple

# Internal imports for scope validation and error handling
from src.cli.constants import SUPPORTED_SCOPE_TYPES
from src.cli.exceptions import (
    NotebookScopeViolationError,
    EntryOutsideNotebookScopeError,
    FolderScopeViolationError,
    LabArchivesMCPException
)
from src.cli.models import ScopeConfig
from src.cli.data_models import FolderPath
from src.cli.logging_setup import get_logger

# External imports for type annotations
from typing import Optional


def validate_resource_scope(
    resource_info: Dict[str, Any], 
    scope_config: ScopeConfig,
    additional_context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Main validation function for comprehensive resource scope enforcement with fail-secure behavior.
    
    This function implements the primary scope validation logic that replaces deferred validation
    throughout the system. It performs immediate, synchronous validation against configured scope
    boundaries and denies access by default when validation is uncertain or fails.
    
    The function implements a multi-level validation chain:
    1. URI parsing and resource type identification
    2. Scope configuration validation against resource properties
    3. Parent relationship validation for hierarchical resources
    4. Fail-secure decision making with comprehensive audit logging
    
    Args:
        resource_info (Dict[str, Any]): Parsed resource information containing type, IDs, and metadata.
                                       Expected keys: 'type', 'notebook_id', 'page_id', 'entry_id'
        scope_config (ScopeConfig): Active scope configuration with notebook/folder restrictions.
                                   Contains notebook_id, notebook_name, or folder_path restrictions
        additional_context (Optional[Dict[str, Any]]): Additional validation context such as
                                                      notebook metadata, page folder information,
                                                      or parent resource relationships
    
    Returns:
        bool: True if resource access is allowed within scope boundaries.
              False if access should be denied due to scope violations.
              Always returns False for uncertain or ambiguous cases (fail-secure)
    
    Raises:
        NotebookScopeViolationError: When resource falls outside configured notebook scope
        EntryOutsideNotebookScopeError: When entry belongs to notebook outside scope
        FolderScopeViolationError: When folder scope restrictions prevent access
        LabArchivesMCPException: For validation errors or malformed resource information
    
    Examples:
        >>> scope = ScopeConfig(notebook_id="123")
        >>> resource = {"type": "page", "notebook_id": "123", "page_id": "456"}
        >>> validate_resource_scope(resource, scope)
        True
        
        >>> resource = {"type": "page", "notebook_id": "789", "page_id": "456"}
        >>> validate_resource_scope(resource, scope)
        NotebookScopeViolationError: Page belongs to notebook 789 outside scope [123]
    """
    logger = get_logger()
    
    # Log validation attempt for audit trail
    logger.debug(
        f"Validating resource scope: {resource_info.get('type', 'unknown')} "
        f"against scope configuration",
        extra={
            "resource_type": resource_info.get('type'),
            "scope_type": _get_active_scope_type(scope_config),
            "validation_event": "scope_validation_start"
        }
    )
    
    try:
        # Step 1: Validate input parameters (fail-secure on invalid input)
        if not isinstance(resource_info, dict) or 'type' not in resource_info:
            logger.error(
                "Invalid resource_info provided to validation function",
                extra={
                    "resource_info": str(resource_info)[:100],  # Truncate for log safety
                    "validation_event": "invalid_input"
                }
            )
            raise LabArchivesMCPException(
                message="Invalid resource information for scope validation",
                code=400,
                context={"resource_info": resource_info}
            )
        
        if not isinstance(scope_config, ScopeConfig):
            logger.error(
                "Invalid scope_config provided to validation function",
                extra={
                    "scope_config_type": type(scope_config).__name__,
                    "validation_event": "invalid_scope_config"
                }
            )
            raise LabArchivesMCPException(
                message="Invalid scope configuration for validation",
                code=400,
                context={"scope_config_type": type(scope_config).__name__}
            )
        
        resource_type = resource_info['type']
        
        # Step 2: Handle no scope configuration (full access mode)
        if not _has_any_scope_configured(scope_config):
            logger.debug(
                f"No scope restrictions configured - allowing access to {resource_type}",
                extra={
                    "resource_type": resource_type,
                    "validation_event": "no_scope_full_access"
                }
            )
            return True
        
        # Step 3: Route to specific validation based on scope type
        active_scope_type = _get_active_scope_type(scope_config)
        
        if scope_config.notebook_id:
            return _validate_notebook_id_scope(resource_info, scope_config.notebook_id, logger)
        elif scope_config.notebook_name:
            return _validate_notebook_name_scope(resource_info, scope_config.notebook_name, additional_context, logger)
        elif scope_config.folder_path:
            return _validate_folder_path_scope(resource_info, scope_config.folder_path, additional_context, logger)
        else:
            # This should not happen due to scope_config validation, but fail-secure
            logger.error(
                "Scope configuration validation failed - no valid scope type found",
                extra={
                    "scope_config": str(scope_config),
                    "validation_event": "scope_config_validation_error"
                }
            )
            return False
    
    except (NotebookScopeViolationError, EntryOutsideNotebookScopeError, FolderScopeViolationError):
        # Re-raise specific scope violation errors for proper error handling
        raise
    except Exception as e:
        # Fail-secure: Any unexpected error results in access denial
        logger.error(
            f"Unexpected error during scope validation: {str(e)}",
            extra={
                "error_type": type(e).__name__,
                "resource_info": str(resource_info)[:100],
                "validation_event": "validation_error"
            }
        )
        return False


def validate_entry_notebook_ownership(
    entry_id: str,
    entry_notebook_id: str,
    scope_config: ScopeConfig,
    logger_context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Validates that an entry belongs to a notebook within the configured scope boundaries.
    
    This function prevents unauthorized cross-notebook data access by ensuring that requested
    entries can only be accessed if their parent notebook falls within the configured scope
    restrictions. This addresses the critical security vulnerability where entry access was
    previously deferred and not properly validated.
    
    The validation implements fail-secure behavior where any uncertainty about notebook
    ownership or scope boundaries results in access denial with detailed audit logging.
    
    Args:
        entry_id (str): Unique identifier of the entry being accessed
        entry_notebook_id (str): ID of the notebook containing the entry
        scope_config (ScopeConfig): Active scope configuration with notebook restrictions
        logger_context (Optional[Dict[str, Any]]): Additional context for audit logging
    
    Returns:
        bool: True if entry access is allowed within notebook scope boundaries.
              False if entry belongs to notebook outside configured scope.
    
    Raises:
        EntryOutsideNotebookScopeError: When entry belongs to notebook outside scope
        LabArchivesMCPException: For validation errors or invalid parameters
    
    Examples:
        >>> scope = ScopeConfig(notebook_id="123")
        >>> validate_entry_notebook_ownership("entry_456", "123", scope)
        True
        
        >>> validate_entry_notebook_ownership("entry_456", "789", scope)
        EntryOutsideNotebookScopeError: Entry entry_456 belongs to notebook 789 outside scope [123]
    """
    logger = get_logger()
    
    # Build audit context
    audit_context = {
        "entry_id": entry_id,
        "entry_notebook_id": entry_notebook_id,
        "validation_event": "entry_notebook_ownership_check"
    }
    if logger_context:
        audit_context.update(logger_context)
    
    logger.debug(
        f"Validating entry {entry_id} notebook ownership against scope",
        extra=audit_context
    )
    
    try:
        # Validate input parameters
        if not entry_id or not isinstance(entry_id, str):
            raise LabArchivesMCPException(
                message="Invalid entry_id provided for notebook ownership validation",
                code=400,
                context={"entry_id": entry_id}
            )
        
        if not entry_notebook_id or not isinstance(entry_notebook_id, str):
            raise LabArchivesMCPException(
                message="Invalid entry_notebook_id provided for ownership validation",
                code=400,
                context={"entry_notebook_id": entry_notebook_id, "entry_id": entry_id}
            )
        
        # No scope restrictions means full access (but log for audit)
        if not _has_any_scope_configured(scope_config):
            logger.debug(
                f"No scope restrictions - allowing entry {entry_id} access",
                extra={**audit_context, "validation_result": "allowed_no_scope"}
            )
            return True
        
        # Validate against notebook ID scope
        if scope_config.notebook_id:
            if entry_notebook_id == scope_config.notebook_id:
                logger.debug(
                    f"Entry {entry_id} notebook ownership validated - within scope",
                    extra={**audit_context, "validation_result": "allowed_notebook_id_match"}
                )
                return True
            else:
                logger.warning(
                    f"Entry {entry_id} belongs to notebook {entry_notebook_id} outside scope [{scope_config.notebook_id}]",
                    extra={
                        **audit_context, 
                        "configured_notebook_id": scope_config.notebook_id,
                        "validation_result": "denied_notebook_id_mismatch"
                    }
                )
                raise EntryOutsideNotebookScopeError(
                    message=f"Entry {entry_id} belongs to notebook {entry_notebook_id} which is outside configured scope [{scope_config.notebook_id}]",
                    code=403,
                    context={
                        "entry_id": entry_id,
                        "entry_notebook_id": entry_notebook_id,
                        "configured_scope": scope_config.notebook_id,
                        "violation_type": "notebook_id_mismatch"
                    }
                )
        
        # For notebook name and folder path scopes, we need additional context
        # This function focuses on notebook ownership, so we allow these cases
        # and let the caller handle folder/name validation
        if scope_config.notebook_name or scope_config.folder_path:
            logger.debug(
                f"Entry {entry_id} notebook ownership check passed - notebook name/folder validation required separately",
                extra={
                    **audit_context, 
                    "validation_result": "allowed_requires_additional_validation",
                    "additional_validation_needed": True
                }
            )
            return True
        
        # Should not reach here, but fail-secure
        logger.error(
            f"Unexpected scope configuration state during entry validation",
            extra={**audit_context, "validation_result": "failed_unexpected_state"}
        )
        return False
    
    except EntryOutsideNotebookScopeError:
        # Re-raise specific errors
        raise
    except Exception as e:
        # Fail-secure on any unexpected error
        logger.error(
            f"Unexpected error during entry notebook ownership validation: {str(e)}",
            extra={
                **audit_context,
                "error_type": type(e).__name__,
                "validation_result": "failed_error"
            }
        )
        return False


def validate_folder_scope_access(
    resource_info: Dict[str, Any],
    folder_scope: str,
    resource_metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Validates resource access against folder scope restrictions with fail-secure behavior.
    
    This function enforces folder-based access control to prevent information leakage when
    only folder scope is configured. It implements the security requirement to deny direct
    notebook reads when the notebook contains no pages within the configured folder scope,
    preventing exposure of notebook metadata outside folder boundaries.
    
    Special handling for root-level pages: When folder_scope is empty string or "/", the
    function explicitly includes pages with null or empty folder_path to ensure complete
    page discovery for root-level content.
    
    Args:
        resource_info (Dict[str, Any]): Resource information with type and identifiers
        folder_scope (str): Configured folder path restriction (empty string means root)
        resource_metadata (Optional[Dict[str, Any]]): Additional metadata including folder
                                                     information and notebook page listings
    
    Returns:
        bool: True if resource access is allowed within folder scope boundaries.
              False if access violates folder restrictions or metadata would leak.
    
    Raises:
        FolderScopeViolationError: When folder scope restrictions prevent access
        LabArchivesMCPException: For validation errors or invalid parameters
    
    Examples:
        >>> resource = {"type": "page", "notebook_id": "123", "page_id": "456"}
        >>> metadata = {"page_folder_path": "/Research/Data"}
        >>> validate_folder_scope_access(resource, "/Research", metadata)
        True
        
        >>> # Root-level page access with empty folder scope
        >>> metadata = {"page_folder_path": ""}
        >>> validate_folder_scope_access(resource, "", metadata)
        True
    """
    logger = get_logger()
    
    resource_type = resource_info.get('type', 'unknown')
    
    # Build audit context
    audit_context = {
        "resource_type": resource_type,
        "folder_scope": folder_scope,
        "validation_event": "folder_scope_access_check"
    }
    
    logger.debug(
        f"Validating {resource_type} access against folder scope: '{folder_scope}'",
        extra=audit_context
    )
    
    try:
        # Validate input parameters
        if not isinstance(resource_info, dict) or 'type' not in resource_info:
            raise LabArchivesMCPException(
                message="Invalid resource_info for folder scope validation",
                code=400,
                context={"resource_info": resource_info}
            )
        
        if folder_scope is None:
            raise LabArchivesMCPException(
                message="folder_scope cannot be None for validation",
                code=400,
                context={"folder_scope": folder_scope}
            )
        
        # Parse and normalize folder scope path
        try:
            if folder_scope in ('', '/'):
                # Empty or root folder scope - include all resources including root-level pages
                scope_folder = FolderPath.from_raw('')  # Root folder path
                logger.debug(
                    f"Using root folder scope - all resources allowed including root-level pages",
                    extra={**audit_context, "normalized_scope": "root"}
                )
            else:
                scope_folder = FolderPath.from_raw(folder_scope)
                logger.debug(
                    f"Using folder scope: {scope_folder}",
                    extra={**audit_context, "normalized_scope": str(scope_folder)}
                )
        except Exception as e:
            logger.error(
                f"Failed to parse folder scope '{folder_scope}': {str(e)}",
                extra={**audit_context, "parse_error": str(e)}
            )
            raise FolderScopeViolationError(
                message=f"Invalid folder scope configuration: '{folder_scope}'",
                code=400,
                context={
                    "folder_scope": folder_scope,
                    "parse_error": str(e)
                }
            )
        
        # Handle different resource types
        if resource_type == 'notebook':
            return _validate_notebook_folder_access(
                resource_info, scope_folder, resource_metadata, audit_context, logger
            )
        elif resource_type == 'page':
            return _validate_page_folder_access(
                resource_info, scope_folder, resource_metadata, audit_context, logger
            )
        elif resource_type == 'entry':
            # Entries inherit folder validation from their parent page
            return _validate_entry_folder_access(
                resource_info, scope_folder, resource_metadata, audit_context, logger
            )
        else:
            logger.warning(
                f"Unknown resource type '{resource_type}' for folder validation - denying access",
                extra={**audit_context, "validation_result": "denied_unknown_type"}
            )
            return False
    
    except FolderScopeViolationError:
        # Re-raise specific errors
        raise
    except Exception as e:
        # Fail-secure on any unexpected error
        logger.error(
            f"Unexpected error during folder scope validation: {str(e)}",
            extra={
                **audit_context,
                "error_type": type(e).__name__,
                "validation_result": "failed_error"
            }
        )
        return False


def is_resource_in_scope(
    resource_info: Dict[str, Any],
    scope_config: ScopeConfig
) -> bool:
    """
    Replacement for deferred validation with immediate, fail-secure scope validation.
    
    This function replaces the previous deferred validation approach with immediate,
    synchronous validation that denies access by default when scope boundaries are
    unclear or violated. It serves as the primary entry point for all scope validation
    throughout the system.
    
    Unlike the previous implementation that deferred validation for entries and folder
    paths, this function performs complete validation immediately and returns definitive
    access control decisions with comprehensive audit logging.
    
    Args:
        resource_info (Dict[str, Any]): Parsed resource information from URI or request
        scope_config (ScopeConfig): Active scope configuration with access restrictions
    
    Returns:
        bool: True if resource is definitively within scope boundaries.
              False if resource is outside scope or validation is uncertain.
    
    Raises:
        NotebookScopeViolationError: For notebook access violations
        EntryOutsideNotebookScopeError: For cross-notebook entry access
        FolderScopeViolationError: For folder scope violations
        LabArchivesMCPException: For validation errors
    
    Examples:
        >>> resource = {"type": "notebook", "notebook_id": "123"}
        >>> scope = ScopeConfig(notebook_id="123")
        >>> is_resource_in_scope(resource, scope)
        True
        
        >>> scope = ScopeConfig(notebook_id="456")
        >>> is_resource_in_scope(resource, scope)
        NotebookScopeViolationError: Notebook 123 access denied: outside configured scope [456]
    """
    logger = get_logger()
    
    # Log all scope validation attempts for audit compliance
    logger.debug(
        f"Performing immediate scope validation for {resource_info.get('type', 'unknown')} resource",
        extra={
            "resource_type": resource_info.get('type'),
            "resource_id": _extract_primary_resource_id(resource_info),
            "validation_event": "immediate_scope_validation",
            "validation_approach": "fail_secure"
        }
    )
    
    try:
        # Use the main validation function for comprehensive checking
        return validate_resource_scope(resource_info, scope_config)
    
    except (NotebookScopeViolationError, EntryOutsideNotebookScopeError, FolderScopeViolationError):
        # Log specific scope violations for audit
        logger.warning(
            f"Scope violation detected for {resource_info.get('type', 'unknown')} resource",
            extra={
                "resource_type": resource_info.get('type'),
                "resource_id": _extract_primary_resource_id(resource_info),
                "validation_event": "scope_violation",
                "violation_type": type(e).__name__ if 'e' in locals() else "unknown"
            }
        )
        # Re-raise for proper error handling by caller
        raise
    
    except Exception as e:
        # Log unexpected errors and fail secure
        logger.error(
            f"Unexpected error in scope validation - failing secure: {str(e)}",
            extra={
                "resource_type": resource_info.get('type'),
                "resource_id": _extract_primary_resource_id(resource_info),
                "validation_event": "validation_error",
                "error_type": type(e).__name__
            }
        )
        # Fail secure - deny access on any unexpected error
        return False


# =============================================================================
# Private Helper Functions
# =============================================================================

def _has_any_scope_configured(scope_config: ScopeConfig) -> bool:
    """Check if any scope restrictions are configured."""
    return bool(scope_config.notebook_id or scope_config.notebook_name or scope_config.folder_path)


def _get_active_scope_type(scope_config: ScopeConfig) -> Optional[str]:
    """Get the active scope type from configuration."""
    if scope_config.notebook_id:
        return "notebook_id"
    elif scope_config.notebook_name:
        return "notebook_name"
    elif scope_config.folder_path:
        return "folder_path"
    return None


def _extract_primary_resource_id(resource_info: Dict[str, Any]) -> str:
    """Extract the primary identifier from resource info for logging."""
    resource_type = resource_info.get('type', '')
    if resource_type == 'notebook':
        return resource_info.get('notebook_id', 'unknown')
    elif resource_type == 'page':
        return resource_info.get('page_id', 'unknown')
    elif resource_type == 'entry':
        return resource_info.get('entry_id', 'unknown')
    return 'unknown'


def _validate_notebook_id_scope(
    resource_info: Dict[str, Any], 
    notebook_id: str, 
    logger
) -> bool:
    """Validate resource against notebook ID scope."""
    resource_type = resource_info['type']
    
    if resource_type == 'notebook':
        resource_notebook_id = resource_info.get('notebook_id')
        if resource_notebook_id == notebook_id:
            logger.debug(f"Notebook {resource_notebook_id} matches scope - access allowed")
            return True
        else:
            logger.warning(f"Notebook {resource_notebook_id} outside scope [{notebook_id}]")
            raise NotebookScopeViolationError(
                message=f"Notebook {resource_notebook_id} access denied: outside configured scope [{notebook_id}]",
                code=403,
                context={
                    "requested_notebook_id": resource_notebook_id,
                    "configured_notebook_scope": notebook_id,
                    "resource_type": resource_type
                }
            )
    
    elif resource_type in ['page', 'entry']:
        resource_notebook_id = resource_info.get('notebook_id')
        if resource_notebook_id == notebook_id:
            logger.debug(f"{resource_type.title()} belongs to notebook {resource_notebook_id} within scope")
            return True
        else:
            logger.warning(f"{resource_type.title()} belongs to notebook {resource_notebook_id} outside scope [{notebook_id}]")
            if resource_type == 'entry':
                raise EntryOutsideNotebookScopeError(
                    message=f"Entry {resource_info.get('entry_id')} belongs to notebook {resource_notebook_id} which is outside configured scope [{notebook_id}]",
                    code=403,
                    context={
                        "entry_id": resource_info.get('entry_id'),
                        "entry_notebook_id": resource_notebook_id,
                        "configured_scope": notebook_id
                    }
                )
            else:
                raise NotebookScopeViolationError(
                    message=f"Page {resource_info.get('page_id')} belongs to notebook {resource_notebook_id} which is outside configured scope [{notebook_id}]",
                    code=403,
                    context={
                        "page_id": resource_info.get('page_id'),
                        "page_notebook_id": resource_notebook_id,
                        "configured_scope": notebook_id
                    }
                )
    
    return False


def _validate_notebook_name_scope(
    resource_info: Dict[str, Any], 
    notebook_name: str, 
    additional_context: Optional[Dict[str, Any]], 
    logger
) -> bool:
    """Validate resource against notebook name scope."""
    # For notebook name validation, we need additional context to resolve names to IDs
    # This is a simplified implementation - in practice, this would require API calls
    # to resolve notebook names to IDs and validate access
    
    logger.debug(f"Notebook name scope validation requires additional API context")
    
    # If we have notebook name in additional context, validate it
    if additional_context and 'notebook_name' in additional_context:
        actual_notebook_name = additional_context['notebook_name']
        if actual_notebook_name == notebook_name:
            logger.debug(f"Notebook name '{actual_notebook_name}' matches scope - access allowed")
            return True
        else:
            logger.warning(f"Notebook name '{actual_notebook_name}' outside scope ['{notebook_name}']")
            raise NotebookScopeViolationError(
                message=f"Notebook '{actual_notebook_name}' access denied: outside configured scope ['{notebook_name}']",
                code=403,
                context={
                    "requested_notebook_name": actual_notebook_name,
                    "configured_notebook_name": notebook_name,
                    "resource_type": resource_info['type']
                }
            )
    
    # Without sufficient context, we must fail secure
    logger.warning("Insufficient context for notebook name validation - failing secure")
    return False


def _validate_folder_path_scope(
    resource_info: Dict[str, Any], 
    folder_path: str, 
    additional_context: Optional[Dict[str, Any]], 
    logger
) -> bool:
    """Validate resource against folder path scope."""
    return validate_folder_scope_access(resource_info, folder_path, additional_context)


def _validate_notebook_folder_access(
    resource_info: Dict[str, Any],
    scope_folder: FolderPath,
    resource_metadata: Optional[Dict[str, Any]],
    audit_context: Dict[str, Any],
    logger
) -> bool:
    """Validate notebook access against folder scope (prevents metadata leakage)."""
    notebook_id = resource_info.get('notebook_id')
    
    # For direct notebook access with folder scope, we must ensure the notebook
    # contains pages within the folder scope to prevent metadata leakage
    if not resource_metadata or 'notebook_folders' not in resource_metadata:
        logger.warning(
            f"Direct notebook {notebook_id} read denied: insufficient metadata for folder validation",
            extra={**audit_context, "validation_result": "denied_insufficient_metadata"}
        )
        raise FolderScopeViolationError(
            message=f"Direct notebook {notebook_id} read denied: cannot validate folder scope without page metadata",
            code=403,
            context={
                "notebook_id": notebook_id,
                "configured_folder_scope": str(scope_folder),
                "missing_metadata": "notebook_folders"
            }
        )
    
    notebook_folders = resource_metadata['notebook_folders']
    
    # Check if any pages exist within the folder scope
    has_pages_in_scope = False
    
    if scope_folder.is_root:
        # Root scope includes all folders, so check if notebook has any pages
        has_pages_in_scope = len(notebook_folders) > 0 or resource_metadata.get('has_root_pages', False)
    else:
        # Check if any folder in notebook is within scope
        for folder_path_str in notebook_folders:
            try:
                if folder_path_str in ('', None):
                    # Root-level pages don't match non-root scope
                    continue
                folder_path = FolderPath.from_raw(folder_path_str)
                if scope_folder.is_parent_of(folder_path) or scope_folder.components == folder_path.components:
                    has_pages_in_scope = True
                    break
            except Exception as e:
                logger.warning(f"Error parsing folder path '{folder_path_str}': {e}")
                continue
    
    if has_pages_in_scope:
        logger.debug(
            f"Notebook {notebook_id} contains pages in folder scope - access allowed",
            extra={**audit_context, "validation_result": "allowed_has_pages_in_scope"}
        )
        return True
    else:
        logger.warning(
            f"Direct notebook {notebook_id} read denied: no pages in configured folder scope '{scope_folder}'",
            extra={
                **audit_context,
                "notebook_folders": notebook_folders,
                "validation_result": "denied_no_pages_in_scope"
            }
        )
        raise FolderScopeViolationError(
            message=f"Direct notebook {notebook_id} read denied: no pages in configured folder scope '{scope_folder}'",
            code=403,
            context={
                "notebook_id": notebook_id,
                "configured_folder_scope": str(scope_folder),
                "notebook_folders": notebook_folders
            }
        )


def _validate_page_folder_access(
    resource_info: Dict[str, Any],
    scope_folder: FolderPath,
    resource_metadata: Optional[Dict[str, Any]],
    audit_context: Dict[str, Any],
    logger
) -> bool:
    """Validate page access against folder scope."""
    page_id = resource_info.get('page_id')
    
    # Get page folder path from metadata
    page_folder_path = resource_metadata.get('page_folder_path') if resource_metadata else None
    
    # Handle root-level pages (empty or None folder path)
    if page_folder_path in ('', None):
        if scope_folder.is_root:
            logger.debug(
                f"Root-level page {page_id} allowed by root folder scope",
                extra={**audit_context, "validation_result": "allowed_root_page_root_scope"}
            )
            return True
        else:
            logger.debug(
                f"Root-level page {page_id} denied by non-root folder scope '{scope_folder}'",
                extra={**audit_context, "validation_result": "denied_root_page_non_root_scope"}
            )
            return False
    
    # Parse and validate page folder path
    try:
        page_folder = FolderPath.from_raw(page_folder_path)
    except Exception as e:
        logger.warning(
            f"Invalid page folder path '{page_folder_path}' for page {page_id}: {e}",
            extra={**audit_context, "parse_error": str(e)}
        )
        return False
    
    # Check if page folder is within scope
    if scope_folder.is_root or scope_folder.is_parent_of(page_folder) or scope_folder.components == page_folder.components:
        logger.debug(
            f"Page {page_id} folder '{page_folder}' is within scope '{scope_folder}' - access allowed",
            extra={**audit_context, "validation_result": "allowed_folder_match"}
        )
        return True
    else:
        logger.debug(
            f"Page {page_id} folder '{page_folder}' is outside scope '{scope_folder}' - access denied",
            extra={**audit_context, "validation_result": "denied_folder_mismatch"}
        )
        return False


def _validate_entry_folder_access(
    resource_info: Dict[str, Any],
    scope_folder: FolderPath,
    resource_metadata: Optional[Dict[str, Any]],
    audit_context: Dict[str, Any],
    logger
) -> bool:
    """Validate entry access against folder scope (inherits from parent page)."""
    entry_id = resource_info.get('entry_id')
    
    # Entries inherit folder access from their parent page
    if not resource_metadata or 'parent_page_folder_path' not in resource_metadata:
        logger.warning(
            f"Entry {entry_id} validation requires parent page folder information",
            extra={**audit_context, "validation_result": "denied_missing_parent_info"}
        )
        return False
    
    parent_page_folder_path = resource_metadata['parent_page_folder_path']
    
    # Create a synthetic page resource for validation
    page_resource_info = {
        'type': 'page',
        'page_id': resource_metadata.get('parent_page_id', 'unknown'),
        'notebook_id': resource_info.get('notebook_id')
    }
    
    page_metadata = {
        'page_folder_path': parent_page_folder_path
    }
    
    # Use page validation logic
    page_allowed = _validate_page_folder_access(
        page_resource_info, scope_folder, page_metadata, audit_context, logger
    )
    
    if page_allowed:
        logger.debug(
            f"Entry {entry_id} allowed through parent page folder validation",
            extra={**audit_context, "validation_result": "allowed_parent_page_valid"}
        )
    else:
        logger.debug(
            f"Entry {entry_id} denied - parent page folder outside scope",
            extra={**audit_context, "validation_result": "denied_parent_page_invalid"}
        )
    
    return page_allowed