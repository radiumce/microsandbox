//! Model Context Protocol (MCP) implementation for microsandbox server.
//!
//! This module implements MCP endpoints served at the `/mcp` endpoint.
//! MCP is essentially JSON-RPC with specific method names and schemas.
//!
//! The module provides:
//! - MCP server initialization and capabilities
//! - Tool definitions for sandbox operations
//! - Prompt templates for common sandbox tasks
//! - Integration with existing sandbox management functions

use serde_json::json;
use tracing::debug;

use crate::{
    error::ServerError,
    payload::{
        JsonRpcRequest, JsonRpcResponse, JsonRpcResponseOrNotification,
        ProcessedNotification,
    },
    simplified_mcp::{
        ExecuteCodeRequest, ExecuteCommandRequest, GetSessionsRequest, GetVolumePathRequest,
        StopSessionRequest, SimplifiedMcpError,
    },
    state::AppState,
    ServerResult,
};

//--------------------------------------------------------------------------------------------------
// Constants
//--------------------------------------------------------------------------------------------------

/// MCP protocol version
const MCP_PROTOCOL_VERSION: &str = "2024-11-05";

/// Server information
const SERVER_NAME: &str = "microsandbox-server";
const SERVER_VERSION: &str = env!("CARGO_PKG_VERSION");

//--------------------------------------------------------------------------------------------------
// Helper Functions
//--------------------------------------------------------------------------------------------------

/// Convert SimplifiedMcpError to ServerError with user-friendly error information
/// 
/// This function creates detailed error responses that include user-friendly messages,
/// suggestions for recovery, and actionable recommendations based on the error type.
fn convert_simplified_mcp_error(error: SimplifiedMcpError) -> ServerError {
    let user_friendly = error.get_user_friendly_message();
    
    // Create detailed error message that includes suggestions
    let detailed_message = format!(
        "{}\n\nSuggestions:\n{}{}",
        user_friendly.message,
        user_friendly.suggestions
            .iter()
            .enumerate()
            .map(|(i, suggestion)| format!("{}. {}", i + 1, suggestion))
            .collect::<Vec<_>>()
            .join("\n"),
        if !user_friendly.recovery_actions.is_empty() {
            format!(
                "\n\nRecovery Actions:\n{}",
                user_friendly.recovery_actions
                    .iter()
                    .enumerate()
                    .map(|(i, action)| format!("{}. {} ({})", i + 1, action.description, action.action))
                    .collect::<Vec<_>>()
                    .join("\n")
            )
        } else {
            String::new()
        }
    );
    
    match error {
        SimplifiedMcpError::SessionNotFound(_) => {
            ServerError::NotFound(detailed_message)
        }
        SimplifiedMcpError::UnsupportedLanguage(_) | 
        SimplifiedMcpError::InvalidFlavor(_) |
        SimplifiedMcpError::ValidationError(_) |
        SimplifiedMcpError::InvalidSessionState(_) => {
            ServerError::ValidationError(crate::error::ValidationError::InvalidInput(detailed_message))
        }
        SimplifiedMcpError::ResourceLimitExceeded(_) |
        SimplifiedMcpError::ResourceAllocationFailed(_) => {
            ServerError::ValidationError(crate::error::ValidationError::InvalidInput(detailed_message))
        }
        SimplifiedMcpError::CompilationError(_) |
        SimplifiedMcpError::RuntimeError(_) |
        SimplifiedMcpError::CodeExecutionError(_) => {
            ServerError::ValidationError(crate::error::ValidationError::InvalidInput(detailed_message))
        }
        SimplifiedMcpError::ExecutionTimeout(_) => {
            ServerError::ValidationError(crate::error::ValidationError::InvalidInput(detailed_message))
        }
        SimplifiedMcpError::SystemError(_) |
        SimplifiedMcpError::InternalError(_) |
        SimplifiedMcpError::SessionCreationFailed(_) |
        SimplifiedMcpError::ConfigurationError(_) |
        SimplifiedMcpError::CleanupFailed(_) |
        SimplifiedMcpError::ResourceCleanupFailed(_) => {
            ServerError::InternalError(detailed_message)
        }
        _ => ServerError::InternalError(detailed_message),
    }
}

/// Create an enhanced MCP response that includes error information in a structured format
/// 
/// This function creates MCP tool responses that include both the original response data
/// and structured error information when errors occur, making it easier for AI assistants
/// to understand and act on the error information.
fn create_enhanced_mcp_response(
    result: Result<serde_json::Value, SimplifiedMcpError>,
    request_id: Option<serde_json::Value>,
) -> ServerResult<JsonRpcResponse> {
    match result {
        Ok(data) => {
            let mcp_result = json!({
                "content": [
                    {
                        "type": "text",
                        "text": serde_json::to_string_pretty(&data)
                            .unwrap_or_else(|_| "Failed to serialize response".to_string())
                    }
                ]
            });
            Ok(JsonRpcResponse::success(mcp_result, request_id))
        }
        Err(error) => {
            let user_friendly = error.get_user_friendly_message();
            
            // Create structured error response for MCP
            let error_response = json!({
                "error": {
                    "type": user_friendly.error_type,
                    "message": user_friendly.message,
                    "details": user_friendly.details,
                    "suggestions": user_friendly.suggestions,
                    "recovery_actions": user_friendly.recovery_actions
                }
            });
            
            let mcp_result = json!({
                "content": [
                    {
                        "type": "text",
                        "text": serde_json::to_string_pretty(&error_response)
                            .unwrap_or_else(|_| "Failed to serialize error response".to_string())
                    }
                ],
                "isError": true
            });
            
            // Still return success at the JSON-RPC level, but with error content
            // This allows the MCP client to receive the structured error information
            Ok(JsonRpcResponse::success(mcp_result, request_id))
        }
    }
}

//--------------------------------------------------------------------------------------------------
// Functions: Handlers
//--------------------------------------------------------------------------------------------------

/// Handle MCP initialize request
pub async fn handle_mcp_initialize(
    _state: AppState,
    request: JsonRpcRequest,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling MCP initialize request");

    let result = json!({
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {
                "listChanged": false
            }
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION
        }
    });

    Ok(JsonRpcResponse::success(result, request.id))
}

/// Handle MCP list tools request
pub async fn handle_mcp_list_tools(
    _state: AppState,
    request: JsonRpcRequest,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling MCP list tools request");

    let tools = json!({
        "tools": [
            {
                "name": "execute_code",
                "description": "Execute code in a sandbox with automatic session management. Creates a new session if none specified or reuses existing session. Supports Python and Node.js templates.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Code to execute"
                        },
                        "template": {
                            "type": "string",
                            "description": "Sandbox template/image to use. If not specified, uses default from environment (currently 'python')",
                            "enum": ["python", "node"]
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Optional session ID - if not provided, a new session will be created"
                        },
                        "flavor": {
                            "type": "string",
                            "description": "Sandbox resource flavor",
                            "enum": ["small", "medium", "large"],
                            "default": "small"
                        }
                    },
                    "required": ["code"]
                }
            },
            {
                "name": "execute_command",
                "description": "Execute a shell command in a sandbox with automatic session management. Creates a new session if none specified or reuses existing session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Command to execute"
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional command arguments"
                        },
                        "template": {
                            "type": "string",
                            "description": "Sandbox template/image to use. If not specified, uses default from environment (currently 'python')",
                            "enum": ["python", "node"]
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Optional session ID - if not provided, a new session will be created"
                        },
                        "flavor": {
                            "type": "string",
                            "description": "Sandbox resource flavor",
                            "enum": ["small", "medium", "large"],
                            "default": "small"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "get_sessions",
                "description": "Get information about active sandbox sessions. Can list all sessions or get details for a specific session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Optional specific session ID to query"
                        }
                    }
                }
            },
            {
                "name": "stop_session",
                "description": "Stop a specific sandbox session and clean up its resources. This will terminate the session and free allocated resources.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID to stop"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "get_volume_path",
                "description": "Get the path to the shared volume inside sandbox containers. This path can be used to access files shared between the host and sandbox.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Optional session ID - if not provided, returns default path"
                        }
                    }
                }
            }
        ]
    });

    Ok(JsonRpcResponse::success(tools, request.id))
}





/// Handle MCP call tool request
pub async fn handle_mcp_call_tool(
    state: AppState,
    request: JsonRpcRequest,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling MCP call tool request");

    let params = request.params.as_object().ok_or_else(|| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            "Request parameters must be an object".to_string(),
        ))
    })?;

    let tool_name = params.get("name").and_then(|v| v.as_str()).ok_or_else(|| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            "Missing required 'name' parameter".to_string(),
        ))
    })?;

    let arguments = params.get("arguments").ok_or_else(|| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            "Missing required 'arguments' parameter".to_string(),
        ))
    })?;

    // Handle simplified MCP tools directly
    match tool_name {
        "execute_code" => {
            return handle_execute_code_tool(state, arguments.clone(), request.id.clone()).await;
        }
        "execute_command" => {
            return handle_execute_command_tool(state, arguments.clone(), request.id.clone()).await;
        }
        "get_sessions" => {
            return handle_get_sessions_tool(state, arguments.clone(), request.id.clone()).await;
        }
        "stop_session" => {
            return handle_stop_session_tool(state, arguments.clone(), request.id.clone()).await;
        }
        "get_volume_path" => {
            return handle_get_volume_path_tool(state, arguments.clone(), request.id.clone()).await;
        }
        _ => {}
    }

    // All tools should have been handled by the simplified MCP handlers above
    return Err(ServerError::NotFound(format!(
        "Tool '{}' not found",
        tool_name
    )));
}

/// Handle MCP notifications/initialized request
pub async fn handle_mcp_notifications_initialized(
    _state: AppState,
    _request: JsonRpcRequest,
) -> ServerResult<ProcessedNotification> {
    debug!("Handling MCP notifications/initialized");

    // This is a notification - no response is expected
    // The client is indicating it has finished initialization
    Ok(ProcessedNotification::processed())
}

//--------------------------------------------------------------------------------------------------
// Simplified MCP Tool Handlers
//--------------------------------------------------------------------------------------------------

/// Handle execute_code tool
async fn handle_execute_code_tool(
    state: AppState,
    arguments: serde_json::Value,
    request_id: Option<serde_json::Value>,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling execute_code tool");

    // Parse request
    let request: ExecuteCodeRequest = serde_json::from_value(arguments).map_err(|e| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            format!("Invalid execute_code parameters: {}", e),
        ))
    })?;

    // Execute the code and handle errors with user-friendly messages
    let result = execute_code_with_error_handling(state, request).await;
    
    // Create enhanced MCP response with structured error information
    create_enhanced_mcp_response(result, request_id)
}

/// Execute code with comprehensive error handling and classification
async fn execute_code_with_error_handling(
    state: AppState,
    request: ExecuteCodeRequest,
) -> Result<serde_json::Value, SimplifiedMcpError> {
    // Get session manager from app state
    let session_manager = state.get_session_manager();

    // Get template from request or use default from session manager config
    let template = request.template.as_deref().unwrap_or_else(|| session_manager.get_default_template());

    // Validate template early
    if !["python", "node"].contains(&template) {
        return Err(SimplifiedMcpError::UnsupportedLanguage(template.to_string()));
    }

    // Get or create session
    let flavor = request.flavor.unwrap_or_default();
    let session_created = request.session_id.is_none();
    let session = session_manager
        .get_or_create_session(request.session_id, template, flavor)
        .await?;

    // Update session status to running
    session_manager
        .update_session_status(&session.id, crate::simplified_mcp::SessionStatus::Running)
        .map_err(|e| SimplifiedMcpError::InternalError(format!("Failed to update session status: {}", e)))?;

    // Execute the code
    let execution_result = {
        let execution_start = std::time::Instant::now();
        
        // TODO: In a future task, this will integrate with actual sandbox creation and code execution
        // For now, we'll simulate the execution with enhanced error detection
        let (stdout, stderr, exit_code) = simulate_code_execution_with_errors(&request.code, template);
        
        let execution_time_ms = execution_start.elapsed().as_millis() as u64;
        
        // Check for execution errors and classify them
        if !stderr.is_empty() || exit_code.map_or(false, |code| code != 0) {
            // Classify the error based on output and template
            let error = crate::simplified_mcp::classify_execution_error(&stdout, &stderr, exit_code, template);
            
            // Update session status to error
            let error_msg = format!("Execution failed: {}", error);
            if let Err(e) = session_manager.update_session_status(
                &session.id, 
                crate::simplified_mcp::SessionStatus::Error(error_msg)
            ) {
                tracing::warn!("Failed to update session status to error: {}", e);
            }
            
            return Err(error);
        }
        
        (stdout, stderr, exit_code, execution_time_ms)
    };

    // Update session status back to ready
    session_manager
        .update_session_status(&session.id, crate::simplified_mcp::SessionStatus::Ready)
        .map_err(|e| SimplifiedMcpError::InternalError(format!("Failed to update session status: {}", e)))?;

    // Touch session to update last accessed time
    session_manager
        .touch_session(&session.id)
        .map_err(|e| SimplifiedMcpError::InternalError(format!("Failed to touch session: {}", e)))?;

    let response = crate::simplified_mcp::ExecutionResponse {
        session_id: session.id,
        stdout: execution_result.0,
        stderr: execution_result.1,
        exit_code: execution_result.2,
        execution_time_ms: execution_result.3,
        session_created,
    };

    Ok(serde_json::to_value(response).map_err(|e| {
        SimplifiedMcpError::InternalError(format!("Failed to serialize response: {}", e))
    })?)
}

/// Handle execute_command tool
async fn handle_execute_command_tool(
    state: AppState,
    arguments: serde_json::Value,
    request_id: Option<serde_json::Value>,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling execute_command tool");

    // Parse request
    let request: ExecuteCommandRequest = serde_json::from_value(arguments).map_err(|e| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            format!("Invalid execute_command parameters: {}", e),
        ))
    })?;

    // Execute the command and handle errors with user-friendly messages
    let result = execute_command_with_error_handling(state, request).await;
    
    // Create enhanced MCP response with structured error information
    create_enhanced_mcp_response(result, request_id)
}

/// Execute command with comprehensive error handling and classification
async fn execute_command_with_error_handling(
    state: AppState,
    request: ExecuteCommandRequest,
) -> Result<serde_json::Value, SimplifiedMcpError> {
    // Get session manager from app state
    let session_manager = state.get_session_manager();

    // Get template from request or use default from session manager config
    let template = request.template.as_deref().unwrap_or_else(|| session_manager.get_default_template());

    // Validate template early
    if !["python", "node"].contains(&template) {
        return Err(SimplifiedMcpError::UnsupportedLanguage(template.to_string()));
    }

    let flavor = request.flavor.unwrap_or_default();
    let session_created = request.session_id.is_none();
    
    let session = session_manager
        .get_or_create_session(request.session_id, template, flavor)
        .await?;

    // Update session status to running
    session_manager
        .update_session_status(&session.id, crate::simplified_mcp::SessionStatus::Running)
        .map_err(|e| SimplifiedMcpError::InternalError(format!("Failed to update session status: {}", e)))?;

    // Execute the command
    let execution_result = {
        let execution_start = std::time::Instant::now();
        
        // Build full command with args
        let full_command = if let Some(args) = &request.args {
            format!("{} {}", request.command, args.join(" "))
        } else {
            request.command.clone()
        };
        
        // TODO: In a future task, this will integrate with actual sandbox command execution
        // For now, we'll simulate the execution with enhanced error detection
        let (stdout, stderr, exit_code) = simulate_command_execution_with_errors(&full_command);
        
        let execution_time_ms = execution_start.elapsed().as_millis() as u64;
        
        // Check for execution errors and classify them
        if !stderr.is_empty() || exit_code != 0 {
            // For commands, we classify errors slightly differently
            let error = classify_command_execution_error(&stdout, &stderr, exit_code, &full_command);
            
            // Update session status to error
            let error_msg = format!("Command execution failed: {}", error);
            if let Err(e) = session_manager.update_session_status(
                &session.id, 
                crate::simplified_mcp::SessionStatus::Error(error_msg)
            ) {
                tracing::warn!("Failed to update session status to error: {}", e);
            }
            
            return Err(error);
        }
        
        (stdout, stderr, exit_code, execution_time_ms)
    };

    // Update session status back to ready
    session_manager
        .update_session_status(&session.id, crate::simplified_mcp::SessionStatus::Ready)
        .map_err(|e| SimplifiedMcpError::InternalError(format!("Failed to update session status: {}", e)))?;

    // Touch session to update last accessed time
    session_manager
        .touch_session(&session.id)
        .map_err(|e| SimplifiedMcpError::InternalError(format!("Failed to touch session: {}", e)))?;

    let response = crate::simplified_mcp::ExecutionResponse {
        session_id: session.id,
        stdout: execution_result.0,
        stderr: execution_result.1,
        exit_code: Some(execution_result.2),
        execution_time_ms: execution_result.3,
        session_created,
    };

    Ok(serde_json::to_value(response).map_err(|e| {
        SimplifiedMcpError::InternalError(format!("Failed to serialize response: {}", e))
    })?)
}

/// Handle get_sessions tool
async fn handle_get_sessions_tool(
    state: AppState,
    arguments: serde_json::Value,
    request_id: Option<serde_json::Value>,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling get_sessions tool");

    // Parse request
    let request: GetSessionsRequest = serde_json::from_value(arguments).map_err(|e| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            format!("Invalid get_sessions parameters: {}", e),
        ))
    })?;

    // Get session manager from app state
    let session_manager = state.get_session_manager();

    let result = session_manager
        .get_sessions(request.session_id.as_deref())
        .map(|sessions| {
            // Convert to summaries
            let session_summaries: Vec<_> = sessions.iter().map(|s| s.to_summary()).collect();
            let response = crate::simplified_mcp::SessionListResponse {
                sessions: session_summaries,
            };
            serde_json::to_value(response).unwrap_or_else(|_| json!({}))
        });

    // Create enhanced MCP response with structured error information
    create_enhanced_mcp_response(result, request_id)
}

/// Handle stop_session tool
async fn handle_stop_session_tool(
    state: AppState,
    arguments: serde_json::Value,
    request_id: Option<serde_json::Value>,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling stop_session tool");

    // Parse request
    let request: StopSessionRequest = serde_json::from_value(arguments).map_err(|e| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            format!("Invalid stop_session parameters: {}", e),
        ))
    })?;

    // Get session manager from app state
    let session_manager = state.get_session_manager();

    let result = session_manager
        .stop_session(&request.session_id)
        .await
        .map(|_| {
            let response = crate::simplified_mcp::StopSessionResponse {
                session_id: request.session_id.clone(),
                success: true,
                message: Some("Session stopped successfully".to_string()),
            };
            serde_json::to_value(response).unwrap_or_else(|_| json!({}))
        });

    // Create enhanced MCP response with structured error information
    create_enhanced_mcp_response(result, request_id)
}

/// Handle get_volume_path tool
async fn handle_get_volume_path_tool(
    state: AppState,
    arguments: serde_json::Value,
    request_id: Option<serde_json::Value>,
) -> ServerResult<JsonRpcResponse> {
    debug!("Handling get_volume_path tool");

    // Parse request
    let _request: GetVolumePathRequest = serde_json::from_value(arguments).map_err(|e| {
        ServerError::ValidationError(crate::error::ValidationError::InvalidInput(
            format!("Invalid get_volume_path parameters: {}", e),
        ))
    })?;

    // Get session manager from app state
    let session_manager = state.get_session_manager();

    // Get volume path information - this operation doesn't typically fail
    let result = Ok(serde_json::to_value(session_manager.get_volume_path_info())
        .unwrap_or_else(|_| json!({})));

    // Create enhanced MCP response with structured error information
    create_enhanced_mcp_response(result, request_id)
}

//--------------------------------------------------------------------------------------------------
// Helper Functions for Simulation
//--------------------------------------------------------------------------------------------------

/// Simulate code execution with enhanced error detection (placeholder for actual implementation)
fn simulate_code_execution_with_errors(code: &str, template: &str) -> (String, String, Option<i32>) {
    match template {
        "python" => {
            if code.contains("SyntaxError") || code.contains("invalid syntax") {
                (String::new(), "SyntaxError: invalid syntax".to_string(), None)
            } else if code.contains("NameError") {
                (String::new(), "NameError: name 'undefined_var' is not defined".to_string(), None)
            } else if code.contains("TypeError") {
                (String::new(), "TypeError: unsupported operand type(s)".to_string(), None)
            } else if code.contains("print") {
                let output = format!("Simulated Python execution:\n{}", code);
                (output, String::new(), None)
            } else if code.contains("error") || code.contains("raise") {
                (String::new(), "RuntimeError: Simulated Python error".to_string(), None)
            } else {
                ("Simulated Python code executed successfully".to_string(), String::new(), None)
            }
        }
        "node" => {
            if code.contains("SyntaxError") || code.contains("unexpected token") {
                (String::new(), "SyntaxError: Unexpected token".to_string(), None)
            } else if code.contains("ReferenceError") {
                (String::new(), "ReferenceError: undefined_var is not defined".to_string(), None)
            } else if code.contains("TypeError") {
                (String::new(), "TypeError: Cannot read property of undefined".to_string(), None)
            } else if code.contains("console.log") {
                let output = format!("Simulated Node.js execution:\n{}", code);
                (output, String::new(), None)
            } else if code.contains("throw") || code.contains("error") {
                (String::new(), "Error: Simulated Node.js error".to_string(), None)
            } else {
                ("Simulated Node.js code executed successfully".to_string(), String::new(), None)
            }
        }
        _ => {
            (String::new(), format!("Unsupported template: {}", template), None)
        }
    }
}

/// Simulate command execution with enhanced error detection (placeholder for actual implementation)
fn simulate_command_execution_with_errors(command: &str) -> (String, String, i32) {
    if command.starts_with("echo") {
        let output = command.strip_prefix("echo ").unwrap_or("").to_string();
        (output, String::new(), 0)
    } else if command.starts_with("ls") {
        if command.contains("nonexistent") {
            (String::new(), "ls: cannot access 'nonexistent': No such file or directory".to_string(), 2)
        } else {
            ("file1.txt\nfile2.py\ndir1/".to_string(), String::new(), 0)
        }
    } else if command.starts_with("cat") && command.contains("nonexistent") {
        (String::new(), "cat: nonexistent: No such file or directory".to_string(), 1)
    } else if command.starts_with("chmod") && command.contains("permission") {
        (String::new(), "chmod: changing permissions of 'file': Operation not permitted".to_string(), 1)
    } else if command.contains("timeout") {
        (String::new(), "Command timed out".to_string(), 124)
    } else if command.contains("killed") {
        (String::new(), "Process was killed".to_string(), 137)
    } else if command.contains("error") {
        (String::new(), "Simulated command error".to_string(), 1)
    } else {
        (format!("Simulated execution of: {}", command), String::new(), 0)
    }
}

/// Classify command execution errors based on stderr output and exit code
fn classify_command_execution_error(
    _stdout: &str,
    stderr: &str,
    exit_code: i32,
    command: &str,
) -> SimplifiedMcpError {
    let stderr_lower = stderr.to_lowercase();
    
    // Check for system-level errors first
    if stderr_lower.contains("permission denied") || stderr_lower.contains("operation not permitted") {
        return SimplifiedMcpError::SystemError(format!(
            "Permission denied while executing command '{}'. Error: {}",
            command,
            crate::simplified_mcp::truncate_error_message(stderr)
        ));
    }
    
    if stderr_lower.contains("no such file") || stderr_lower.contains("cannot access") {
        return SimplifiedMcpError::SystemError(format!(
            "File or directory not found while executing command '{}'. Error: {}",
            command,
            crate::simplified_mcp::truncate_error_message(stderr)
        ));
    }
    
    if stderr_lower.contains("command not found") || stderr_lower.contains("not found") {
        return SimplifiedMcpError::SystemError(format!(
            "Command '{}' not found or not executable. Error: {}",
            command,
            crate::simplified_mcp::truncate_error_message(stderr)
        ));
    }
    
    // Check for timeout/termination
    if exit_code == 124 || stderr_lower.contains("timeout") {
        return SimplifiedMcpError::ExecutionTimeout(format!(
            "Command '{}' timed out during execution",
            command
        ));
    }
    
    if exit_code == 137 || exit_code == 143 || stderr_lower.contains("killed") || stderr_lower.contains("terminated") {
        return SimplifiedMcpError::SystemError(format!(
            "Command '{}' was terminated by the system. Exit code: {}",
            command,
            exit_code
        ));
    }
    
    // Check for resource issues
    if stderr_lower.contains("out of memory") || stderr_lower.contains("cannot allocate") {
        return SimplifiedMcpError::ResourceLimitExceeded(format!(
            "Insufficient memory to execute command '{}'. Error: {}",
            command,
            crate::simplified_mcp::truncate_error_message(stderr)
        ));
    }
    
    if stderr_lower.contains("disk full") || stderr_lower.contains("no space left") {
        return SimplifiedMcpError::ResourceLimitExceeded(format!(
            "Insufficient disk space while executing command '{}'. Error: {}",
            command,
            crate::simplified_mcp::truncate_error_message(stderr)
        ));
    }
    
    // Default to general execution error
    SimplifiedMcpError::CodeExecutionError(format!(
        "Command '{}' failed with exit code {}. Error output: {}",
        command,
        exit_code,
        crate::simplified_mcp::truncate_error_message(stderr)
    ))
}

/// Handle MCP methods
pub async fn handle_mcp_method(
    state: AppState,
    request: JsonRpcRequest,
) -> ServerResult<JsonRpcResponseOrNotification> {
    match request.method.as_str() {
        "initialize" => {
            let response = handle_mcp_initialize(state, request).await?;
            Ok(JsonRpcResponseOrNotification::response(response))
        }
        "tools/list" => {
            let response = handle_mcp_list_tools(state, request).await?;
            Ok(JsonRpcResponseOrNotification::response(response))
        }
        "tools/call" => {
            let response = handle_mcp_call_tool(state, request).await?;
            Ok(JsonRpcResponseOrNotification::response(response))
        }
        "notifications/initialized" => {
            let notification = handle_mcp_notifications_initialized(state, request).await?;
            Ok(JsonRpcResponseOrNotification::notification(notification))
        }
        _ => Err(ServerError::NotFound(format!(
            "MCP method '{}' not found",
            request.method
        ))),
    }
}
