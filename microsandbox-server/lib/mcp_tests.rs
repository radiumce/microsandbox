//! Unit tests for MCP tool interface handlers
//!
//! This module contains tests for the MCP tool interface handlers that integrate
//! with the simplified MCP functionality.

#[cfg(test)]
mod tests {
    use crate::simplified_mcp::*;
    use crate::state::AppState;
    use serde_json::json;
    use std::sync::Arc;

    /// Create a test AppState with simplified MCP components
    async fn create_test_app_state() -> AppState {
        use crate::config::Config;
        use crate::port::PortManager;
        use tokio::sync::RwLock;
        use std::path::PathBuf;
        
        // Create a minimal config for testing
        let config = Arc::new(Config::new(
            None, // key
            "127.0.0.1".to_string(), // host
            8080, // port
            Some(PathBuf::from("/tmp")), // namespace_dir
            true, // dev_mode
        ).unwrap());
        
        // Create a port manager for testing
        let port_manager = Arc::new(RwLock::new(PortManager::new(PathBuf::from("/tmp")).await.unwrap()));
        
        AppState::new(config, port_manager)
    }

    #[tokio::test]
    async fn test_handle_execute_code_tool_success() {
        let _state = create_test_app_state().await;
        
        let arguments = json!({
            "code": "print('Hello, World!')",
            "template": "python",
            "flavor": "small"
        });

        // Note: This test would require mocking the actual code execution
        // For now, we test the request parsing and basic flow
        let request: ExecuteCodeRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.code, "print('Hello, World!')");
        assert_eq!(request.template, Some("python".to_string()));
        assert_eq!(request.flavor, Some(SandboxFlavor::Small));
        assert_eq!(request.session_id, None);
    }

    #[tokio::test]
    async fn test_handle_execute_code_tool_invalid_arguments() {
        let _state = create_test_app_state().await;
        
        // Test missing required field
        let arguments = json!({
            "template": "python"
            // Missing "code" field
        });

        let result: Result<ExecuteCodeRequest, _> = serde_json::from_value(arguments);
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_handle_execute_code_tool_with_session_id() {
        let _state = create_test_app_state().await;
        
        let arguments = json!({
            "code": "x = 42\nprint(x)",
            "template": "python",
            "session_id": "existing-session-123",
            "flavor": "medium"
        });

        let request: ExecuteCodeRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.code, "x = 42\nprint(x)");
        assert_eq!(request.template, Some("python".to_string()));
        assert_eq!(request.session_id, Some("existing-session-123".to_string()));
        assert_eq!(request.flavor, Some(SandboxFlavor::Medium));
    }

    #[tokio::test]
    async fn test_handle_execute_command_tool_success() {
        let _state = create_test_app_state().await;
        
        let arguments = json!({
            "command": "ls",
            "args": ["-la", "/tmp"],
            "template": "python",
            "flavor": "small"
        });

        let request: ExecuteCommandRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.command, "ls");
        assert_eq!(request.args, Some(vec!["-la".to_string(), "/tmp".to_string()]));
        assert_eq!(request.template, Some("python".to_string()));
        assert_eq!(request.flavor, Some(SandboxFlavor::Small));
    }

    #[tokio::test]
    async fn test_handle_execute_command_tool_minimal() {
        let _state = create_test_app_state().await;
        
        let arguments = json!({
            "command": "pwd"
        });

        let request: ExecuteCommandRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.command, "pwd");
        assert_eq!(request.args, None);
        assert_eq!(request.template, None);
        assert_eq!(request.session_id, None);
        assert_eq!(request.flavor, None);
    }

    #[tokio::test]
    async fn test_handle_execute_command_tool_invalid_arguments() {
        let _state = create_test_app_state().await;
        
        // Test missing required field
        let arguments = json!({
            "args": ["-la"]
            // Missing "command" field
        });

        let result: Result<ExecuteCommandRequest, _> = serde_json::from_value(arguments);
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_handle_get_sessions_tool_all_sessions() {
        let state = create_test_app_state().await;
        
        // Create some test sessions first
        let session_manager = state.get_session_manager();
        let _session1 = session_manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let _session2 = session_manager.create_session("node", SandboxFlavor::Medium).await.unwrap();
        
        let arguments = json!({});
        let request: GetSessionsRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.session_id, None);
        
        // Test getting all sessions
        let sessions = session_manager.get_sessions(None).unwrap();
        assert_eq!(sessions.len(), 2);
    }

    #[tokio::test]
    async fn test_handle_get_sessions_tool_specific_session() {
        let state = create_test_app_state().await;
        
        // Create a test session first
        let session_manager = state.get_session_manager();
        let session_id = session_manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        
        let arguments = json!({
            "session_id": session_id
        });
        let request: GetSessionsRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.session_id, Some(session_id.clone()));
        
        // Test getting specific session
        let sessions = session_manager.get_sessions(Some(&session_id)).unwrap();
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].id, session_id);
    }

    #[tokio::test]
    async fn test_handle_get_sessions_tool_nonexistent_session() {
        let state = create_test_app_state().await;
        
        let arguments = json!({
            "session_id": "nonexistent-session"
        });
        let request: GetSessionsRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.session_id, Some("nonexistent-session".to_string()));
        
        // Test getting nonexistent session
        let session_manager = state.get_session_manager();
        let result = session_manager.get_sessions(Some("nonexistent-session"));
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), SimplifiedMcpError::SessionNotFound(_)));
    }

    #[tokio::test]
    async fn test_handle_stop_session_tool_success() {
        let state = create_test_app_state().await;
        
        // Create a test session first
        let session_manager = state.get_session_manager();
        let session_id = session_manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        
        let arguments = json!({
            "session_id": session_id
        });
        let request: StopSessionRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.session_id, session_id);
        
        // Test stopping the session
        let result = session_manager.stop_session(&session_id).await;
        assert!(result.is_ok());
        
        // Verify session is stopped
        let session = session_manager.get_session(&session_id).unwrap();
        assert_eq!(session.status, SessionStatus::Stopped);
    }

    #[tokio::test]
    async fn test_handle_stop_session_tool_nonexistent_session() {
        let state = create_test_app_state().await;
        
        let arguments = json!({
            "session_id": "nonexistent-session"
        });
        let request: StopSessionRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.session_id, "nonexistent-session");
        
        // Test stopping nonexistent session
        let session_manager = state.get_session_manager();
        let result = session_manager.stop_session("nonexistent-session").await;
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), SimplifiedMcpError::SessionNotFound(_)));
    }

    #[tokio::test]
    async fn test_handle_stop_session_tool_invalid_arguments() {
        let _state = create_test_app_state().await;
        
        // Test missing required field
        let arguments = json!({});
        let result: Result<StopSessionRequest, _> = serde_json::from_value(arguments);
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_handle_get_volume_path_tool_no_shared_volume() {
        let state = create_test_app_state().await;
        
        let arguments = json!({});
        let request: GetVolumePathRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.session_id, None);
        
        // Test getting volume path when no shared volume is configured
        let session_manager = state.get_session_manager();
        let volume_info = session_manager.get_volume_path_info();
        assert_eq!(volume_info.volume_path, "/shared");
        assert!(!volume_info.available);
        assert!(volume_info.description.contains("No shared volume configured"));
    }

    #[tokio::test]
    async fn test_handle_get_volume_path_tool_with_session_id() {
        let state = create_test_app_state().await;
        
        let arguments = json!({
            "session_id": "test-session"
        });
        let request: GetVolumePathRequest = serde_json::from_value(arguments).unwrap();
        
        assert_eq!(request.session_id, Some("test-session".to_string()));
        
        // The volume path should be the same regardless of session ID
        let session_manager = state.get_session_manager();
        let volume_info = session_manager.get_volume_path_info();
        assert_eq!(volume_info.volume_path, "/shared");
    }

    // Test error response formatting
    #[test]
    fn test_execution_response_formatting() {
        let response = ExecutionResponse {
            session_id: "test-session-123".to_string(),
            stdout: "Hello, World!\n".to_string(),
            stderr: "".to_string(),
            exit_code: Some(0),
            execution_time_ms: 250,
            session_created: true,
        };

        // Test serialization
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("test-session-123"));
        assert!(json.contains("Hello, World!"));
        assert!(json.contains("250"));
        assert!(json.contains("true"));

        // Test that JSON contains expected values
        assert!(json.contains("\"session_id\":\"test-session-123\""));
        assert!(json.contains("\"exit_code\":0"));
    }

    #[test]
    fn test_session_list_response_formatting() {
        let sessions = vec![
            SessionSummary {
                id: "session-1".to_string(),
                language: "python".to_string(),
                flavor: "small".to_string(),
                status: "ready".to_string(),
                created_at: "just now".to_string(),
                last_accessed: "just now".to_string(),
                uptime_seconds: 0,
            },
            SessionSummary {
                id: "session-2".to_string(),
                language: "node".to_string(),
                flavor: "medium".to_string(),
                status: "running".to_string(),
                created_at: "2 minutes ago".to_string(),
                last_accessed: "1 minute ago".to_string(),
                uptime_seconds: 120,
            },
        ];

        let response = SessionListResponse { sessions };

        // Test serialization
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("session-1"));
        assert!(json.contains("session-2"));
        assert!(json.contains("python"));
        assert!(json.contains("node"));
        assert!(json.contains("small"));
        assert!(json.contains("medium"));

        // Test that JSON contains expected session data
        assert!(json.contains("\"sessions\":["));
        assert!(json.contains("\"uptime_seconds\":120"));
    }

    #[test]
    fn test_stop_session_response_formatting() {
        let response = StopSessionResponse {
            session_id: "test-session".to_string(),
            success: true,
            message: Some("Session stopped successfully".to_string()),
        };

        // Test serialization
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("test-session"));
        assert!(json.contains("true"));
        assert!(json.contains("Session stopped successfully"));

        // Test that JSON contains expected values
        assert!(json.contains("\"session_id\":\"test-session\""));
        assert!(json.contains("\"success\":true"));
    }

    #[test]
    fn test_volume_path_response_formatting() {
        let response = VolumePathResponse {
            volume_path: "/shared".to_string(),
            description: "Shared volume mounted at /shared (host: /tmp/shared)".to_string(),
            available: true,
        };

        // Test serialization
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("/shared"));
        assert!(json.contains("Shared volume mounted"));
        assert!(json.contains("true"));

        // Test that JSON contains expected values
        assert!(json.contains("\"volume_path\":\"/shared\""));
        assert!(json.contains("\"available\":true"));
    }

    // Test request validation edge cases
    #[test]
    fn test_execute_code_request_validation() {
        // Test with invalid flavor
        let json = r#"{
            "code": "print('hello')",
            "template": "python",
            "flavor": "invalid-flavor"
        }"#;
        
        let result: Result<ExecuteCodeRequest, _> = serde_json::from_str(json);
        assert!(result.is_err());

        // Test with empty code
        let json = r#"{
            "code": "",
            "template": "python"
        }"#;
        
        let request: ExecuteCodeRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.code, "");
        assert_eq!(request.template, Some("python".to_string()));
    }

    #[test]
    fn test_execute_command_request_validation() {
        // Test with empty command
        let json = r#"{
            "command": ""
        }"#;
        
        let request: ExecuteCommandRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.command, "");

        // Test with empty args array
        let json = r#"{
            "command": "ls",
            "args": []
        }"#;
        
        let request: ExecuteCommandRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.command, "ls");
        assert_eq!(request.args, Some(vec![]));
    }

    // Integration tests for tool interface workflows
    #[tokio::test]
    async fn test_tool_interface_workflow_create_and_stop_session() {
        let state = create_test_app_state().await;
        
        // Step 1: Execute code to create a new session
        let execute_args = json!({
            "code": "x = 42",
            "template": "python",
            "flavor": "small"
        });
        let _execute_request: ExecuteCodeRequest = serde_json::from_value(execute_args).unwrap();
        
        // Simulate session creation (in real implementation, this would execute code)
        let session_manager = state.get_session_manager();
        let session_id = session_manager.create_session("python", SandboxFlavor::Small).await.unwrap();

        // Step 2: Get sessions to verify creation
        let get_sessions_args = json!({});
        let _get_sessions_request: GetSessionsRequest = serde_json::from_value(get_sessions_args).unwrap();
        
        let sessions = session_manager.get_sessions(None).unwrap();
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].id, session_id);

        // Step 3: Stop the session
        let stop_args = json!({
            "session_id": session_id
        });
        let stop_request: StopSessionRequest = serde_json::from_value(stop_args).unwrap();
        
        session_manager.stop_session(&stop_request.session_id).await.unwrap();
        
        // Verify session is stopped
        let session = session_manager.get_session(&session_id).unwrap();
        assert_eq!(session.status, SessionStatus::Stopped);
    }

    #[tokio::test]
    async fn test_tool_interface_workflow_reuse_session() {
        let state = create_test_app_state().await;
        
        // Step 1: Create initial session
        let session_manager = state.get_session_manager();
        let session_id = session_manager.create_session("python", SandboxFlavor::Medium).await.unwrap();

        // Step 2: Execute code with existing session ID
        let execute_args = json!({
            "code": "y = x + 1",
            "template": "python",
            "session_id": session_id,
            "flavor": "medium"
        });
        let _execute_request: ExecuteCodeRequest = serde_json::from_value(execute_args).unwrap();
        
        assert_eq!(_execute_request.session_id, Some(session_id.clone()));
        assert_eq!(_execute_request.template, Some("python".to_string()));
        assert_eq!(_execute_request.flavor, Some(SandboxFlavor::Medium));

        // Step 3: Execute command in same session
        let command_args = json!({
            "command": "echo",
            "args": ["hello"],
            "session_id": session_id
        });
        let command_request: ExecuteCommandRequest = serde_json::from_value(command_args).unwrap();
        
        assert_eq!(command_request.session_id, Some(session_id.clone()));
        assert_eq!(command_request.command, "echo");
        assert_eq!(command_request.args, Some(vec!["hello".to_string()]));

        // Verify session still exists and is accessible
        let session = session_manager.get_session(&session_id).unwrap();
        assert_eq!(session.language, "python");
        assert_eq!(session.flavor, SandboxFlavor::Medium);
    }

    #[tokio::test]
    async fn test_tool_interface_error_handling() {
        let state = create_test_app_state().await;
        
        // Test execute code with unsupported template
        let execute_args = json!({
            "code": "System.out.println(\"Hello\");",
            "template": "java"
        });
        let _execute_request: ExecuteCodeRequest = serde_json::from_value(execute_args).unwrap();
        
        // This would fail in the actual handler due to unsupported template
        let session_manager = state.get_session_manager();
        let result = session_manager.create_session("java", SandboxFlavor::Small).await;
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), SimplifiedMcpError::UnsupportedLanguage(_)));

        // Test stop session with invalid session ID
        let stop_args = json!({
            "session_id": "invalid-session-id"
        });
        let stop_request: StopSessionRequest = serde_json::from_value(stop_args).unwrap();
        
        let result = session_manager.stop_session(&stop_request.session_id).await;
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), SimplifiedMcpError::SessionNotFound(_)));

        // Test get sessions with invalid session ID
        let result = session_manager.get_sessions(Some("invalid-session-id"));
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), SimplifiedMcpError::SessionNotFound(_)));
    }
}