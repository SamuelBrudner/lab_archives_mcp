"""
LabArchives MCP Server - Protocol Request Handlers

This module defines the main MCP protocol request handler functions and classes for the LabArchives 
MCP Server. It acts as the bridge between the protocol dispatcher and the resource management layer,
implementing stateless, auditable, and robust handling of all MCP protocol requests.

This file provides the entrypoints for processing JSON-RPC messages, routing requests to resource
listing and reading logic, handling protocol handshake and capability negotiation, and converting
exceptions into protocol-compliant error responses. The handler ensures strict compliance with the
MCP specification, integrates with the audit logging system, and supports future extensibility for
additional MCP methods.

Key Features:
- MCP Protocol Implementation (F-001): Implements core MCP protocol request handling, including
  handshake, capability negotiation, and routing of JSON-RPC messages to appropriate resource
  management logic
- Resource Discovery and Listing (F-003): Handles MCP resources/list requests by delegating to
  the resource manager, returning hierarchical resource listings in MCP-compliant format
- Content Retrieval and Contextualization (F-004): Handles MCP resources/read requests by
  delegating to the resource manager, returning detailed resource content and metadata
- Error Handling and Graceful Degradation (F-001/F-002/F-003/F-004): Centralizes error handling
  for all MCP protocol operations, converting exceptions into structured, protocol-compliant
  error responses and logging all error events for audit and compliance
- Comprehensive Audit Logging (F-008): Ensures all protocol events, errors, and access operations
  are logged in structured, auditable format, supporting compliance and diagnostics

The handler follows the stateless design pattern, processing each request independently while
maintaining comprehensive audit trails and providing robust error handling for all scenarios.
"""

import json  # builtin - JSON serialization and deserialization
import logging  # builtin - Logging of protocol events, errors, and diagnostics
import sys  # builtin - System-specific parameters and functions
from typing import Optional, Dict, Any  # builtin - Type hinting for handler methods and message structures

# Import internal dependencies for resource management and data models
from src.cli.mcp.resources import MCPResourceManager
from src.cli.mcp.models import MCPResourceListResponse, MCPResourceReadResponse
from src.cli.mcp.errors import handle_mcp_error, MCP_ERROR_CODES, MCP_ERROR_MESSAGES, MCPProtocolError

# Import constants for MCP protocol configuration
from src.cli.constants import (
    DEFAULT_PROTOCOL_VERSION,
    MCP_SERVER_NAME,
    MCP_SERVER_VERSION
)

# Global logger name for handler operations
HANDLER_LOGGER_NAME = "mcp.handlers"


def parse_jsonrpc_message(raw_message: str) -> Dict[str, Any]:
    """
    Parses and validates a JSON-RPC 2.0 message from a raw JSON string.
    
    This function ensures that incoming messages conform to the JSON-RPC 2.0 specification
    and extracts the method, params, and id fields for MCP protocol processing. It performs
    comprehensive validation to ensure protocol compliance and provides detailed error
    information for debugging and audit purposes.
    
    The function validates:
    - Valid JSON format
    - Required 'jsonrpc' field with value '2.0'
    - Required 'method' field with string value
    - Optional 'params' field (object or array)
    - Optional 'id' field for request correlation
    
    Args:
        raw_message (str): Raw JSON string containing the JSON-RPC message
        
    Returns:
        Dict[str, Any]: Parsed and validated JSON-RPC message as a dictionary containing
                       'jsonrpc', 'method', 'params' (optional), and 'id' (optional)
                       
    Raises:
        MCPProtocolError: If the message is invalid, malformed, or doesn't conform to
                         JSON-RPC 2.0 specification
                         
    Examples:
        >>> parse_jsonrpc_message('{"jsonrpc": "2.0", "method": "resources/list", "id": 1}')
        {"jsonrpc": "2.0", "method": "resources/list", "id": 1}
        
        >>> parse_jsonrpc_message('{"jsonrpc": "2.0", "method": "resources/read", "params": {"uri": "labarchives://notebook/123"}, "id": 2}')
        {"jsonrpc": "2.0", "method": "resources/read", "params": {"uri": "labarchives://notebook/123"}, "id": 2}
    """
    logger = logging.getLogger(HANDLER_LOGGER_NAME)
    
    try:
        # Attempt to deserialize the raw message string
        message = json.loads(raw_message)
        
        # Log the incoming message for audit trail (excluding potentially sensitive params)
        logger.debug("Parsing JSON-RPC message", extra={
            "message_length": len(raw_message),
            "has_method": "method" in message if isinstance(message, dict) else False
        })
        
    except json.JSONDecodeError as e:
        # Handle invalid JSON format
        logger.error("Invalid JSON in message", extra={
            "error": str(e),
            "message_preview": raw_message[:100] + "..." if len(raw_message) > 100 else raw_message
        })
        raise MCPProtocolError(
            message="Invalid JSON format in request",
            code=MCP_ERROR_CODES['INVALID_REQUEST'],
            context={"parse_error": str(e), "message_preview": raw_message[:100]}
        )
    
    # Validate that the message is a dictionary
    if not isinstance(message, dict):
        logger.error("Message is not a JSON object", extra={
            "message_type": type(message).__name__,
            "message_value": str(message)
        })
        raise MCPProtocolError(
            message="JSON-RPC message must be an object",
            code=MCP_ERROR_CODES['INVALID_REQUEST'],
            context={"message_type": type(message).__name__}
        )
    
    # Validate required 'jsonrpc' field
    if message.get('jsonrpc') != '2.0':
        logger.error("Invalid JSON-RPC version", extra={
            "jsonrpc_value": message.get('jsonrpc'),
            "expected": "2.0"
        })
        raise MCPProtocolError(
            message="Invalid JSON-RPC version, expected '2.0'",
            code=MCP_ERROR_CODES['INVALID_REQUEST'],
            context={"jsonrpc_value": message.get('jsonrpc')}
        )
    
    # Validate required 'method' field
    if 'method' not in message:
        logger.error("Missing 'method' field in JSON-RPC message", extra={
            "message_keys": list(message.keys())
        })
        raise MCPProtocolError(
            message="Missing 'method' field in JSON-RPC request",
            code=MCP_ERROR_CODES['INVALID_REQUEST'],
            context={"message_keys": list(message.keys())}
        )
    
    # Validate that method is a string
    if not isinstance(message['method'], str):
        logger.error("Invalid 'method' field type", extra={
            "method_type": type(message['method']).__name__,
            "method_value": str(message['method'])
        })
        raise MCPProtocolError(
            message="'method' field must be a string",
            code=MCP_ERROR_CODES['INVALID_REQUEST'],
            context={"method_type": type(message['method']).__name__}
        )
    
    # Validate optional 'params' field if present
    if 'params' in message:
        if not isinstance(message['params'], (dict, list)):
            logger.error("Invalid 'params' field type", extra={
                "params_type": type(message['params']).__name__,
                "method": message['method']
            })
            raise MCPProtocolError(
                message="'params' field must be an object or array",
                code=MCP_ERROR_CODES['INVALID_REQUEST'],
                context={"params_type": type(message['params']).__name__}
            )
    
    # Log successful message parsing
    logger.info("JSON-RPC message parsed successfully", extra={
        "method": message['method'],
        "has_params": 'params' in message,
        "has_id": 'id' in message
    })
    
    return message


def build_jsonrpc_response(result: Any = None, error: Optional[Any] = None, id: Any = None) -> str:
    """
    Constructs a JSON-RPC 2.0 response message from the given result or error object.
    
    This function creates properly formatted JSON-RPC 2.0 response messages that comply
    with the specification requirements. It handles both successful results and error
    responses, ensuring proper correlation with the original request through the id field.
    
    The function follows JSON-RPC 2.0 requirements:
    - Always includes 'jsonrpc': '2.0'
    - Includes either 'result' or 'error' field (never both)
    - Includes 'id' field for request correlation
    - Properly serializes the response to JSON string
    
    Args:
        result (Any): The result object to include in a successful response
                     (mutually exclusive with error)
        error (Optional[Any]): The error object to include in an error response
                              (mutually exclusive with result)
        id (Any): The request ID for correlation with the original request
                 (can be string, number, or null)
                 
    Returns:
        str: Serialized JSON-RPC 2.0 response string ready for transmission
        
    Examples:
        >>> build_jsonrpc_response(result={"resources": []}, id=1)
        '{"jsonrpc": "2.0", "result": {"resources": []}, "id": 1}'
        
        >>> build_jsonrpc_response(error={"code": -32601, "message": "Method not found"}, id=1)
        '{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": 1}'
    """
    logger = logging.getLogger(HANDLER_LOGGER_NAME)
    
    # Create the base response object with required fields
    response = {
        "jsonrpc": "2.0",
        "id": id
    }
    
    # Add either result or error field (never both)
    if error is not None:
        response["error"] = error
        logger.debug("Building JSON-RPC error response", extra={
            "error_code": error.get('code') if isinstance(error, dict) else None,
            "request_id": id
        })
    else:
        response["result"] = result
        logger.debug("Building JSON-RPC success response", extra={
            "result_type": type(result).__name__,
            "request_id": id
        })
    
    try:
        # Serialize the response to JSON string
        response_str = json.dumps(response, separators=(',', ':'))
        
        logger.debug("JSON-RPC response built successfully", extra={
            "response_length": len(response_str),
            "is_error": error is not None,
            "request_id": id
        })
        
        return response_str
        
    except (TypeError, ValueError) as e:
        # Handle JSON serialization errors
        logger.error("Failed to serialize JSON-RPC response", extra={
            "error": str(e),
            "response_data": str(response),
            "request_id": id
        })
        
        # Create a fallback error response
        fallback_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": MCP_ERROR_CODES['INTERNAL_ERROR'],
                "message": "Failed to serialize response"
            },
            "id": id
        }
        
        return json.dumps(fallback_response, separators=(',', ':'))


def route_mcp_request(request: Dict[str, Any], resource_manager: MCPResourceManager) -> str:
    """
    Routes an MCP protocol request to the appropriate handler based on the method.
    
    This function serves as the central routing mechanism for all MCP protocol requests,
    dispatching them to the appropriate handler methods based on the 'method' field.
    It supports the core MCP methods required for LabArchives integration and provides
    comprehensive error handling for unsupported or invalid requests.
    
    Supported MCP methods:
    - 'initialize': Protocol handshake and capability negotiation
    - 'resources/list': Resource discovery and listing
    - 'resources/read': Resource content retrieval
    
    The function handles all aspects of request routing including parameter validation,
    handler invocation, response formatting, and error handling with proper audit logging.
    
    Args:
        request (Dict[str, Any]): Parsed JSON-RPC request object containing method,
                                 params, and id fields
        resource_manager (MCPResourceManager): Initialized resource manager instance
                                             for handling resource operations
                                             
    Returns:
        str: Serialized JSON-RPC response string containing either successful result
             or structured error response
             
    Examples:
        >>> route_mcp_request(
        ...     {"jsonrpc": "2.0", "method": "initialize", "id": 1},
        ...     resource_manager
        ... )
        '{"jsonrpc": "2.0", "result": {"capabilities": {...}}, "id": 1}'
    """
    logger = logging.getLogger(HANDLER_LOGGER_NAME)
    
    # Extract method and other components from request
    method = request.get('method')
    params = request.get('params', {})
    request_id = request.get('id')
    
    # Log the request routing for audit trail
    logger.info("Routing MCP request", extra={
        "method": method,
        "has_params": bool(params),
        "request_id": request_id
    })
    
    try:
        # Route to appropriate handler based on method
        if method == 'initialize':
            # Handle protocol handshake and capability negotiation
            result = MCPProtocolHandler.handle_initialize(request)
            return build_jsonrpc_response(result=result, id=request_id)
            
        elif method == 'resources/list':
            # Handle resource discovery and listing
            result = MCPProtocolHandler.handle_resources_list(request, resource_manager)
            return build_jsonrpc_response(result=result, id=request_id)
            
        elif method == 'resources/read':
            # Handle resource content retrieval
            result = MCPProtocolHandler.handle_resources_read(request, resource_manager)
            return build_jsonrpc_response(result=result, id=request_id)
            
        else:
            # Handle unsupported methods
            logger.warning("Unsupported MCP method", extra={
                "method": method,
                "request_id": request_id
            })
            
            raise MCPProtocolError(
                message=f"Method '{method}' not found",
                code=MCP_ERROR_CODES['METHOD_NOT_FOUND'],
                context={"method": method, "supported_methods": ["initialize", "resources/list", "resources/read"]}
            )
            
    except Exception as e:
        # Handle all exceptions and convert to structured error response
        logger.error("Error processing MCP request", extra={
            "method": method,
            "error": str(e),
            "error_type": type(e).__name__,
            "request_id": request_id
        })
        
        # Use centralized error handler to generate structured error response
        error_response = handle_mcp_error(e, context={
            "method": method,
            "request_id": request_id,
            "params": params
        })
        
        return build_jsonrpc_response(error=error_response, id=request_id)


class MCPProtocolHandler:
    """
    Main handler class for managing the lifecycle of the MCP protocol session.
    
    This class provides stateless, robust, and auditable processing of all MCP protocol
    messages, including handshake, message parsing, request routing, and error handling.
    It serves as the primary interface between MCP clients (like Claude Desktop) and the
    LabArchives resource management system.
    
    The handler implements the complete MCP protocol workflow:
    1. Protocol initialization and capability negotiation
    2. Stateless message processing with JSON-RPC 2.0 compliance
    3. Request routing to appropriate resource operations
    4. Comprehensive error handling and audit logging
    5. Session management for interactive AI workflows
    
    Key Features:
    - Stateless design for scalability and reliability
    - Comprehensive audit logging for compliance and diagnostics
    - Protocol-compliant error handling with structured responses
    - Support for all required MCP methods (initialize, resources/list, resources/read)
    - Graceful degradation and recovery from errors
    - Integration with LabArchives resource management layer
    
    The handler maintains no persistent state between requests, ensuring that each
    operation is independent and auditable while supporting concurrent client requests.
    """
    
    def __init__(self, resource_manager: MCPResourceManager):
        """
        Initializes the MCPProtocolHandler with a resource manager and logging.
        
        This constructor sets up the protocol handler with all necessary dependencies
        for MCP protocol operations, including the resource manager for data access
        and a dedicated logger for audit trail generation.
        
        Args:
            resource_manager (MCPResourceManager): Initialized resource manager instance
                                                 for handling LabArchives resource operations
                                                 including listing and reading resources
        """
        # Store the resource manager for delegation of resource operations
        self.resource_manager = resource_manager
        
        # Initialize dedicated logger for handler events and audit trail
        self.logger = logging.getLogger(HANDLER_LOGGER_NAME)
        
        # Log handler initialization for audit trail
        self.logger.info("MCPProtocolHandler initialized", extra={
            "resource_manager_configured": self.resource_manager is not None,
            "handler_instance": id(self)
        })
    
    def handle_message(self, raw_message: str) -> str:
        """
        Processes a single MCP JSON-RPC message and returns a JSON-RPC response string.
        
        This method handles the complete message processing workflow including parsing,
        validation, routing, and response generation. It ensures that all protocol
        errors are properly handled and that comprehensive audit logging is maintained
        for all operations.
        
        The method is stateless, processing each message independently while maintaining
        full audit trails for compliance and diagnostics. It handles both successful
        operations and error conditions with appropriate JSON-RPC 2.0 responses.
        
        Args:
            raw_message (str): Raw JSON-RPC message string from MCP client
            
        Returns:
            str: Serialized JSON-RPC response string containing either successful
                 result or structured error response
        """
        # Log the incoming message for audit trail
        self.logger.info("Processing MCP message", extra={
            "message_length": len(raw_message),
            "handler_instance": id(self)
        })
        
        try:
            # Parse and validate the JSON-RPC message
            parsed_request = parse_jsonrpc_message(raw_message)
            
            # Route the request to appropriate handler
            response = route_mcp_request(parsed_request, self.resource_manager)
            
            # Log successful message processing
            self.logger.info("MCP message processed successfully", extra={
                "method": parsed_request.get('method'),
                "request_id": parsed_request.get('id'),
                "response_length": len(response)
            })
            
            return response
            
        except Exception as e:
            # Handle any errors that occur during message processing
            self.logger.error("Error processing MCP message", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "message_preview": raw_message[:100] + "..." if len(raw_message) > 100 else raw_message
            })
            
            # Generate error response using centralized error handler
            error_response = handle_mcp_error(e, context={
                "operation": "handle_message",
                "message_length": len(raw_message)
            })
            
            # Return error response with null ID (since we couldn't parse the request)
            return build_jsonrpc_response(error=error_response, id=None)
    
    def run_session(self, input_stream: Any = None, output_stream: Any = None) -> None:
        """
        Runs the main protocol session loop, reading JSON-RPC messages and writing responses.
        
        This method implements the interactive session loop for MCP protocol communication,
        reading messages from the input stream, processing them, and writing responses to
        the output stream. It handles session initialization, graceful shutdown, and error
        recovery while maintaining comprehensive audit logging.
        
        The session loop supports:
        - Line-by-line message processing
        - Graceful shutdown on interruption or end-of-file
        - Comprehensive error logging and recovery
        - Audit trail for session lifecycle events
        
        Args:
            input_stream (Any): Input stream for reading JSON-RPC messages (default: stdin)
            output_stream (Any): Output stream for writing JSON-RPC responses (default: stdout)
        """
        # Use default streams if not provided
        if input_stream is None:
            input_stream = sys.stdin
        if output_stream is None:
            output_stream = sys.stdout
        
        # Log session startup
        self.logger.info("Starting MCP protocol session", extra={
            "handler_instance": id(self),
            "input_stream": str(input_stream),
            "output_stream": str(output_stream)
        })
        
        try:
            # Main session loop
            while True:
                try:
                    # Read next message from input stream
                    line = input_stream.readline()
                    
                    # Check for end of input
                    if not line:
                        self.logger.info("End of input reached, terminating session")
                        break
                    
                    # Strip whitespace and process non-empty lines
                    line = line.strip()
                    if line:
                        # Process the message and get response
                        response = self.handle_message(line)
                        
                        # Write response to output stream
                        output_stream.write(response + '\n')
                        output_stream.flush()
                        
                        # Log message exchange for audit trail
                        self.logger.debug("Message exchange completed", extra={
                            "message_length": len(line),
                            "response_length": len(response)
                        })
                
                except KeyboardInterrupt:
                    # Handle graceful shutdown on interruption
                    self.logger.info("Session interrupted by user, shutting down gracefully")
                    break
                    
                except EOFError:
                    # Handle end-of-file condition
                    self.logger.info("End of file reached, terminating session")
                    break
                    
                except Exception as e:
                    # Handle unexpected errors in session loop
                    self.logger.error("Unexpected error in session loop", extra={
                        "error": str(e),
                        "error_type": type(e).__name__
                    })
                    
                    # Generate error response for unexpected errors
                    error_response = handle_mcp_error(e, context={
                        "operation": "session_loop",
                        "session_handler": id(self)
                    })
                    
                    # Send error response to client
                    response = build_jsonrpc_response(error=error_response, id=None)
                    output_stream.write(response + '\n')
                    output_stream.flush()
        
        except Exception as e:
            # Handle critical session errors
            self.logger.critical("Critical error in MCP session", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "handler_instance": id(self)
            })
            
        finally:
            # Log session termination
            self.logger.info("MCP protocol session terminated", extra={
                "handler_instance": id(self)
            })
    
    @staticmethod
    def handle_initialize(request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles the MCP protocol handshake (initialize) request.
        
        This method processes the initialization request from MCP clients, validates
        protocol version compatibility, and returns server capabilities and configuration.
        It establishes the foundation for all subsequent MCP protocol communication.
        
        The initialize method:
        - Validates protocol version compatibility
        - Returns server capabilities and supported methods
        - Provides server identification and version information
        - Establishes the baseline for protocol communication
        
        Args:
            request (Dict[str, Any]): JSON-RPC request object containing initialization
                                     parameters including protocol version
                                     
        Returns:
            Dict[str, Any]: Result object containing server capabilities, protocol version,
                           and server identification information
        """
        logger = logging.getLogger(HANDLER_LOGGER_NAME)
        
        # Extract initialization parameters
        params = request.get('params', {})
        client_version = params.get('protocolVersion', DEFAULT_PROTOCOL_VERSION)
        client_capabilities = params.get('capabilities', {})
        
        # Log initialization request
        logger.info("Processing MCP initialize request", extra={
            "client_version": client_version,
            "client_capabilities": client_capabilities,
            "request_id": request.get('id')
        })
        
        # Validate protocol version compatibility
        if client_version != DEFAULT_PROTOCOL_VERSION:
            logger.warning("Protocol version mismatch", extra={
                "client_version": client_version,
                "server_version": DEFAULT_PROTOCOL_VERSION
            })
            
            # For now, we'll accept the version but log the mismatch
            # Future versions could implement strict version checking
        
        # Build server capabilities response
        capabilities = {
            "resources": {
                "listChanged": False,  # We don't support resource change notifications
                "subscribe": False     # We don't support resource subscriptions
            },
            "tools": {},              # We don't implement tools in this version
            "prompts": {},            # We don't implement prompts in this version
            "logging": {}             # We don't implement logging endpoints in this version
        }
        
        # Build complete initialization response
        result = {
            "protocolVersion": DEFAULT_PROTOCOL_VERSION,
            "capabilities": capabilities,
            "serverInfo": {
                "name": MCP_SERVER_NAME,
                "version": MCP_SERVER_VERSION
            }
        }
        
        # Log successful initialization
        logger.info("MCP initialization completed successfully", extra={
            "protocol_version": DEFAULT_PROTOCOL_VERSION,
            "server_name": MCP_SERVER_NAME,
            "server_version": MCP_SERVER_VERSION
        })
        
        return result
    
    @staticmethod
    def handle_resources_list(request: Dict[str, Any], resource_manager: MCPResourceManager) -> Dict[str, Any]:
        """
        Handles the MCP resources/list request.
        
        This method processes resource listing requests by delegating to the resource
        manager, transforming the result to MCP-compliant format, and returning the
        structured response. It supports hierarchical resource navigation and scope
        enforcement while maintaining comprehensive audit logging.
        
        Args:
            request (Dict[str, Any]): JSON-RPC request object containing optional
                                     parameters for resource listing
            resource_manager (MCPResourceManager): Resource manager instance for
                                                  handling LabArchives resource operations
                                                  
        Returns:
            Dict[str, Any]: Result object containing MCP-compliant resource list
                           with optional metadata
        """
        logger = logging.getLogger(HANDLER_LOGGER_NAME)
        
        # Extract request parameters
        params = request.get('params', {})
        request_id = request.get('id')
        
        # Log resource listing request
        logger.info("Processing MCP resources/list request", extra={
            "params": params,
            "request_id": request_id
        })
        
        # Delegate to resource manager for actual listing
        resources = resource_manager.list_resources()
        
        # Transform to MCP response format
        response = MCPResourceListResponse(
            resources=resources,
            metadata={
                "total_count": len(resources),
                "request_id": request_id
            }
        )
        
        # Log successful resource listing
        logger.info("MCP resources/list completed successfully", extra={
            "resource_count": len(resources),
            "request_id": request_id
        })
        
        return response.dict()
    
    @staticmethod
    def handle_resources_read(request: Dict[str, Any], resource_manager: MCPResourceManager) -> Dict[str, Any]:
        """
        Handles the MCP resources/read request.
        
        This method processes resource reading requests by extracting the resource URI,
        delegating to the resource manager, and transforming the result to MCP-compliant
        format. It supports detailed content retrieval with metadata and optional
        JSON-LD context while maintaining audit logging and error handling.
        
        Args:
            request (Dict[str, Any]): JSON-RPC request object containing resource URI
                                     and optional parameters
            resource_manager (MCPResourceManager): Resource manager instance for
                                                  handling LabArchives resource operations
                                                  
        Returns:
            Dict[str, Any]: Result object containing MCP-compliant resource content
                           with metadata and optional JSON-LD context
                           
        Raises:
            MCPProtocolError: If the resource URI is missing or invalid
        """
        logger = logging.getLogger(HANDLER_LOGGER_NAME)
        
        # Extract request parameters
        params = request.get('params', {})
        request_id = request.get('id')
        
        # Validate that URI parameter is provided
        if 'uri' not in params:
            logger.error("Missing 'uri' parameter in resources/read request", extra={
                "params": params,
                "request_id": request_id
            })
            raise MCPProtocolError(
                message="Missing required 'uri' parameter for resources/read",
                code=MCP_ERROR_CODES['INVALID_PARAMS'],
                context={"method": "resources/read", "params": params}
            )
        
        resource_uri = params['uri']
        
        # Log resource reading request
        logger.info("Processing MCP resources/read request", extra={
            "uri": resource_uri,
            "request_id": request_id
        })
        
        # Delegate to resource manager for actual reading
        resource_content = resource_manager.read_resource(resource_uri)
        
        # Transform to MCP response format
        response = MCPResourceReadResponse(
            resource=resource_content,
            metadata={
                "request_uri": resource_uri,
                "request_id": request_id
            }
        )
        
        # Log successful resource reading
        logger.info("MCP resources/read completed successfully", extra={
            "uri": resource_uri,
            "content_size": len(str(resource_content.content)),
            "request_id": request_id
        })
        
        return response.dict()