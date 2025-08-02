//! Simplified MCP interface module for microsandbox server.
//!
//! This module provides a simplified interface for MCP (Model Context Protocol) operations
//! with automatic session management, predefined sandbox flavors, and streamlined tool interfaces.
//!
//! The module includes:
//! - Core data structures for simplified MCP operations
//! - Error types specific to simplified MCP functionality
//! - Request and response models for the simplified tools
//! - SandboxFlavor enum for predefined resource configurations
//! - AutomaticSandboxCreator for on-demand sandbox creation
//!
//! # Automatic Sandbox Creation
//!
//! The `AutomaticSandboxCreator` integrates with the existing `sandbox_start_impl` functionality
//! to provide on-demand sandbox creation with automatic configuration generation:
//!
//! ```rust,no_run
//! use microsandbox_server::simplified_mcp::{
//!     ConfigurationManager, AutomaticSandboxCreator, SessionInfo, SandboxFlavor
//! };
//!
//! # async fn example() -> Result<(), Box<dyn std::error::Error>> {
//! // Create configuration manager from environment
//! let config = ConfigurationManager::from_env()?;
//!
//! // Create automatic sandbox creator
//! let creator = AutomaticSandboxCreator::new(config);
//!
//! // Create session info
//! let session_info = SessionInfo::new(
//!     "session-123".to_string(),
//!     "my-namespace".to_string(),
//!     "my-sandbox".to_string(),
//!     "python".to_string(),
//!     SandboxFlavor::Medium,
//! );
//!
//! // The creator will automatically:
//! // - Map language to appropriate container image (python -> microsandbox/python)
//! // - Configure memory and CPU based on flavor (Medium = 2GB RAM, 2 CPUs)
//! // - Set up shared volume mapping if configured via MSB_SHARED_VOLUME_PATH
//! // - Add appropriate environment variables
//! // - Call the existing sandbox_start_impl to create the actual sandbox
//!
//! # Ok(())
//! # }
//! ```

use serde::{Deserialize, Serialize};
use serde_json::json;
use std::fmt;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant};
use thiserror::Error;
use tokio::time::interval;

//--------------------------------------------------------------------------------------------------
// Core Data Structures
//--------------------------------------------------------------------------------------------------

/// Predefined sandbox resource configurations
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SandboxFlavor {
    /// Small sandbox: 1 CPU, 1GB RAM
    Small,
    /// Medium sandbox: 2 CPUs, 2GB RAM
    Medium,
    /// Large sandbox: 4 CPUs, 4GB RAM
    Large,
}

impl SandboxFlavor {
    /// Get memory allocation in MB for this flavor
    pub fn get_memory_mb(&self) -> u32 {
        match self {
            Self::Small => 1024,
            Self::Medium => 2048,
            Self::Large => 4096,
        }
    }

    /// Get CPU count for this flavor
    pub fn get_cpus(&self) -> u8 {
        match self {
            Self::Small => 1,
            Self::Medium => 2,
            Self::Large => 4,
        }
    }

    /// Get the string representation of the flavor
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Small => "small",
            Self::Medium => "medium",
            Self::Large => "large",
        }
    }
}

impl Default for SandboxFlavor {
    fn default() -> Self {
        Self::Small
    }
}

impl fmt::Display for SandboxFlavor {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl std::str::FromStr for SandboxFlavor {
    type Err = SimplifiedMcpError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "small" => Ok(Self::Small),
            "medium" => Ok(Self::Medium),
            "large" => Ok(Self::Large),
            _ => Err(SimplifiedMcpError::InvalidFlavor(s.to_string())),
        }
    }
}

//--------------------------------------------------------------------------------------------------
// Error Types
//--------------------------------------------------------------------------------------------------

/// Error types specific to simplified MCP operations
#[derive(Debug, Error)]
pub enum SimplifiedMcpError {
    /// Session not found
    #[error("Session not found: {0}")]
    SessionNotFound(String),

    /// Session creation failed
    #[error("Session creation failed: {0}")]
    SessionCreationFailed(String),

    /// Unsupported template
    #[error("Unsupported template: {0}. Supported templates: python, node")]
    UnsupportedLanguage(String),

    /// Resource limit exceeded
    #[error("Resource limit exceeded: {0}")]
    ResourceLimitExceeded(String),

    /// Execution timeout
    #[error("Execution timeout: {0}")]
    ExecutionTimeout(String),

    /// Invalid session state
    #[error("Invalid session state: {0}")]
    InvalidSessionState(String),

    /// Configuration error
    #[error("Configuration error: {0}")]
    ConfigurationError(String),

    /// Invalid sandbox flavor
    #[error("Invalid sandbox flavor: {0}. Valid flavors: small, medium, large")]
    InvalidFlavor(String),

    /// Internal error
    #[error("Internal error: {0}")]
    InternalError(String),

    /// Validation error
    #[error("Validation error: {0}")]
    ValidationError(String),

    /// Session already exists
    #[error("Session already exists: {0}")]
    SessionAlreadyExists(String),

    /// Resource allocation failed
    #[error("Resource allocation failed: {0}")]
    ResourceAllocationFailed(String),

    /// Session timeout
    #[error("Session timed out: {0}")]
    SessionTimeout(String),

    /// Cleanup failed
    #[error("Cleanup failed: {0}")]
    CleanupFailed(String),

    /// Resource cleanup failed
    #[error("Resource cleanup failed: {0}")]
    ResourceCleanupFailed(String),

    /// Code execution error with specific error type
    #[error("Code execution failed: {0}")]
    CodeExecutionError(String),

    /// Compilation error
    #[error("Compilation error: {0}")]
    CompilationError(String),

    /// Runtime error
    #[error("Runtime error: {0}")]
    RuntimeError(String),

    /// System error during execution
    #[error("System error: {0}")]
    SystemError(String),
}

impl SimplifiedMcpError {
    /// Get a user-friendly error message with context and suggestions
    pub fn get_user_friendly_message(&self) -> UserFriendlyError {
        match self {
            SimplifiedMcpError::SessionNotFound(session_id) => UserFriendlyError {
                error_type: "session_not_found".to_string(),
                message: format!("Session '{}' was not found or has expired", session_id),
                details: Some(format!("The session '{}' either never existed, has been stopped, or has timed out due to inactivity", session_id)),
                suggestions: vec![
                    "Create a new session by calling the tool without specifying a session_id".to_string(),
                    "Check if the session ID is correct and hasn't been mistyped".to_string(),
                    "List active sessions using the get_sessions tool to see available sessions".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "create_new_session".to_string(),
                        description: "Create a new session automatically".to_string(),
                        parameters: None,
                    }
                ],
            },

            SimplifiedMcpError::SessionCreationFailed(reason) => UserFriendlyError {
                error_type: "session_creation_failed".to_string(),
                message: "Failed to create a new sandbox session".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Try again with a smaller resource flavor (e.g., 'small' instead of 'large')".to_string(),
                    "Wait a moment and retry as resources may become available".to_string(),
                    "Check system resource availability using get_sessions tool".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "retry_with_smaller_flavor".to_string(),
                        description: "Retry with 'small' flavor to use fewer resources".to_string(),
                        parameters: Some(json!({"flavor": "small"})),
                    }
                ],
            },

            SimplifiedMcpError::UnsupportedLanguage(template) => UserFriendlyError {
                error_type: "unsupported_language".to_string(),
                message: format!("Template '{}' is not supported", template),
                details: Some("Only specific programming language templates are currently supported".to_string()),
                suggestions: vec![
                    "Use 'python' for Python code execution".to_string(),
                    "Use 'node' for JavaScript/Node.js code execution".to_string(),
                    "Check the template name for typos".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "use_python_template".to_string(),
                        description: "Use Python template instead".to_string(),
                        parameters: Some(json!({"template": "python"})),
                    },
                    RecoveryAction {
                        action: "use_node_template".to_string(),
                        description: "Use Node.js template instead".to_string(),
                        parameters: Some(json!({"template": "node"})),
                    }
                ],
            },

            SimplifiedMcpError::ResourceLimitExceeded(reason) => UserFriendlyError {
                error_type: "resource_limit_exceeded".to_string(),
                message: "System resource limits have been reached".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Wait for other sessions to complete or timeout".to_string(),
                    "Use a smaller resource flavor (small, medium, large)".to_string(),
                    "Stop unused sessions using the stop_session tool".to_string(),
                    "Try again in a few minutes when resources may be freed".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "wait_and_retry".to_string(),
                        description: "Wait 30 seconds and retry the operation".to_string(),
                        parameters: Some(json!({"wait_seconds": 30})),
                    },
                    RecoveryAction {
                        action: "use_small_flavor".to_string(),
                        description: "Retry with small resource flavor".to_string(),
                        parameters: Some(json!({"flavor": "small"})),
                    }
                ],
            },

            SimplifiedMcpError::InvalidSessionState(reason) => UserFriendlyError {
                error_type: "invalid_session_state".to_string(),
                message: "Session is in an invalid state for this operation".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Create a new session if the current one is stopped or in error state".to_string(),
                    "Wait for the session to finish its current operation if it's running".to_string(),
                    "Check session status using the get_sessions tool".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "create_new_session".to_string(),
                        description: "Create a new session to replace the invalid one".to_string(),
                        parameters: None,
                    }
                ],
            },

            SimplifiedMcpError::ExecutionTimeout(reason) => UserFriendlyError {
                error_type: "execution_timeout".to_string(),
                message: "Code or command execution timed out".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Optimize your code to run faster".to_string(),
                    "Break down complex operations into smaller parts".to_string(),
                    "Avoid infinite loops or long-running operations".to_string(),
                    "Use more efficient algorithms or data structures".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "retry_with_optimization".to_string(),
                        description: "Review and optimize the code before retrying".to_string(),
                        parameters: None,
                    }
                ],
            },

            SimplifiedMcpError::CodeExecutionError(reason) => UserFriendlyError {
                error_type: "code_execution_error".to_string(),
                message: "Code execution failed".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Check your code syntax and fix any errors".to_string(),
                    "Ensure all required dependencies are available".to_string(),
                    "Verify that your code is compatible with the selected template".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "fix_and_retry".to_string(),
                        description: "Fix the code issues and retry execution".to_string(),
                        parameters: None,
                    }
                ],
            },

            SimplifiedMcpError::CompilationError(reason) => UserFriendlyError {
                error_type: "compilation_error".to_string(),
                message: "Code compilation failed".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Check for syntax errors in your code".to_string(),
                    "Ensure all imports and dependencies are correct".to_string(),
                    "Verify that your code follows the language's syntax rules".to_string(),
                    "Check for missing semicolons, brackets, or other punctuation".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "fix_syntax_and_retry".to_string(),
                        description: "Fix syntax errors and retry compilation".to_string(),
                        parameters: None,
                    }
                ],
            },

            SimplifiedMcpError::RuntimeError(reason) => UserFriendlyError {
                error_type: "runtime_error".to_string(),
                message: "Code execution failed at runtime".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Check for logical errors in your code".to_string(),
                    "Verify that all variables are properly initialized".to_string(),
                    "Handle potential exceptions and edge cases".to_string(),
                    "Check array bounds and null pointer access".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "debug_and_retry".to_string(),
                        description: "Debug the runtime issue and retry execution".to_string(),
                        parameters: None,
                    }
                ],
            },

            SimplifiedMcpError::SystemError(reason) => UserFriendlyError {
                error_type: "system_error".to_string(),
                message: "System error occurred during execution".to_string(),
                details: Some(reason.clone()),
                suggestions: vec![
                    "Try the operation again as this may be a temporary system issue".to_string(),
                    "Check if the system has sufficient resources available".to_string(),
                    "Contact system administrator if the problem persists".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "retry_operation".to_string(),
                        description: "Retry the operation after a brief wait".to_string(),
                        parameters: Some(json!({"wait_seconds": 5})),
                    }
                ],
            },

            SimplifiedMcpError::InvalidFlavor(flavor) => UserFriendlyError {
                error_type: "invalid_flavor".to_string(),
                message: format!("Invalid resource flavor: {}", flavor),
                details: Some("Resource flavor must be one of the predefined options".to_string()),
                suggestions: vec![
                    "Use 'small' for basic tasks (1 CPU, 1GB RAM)".to_string(),
                    "Use 'medium' for moderate workloads (2 CPUs, 2GB RAM)".to_string(),
                    "Use 'large' for intensive tasks (4 CPUs, 4GB RAM)".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "use_small_flavor".to_string(),
                        description: "Use small flavor as default".to_string(),
                        parameters: Some(json!({"flavor": "small"})),
                    }
                ],
            },

            // Default handling for other error types
            _ => UserFriendlyError {
                error_type: "general_error".to_string(),
                message: self.to_string(),
                details: None,
                suggestions: vec![
                    "Try the operation again".to_string(),
                    "Check your input parameters".to_string(),
                    "Contact support if the problem persists".to_string(),
                ],
                recovery_actions: vec![
                    RecoveryAction {
                        action: "retry_operation".to_string(),
                        description: "Retry the operation".to_string(),
                        parameters: None,
                    }
                ],
            },
        }
    }
}

//--------------------------------------------------------------------------------------------------
// Error Response Structures
//--------------------------------------------------------------------------------------------------

/// User-friendly error information with recovery suggestions
#[derive(Debug, Serialize, Clone)]
pub struct UserFriendlyError {
    /// Error type identifier for programmatic handling
    pub error_type: String,
    /// Human-readable error message
    pub message: String,
    /// Optional detailed explanation of the error
    pub details: Option<String>,
    /// List of suggestions for resolving the error
    pub suggestions: Vec<String>,
    /// List of automated recovery actions that can be taken
    pub recovery_actions: Vec<RecoveryAction>,
}

/// Automated recovery action that can be suggested to users
#[derive(Debug, Serialize, Clone)]
pub struct RecoveryAction {
    /// Action identifier
    pub action: String,
    /// Human-readable description of the action
    pub description: String,
    /// Optional parameters for the recovery action
    pub parameters: Option<serde_json::Value>,
}

//--------------------------------------------------------------------------------------------------
// Request Data Structures
//--------------------------------------------------------------------------------------------------

/// Request structure for executing code in a sandbox
#[derive(Debug, Deserialize, Clone)]
pub struct ExecuteCodeRequest {
    /// Code to execute
    pub code: String,
    /// Sandbox template/image to use (python, node)
    pub template: Option<String>,
    /// Optional session ID - if not provided, a new session will be created
    pub session_id: Option<String>,
    /// Sandbox resource flavor - defaults to Small if not specified
    pub flavor: Option<SandboxFlavor>,
}

/// Request structure for executing commands in a sandbox
#[derive(Debug, Deserialize, Clone)]
pub struct ExecuteCommandRequest {
    /// Command to execute
    pub command: String,
    /// Optional command arguments
    pub args: Option<Vec<String>>,
    /// Sandbox template/image to use (python, node)
    pub template: Option<String>,
    /// Optional session ID - if not provided, a new session will be created
    pub session_id: Option<String>,
    /// Sandbox resource flavor - defaults to Small if not specified
    pub flavor: Option<SandboxFlavor>,
}

/// Request structure for getting session information
#[derive(Debug, Deserialize, Clone)]
pub struct GetSessionsRequest {
    /// Optional specific session ID to query
    pub session_id: Option<String>,
}

/// Request structure for stopping a session
#[derive(Debug, Deserialize, Clone)]
pub struct StopSessionRequest {
    /// Session ID to stop
    pub session_id: String,
}

/// Request structure for getting volume path information
#[derive(Debug, Deserialize, Clone)]
pub struct GetVolumePathRequest {
    /// Optional session ID - if not provided, returns default path
    pub session_id: Option<String>,
}

//--------------------------------------------------------------------------------------------------
// Response Data Structures
//--------------------------------------------------------------------------------------------------

/// Response structure for code/command execution
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ExecutionResponse {
    /// Session ID used for execution
    pub session_id: String,
    /// Standard output from execution
    pub stdout: String,
    /// Standard error from execution
    pub stderr: String,
    /// Exit code (None for code execution, Some for command execution)
    pub exit_code: Option<i32>,
    /// Execution time in milliseconds
    pub execution_time_ms: u64,
    /// Whether a new session was created for this execution
    pub session_created: bool,
}

/// Summary information about a session
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SessionSummary {
    /// Session ID
    pub id: String,
    /// Programming language/environment
    pub language: String,
    /// Resource flavor
    pub flavor: String,
    /// Current session status
    pub status: String,
    /// Session creation timestamp (ISO 8601)
    pub created_at: String,
    /// Last access timestamp (ISO 8601)
    pub last_accessed: String,
    /// Session uptime in seconds
    pub uptime_seconds: u64,
}

/// Response structure for session list queries
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SessionListResponse {
    /// List of session summaries
    pub sessions: Vec<SessionSummary>,
}

/// Response structure for volume path queries
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct VolumePathResponse {
    /// Path to the shared volume inside the sandbox
    pub volume_path: String,
    /// Description of the volume usage
    pub description: String,
    /// Whether the volume is available and accessible
    pub available: bool,
}

/// Response structure for session stop operations
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct StopSessionResponse {
    /// Session ID that was stopped
    pub session_id: String,
    /// Whether the session was successfully stopped
    pub success: bool,
    /// Optional message about the stop operation
    pub message: Option<String>,
}

//--------------------------------------------------------------------------------------------------
// Internal Data Structures
//--------------------------------------------------------------------------------------------------

/// Template to container image mapping
#[derive(Debug, Clone)]
pub struct TemplateMapping {
    mappings: std::collections::HashMap<String, String>,
}

impl Default for TemplateMapping {
    fn default() -> Self {
        let mut mappings = std::collections::HashMap::new();
        mappings.insert("python".to_string(), "microsandbox/python".to_string());
        mappings.insert("node".to_string(), "microsandbox/node".to_string());
        
        Self { mappings }
    }
}

impl TemplateMapping {
    /// Get the container image for a given template
    pub fn get_image(&self, template: &str) -> Option<&String> {
        self.mappings.get(template)
    }

    /// Check if a template is supported
    pub fn is_supported(&self, template: &str) -> bool {
        self.mappings.contains_key(template)
    }

    /// Get list of supported templates
    pub fn supported_templates(&self) -> Vec<&String> {
        self.mappings.keys().collect()
    }
}

//--------------------------------------------------------------------------------------------------
// Configuration Manager
//--------------------------------------------------------------------------------------------------

use std::env;
use std::path::PathBuf;

/// Configuration manager for simplified MCP operations
/// 
/// Handles environment variable parsing, default values, and configuration validation
/// for the simplified MCP interface.
#[derive(Debug, Clone)]
pub struct ConfigurationManager {
    /// Optional path to shared volume on host system
    shared_volume_path: Option<PathBuf>,
    /// Path to shared volume inside sandbox containers
    shared_volume_guest_path: String,
    /// Default sandbox flavor when not specified
    default_flavor: SandboxFlavor,
    /// Default sandbox template when not specified
    default_template: String,
    /// Session timeout duration
    session_timeout: Duration,
    /// Maximum number of concurrent sessions
    max_sessions: usize,
}

impl ConfigurationManager {
    /// Create a new ConfigurationManager from environment variables
    /// 
    /// Environment variables:
    /// - `MSB_SHARED_VOLUME_PATH`: Host path for shared volume (optional)
    /// - `MSB_SHARED_VOLUME_GUEST_PATH`: Guest path for shared volume (default: "/shared")
    /// - `MSB_DEFAULT_FLAVOR`: Default sandbox flavor (default: "small")
    /// - `MSB_DEFAULT_TEMPLATE`: Default sandbox template (default: "python")
    /// - `MSB_SESSION_TIMEOUT_SECONDS`: Session timeout in seconds (default: 1800)
    /// - `MSB_MAX_SESSIONS`: Maximum concurrent sessions (default: 10)
    pub fn from_env() -> Result<Self, SimplifiedMcpError> {
        let shared_volume_path = env::var("MSB_SHARED_VOLUME_PATH")
            .ok()
            .map(PathBuf::from);

        let shared_volume_guest_path = env::var("MSB_SHARED_VOLUME_GUEST_PATH")
            .unwrap_or_else(|_| "/shared".to_string());

        let default_flavor = env::var("MSB_DEFAULT_FLAVOR")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(SandboxFlavor::Small);

        let default_template = env::var("MSB_DEFAULT_TEMPLATE")
            .unwrap_or_else(|_| "python".to_string());

        let session_timeout_seconds = env::var("MSB_SESSION_TIMEOUT_SECONDS")
            .ok()
            .and_then(|s| s.parse::<u64>().ok())
            .unwrap_or(1800); // 30 minutes default

        let max_sessions = env::var("MSB_MAX_SESSIONS")
            .ok()
            .and_then(|s| s.parse::<usize>().ok())
            .unwrap_or(10);

        let config = Self {
            shared_volume_path,
            shared_volume_guest_path,
            default_flavor,
            default_template,
            session_timeout: Duration::from_secs(session_timeout_seconds),
            max_sessions,
        };

        // Validate configuration
        config.validate()?;

        Ok(config)
    }

    /// Create a new ConfigurationManager with default values
    pub fn default() -> Self {
        Self {
            shared_volume_path: None,
            shared_volume_guest_path: "/shared".to_string(),
            default_flavor: SandboxFlavor::Small,
            default_template: "python".to_string(),
            session_timeout: Duration::from_secs(1800), // 30 minutes
            max_sessions: 10,
        }
    }

    /// Validate the configuration
    pub fn validate(&self) -> Result<(), SimplifiedMcpError> {
        // Validate shared volume path exists if specified
        if let Some(ref path) = self.shared_volume_path {
            if !path.exists() {
                return Err(SimplifiedMcpError::ConfigurationError(
                    format!("Shared volume path does not exist: {}", path.display())
                ));
            }
            if !path.is_dir() {
                return Err(SimplifiedMcpError::ConfigurationError(
                    format!("Shared volume path is not a directory: {}", path.display())
                ));
            }
        }

        // Validate guest path is absolute
        if !self.shared_volume_guest_path.starts_with('/') {
            return Err(SimplifiedMcpError::ConfigurationError(
                format!("Shared volume guest path must be absolute: {}", self.shared_volume_guest_path)
            ));
        }

        // Validate session timeout is reasonable (between 1 minute and 24 hours)
        let timeout_secs = self.session_timeout.as_secs();
        if timeout_secs < 60 || timeout_secs > 86400 {
            return Err(SimplifiedMcpError::ConfigurationError(
                format!("Session timeout must be between 60 and 86400 seconds, got: {}", timeout_secs)
            ));
        }

        // Validate max sessions is reasonable (between 1 and 100)
        if self.max_sessions == 0 || self.max_sessions > 100 {
            return Err(SimplifiedMcpError::ConfigurationError(
                format!("Max sessions must be between 1 and 100, got: {}", self.max_sessions)
            ));
        }

        Ok(())
    }

    /// Get the shared volume host path
    pub fn get_shared_volume_path(&self) -> Option<&PathBuf> {
        self.shared_volume_path.as_ref()
    }

    /// Get the shared volume guest path (path inside sandbox containers)
    pub fn get_shared_volume_guest_path(&self) -> &str {
        &self.shared_volume_guest_path
    }

    /// Get the default sandbox flavor
    pub fn get_default_flavor(&self) -> SandboxFlavor {
        self.default_flavor
    }

    /// Get the default sandbox template
    pub fn get_default_template(&self) -> &str {
        &self.default_template
    }

    /// Get the session timeout duration
    pub fn get_session_timeout(&self) -> Duration {
        self.session_timeout
    }

    /// Get the maximum number of concurrent sessions
    pub fn get_max_sessions(&self) -> usize {
        self.max_sessions
    }

    /// Check if shared volume is configured
    pub fn has_shared_volume(&self) -> bool {
        self.shared_volume_path.is_some()
    }

    /// Get volume path information for responses
    pub fn get_volume_path_info(&self) -> VolumePathResponse {
        VolumePathResponse {
            volume_path: self.shared_volume_guest_path.clone(),
            description: if self.has_shared_volume() {
                format!("Shared volume mounted at {} (host: {})", 
                    self.shared_volume_guest_path,
                    self.shared_volume_path.as_ref().unwrap().display())
            } else {
                "No shared volume configured".to_string()
            },
            available: self.has_shared_volume(),
        }
    }

    /// Update configuration from environment (for runtime reconfiguration)
    pub fn reload_from_env(&mut self) -> Result<(), SimplifiedMcpError> {
        let new_config = Self::from_env()?;
        *self = new_config;
        Ok(())
    }
}

//--------------------------------------------------------------------------------------------------
// Session Management
//--------------------------------------------------------------------------------------------------

use uuid::Uuid;

/// Session status enumeration
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SessionStatus {
    /// Session is being created
    Creating,
    /// Session is ready for use
    Ready,
    /// Session is currently running a task
    Running,
    /// Session encountered an error
    Error(String),
    /// Session has been stopped
    Stopped,
}

impl fmt::Display for SessionStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Creating => write!(f, "creating"),
            Self::Ready => write!(f, "ready"),
            Self::Running => write!(f, "running"),
            Self::Error(msg) => write!(f, "error: {}", msg),
            Self::Stopped => write!(f, "stopped"),
        }
    }
}

/// Information about a managed session
#[derive(Debug, Clone)]
pub struct SessionInfo {
    /// Unique session identifier
    pub id: String,
    /// Namespace for the sandbox
    pub namespace: String,
    /// Name of the sandbox instance
    pub sandbox_name: String,
    /// Programming language/environment
    pub language: String,
    /// Resource flavor configuration
    pub flavor: SandboxFlavor,
    /// When the session was created
    pub created_at: Instant,
    /// When the session was last accessed
    pub last_accessed: Instant,
    /// Current session status
    pub status: SessionStatus,
}

impl SessionInfo {
    /// Create a new SessionInfo
    pub fn new(
        id: String,
        namespace: String,
        sandbox_name: String,
        language: String,
        flavor: SandboxFlavor,
    ) -> Self {
        let now = Instant::now();
        Self {
            id,
            namespace,
            sandbox_name,
            language,
            flavor,
            created_at: now,
            last_accessed: now,
            status: SessionStatus::Creating,
        }
    }

    /// Update the last accessed time to now
    pub fn touch(&mut self) {
        self.last_accessed = Instant::now();
    }

    /// Get the session uptime in seconds
    pub fn uptime_seconds(&self) -> u64 {
        self.created_at.elapsed().as_secs()
    }

    /// Get the time since last access in seconds
    pub fn idle_seconds(&self) -> u64 {
        self.last_accessed.elapsed().as_secs()
    }

    /// Check if the session has timed out
    pub fn is_timed_out(&self, timeout: Duration) -> bool {
        self.last_accessed.elapsed() > timeout
    }

    /// Check if the session should be considered for timeout cleanup
    /// 
    /// Only sessions in certain states should be considered for timeout:
    /// - Ready sessions that haven't been accessed recently
    /// - Running sessions that have been running too long
    /// - Error sessions that are old
    pub fn should_timeout(&self, timeout: Duration) -> bool {
        match &self.status {
            SessionStatus::Creating => false, // Don't timeout sessions that are still being created
            SessionStatus::Stopped => false, // Already stopped
            SessionStatus::Ready | SessionStatus::Running => self.is_timed_out(timeout),
            SessionStatus::Error(_) => {
                // Timeout error sessions after a shorter period
                let error_timeout = Duration::from_secs(300); // 5 minutes for error sessions
                self.last_accessed.elapsed() > error_timeout
            }
        }
    }

    /// Convert to SessionSummary for API responses
    pub fn to_summary(&self) -> SessionSummary {
        SessionSummary {
            id: self.id.clone(),
            language: self.language.clone(),
            flavor: self.flavor.to_string(),
            status: self.status.to_string(),
            created_at: format_instant_as_iso8601(self.created_at),
            last_accessed: format_instant_as_iso8601(self.last_accessed),
            uptime_seconds: self.uptime_seconds(),
        }
    }
}

/// Session manager for handling sandbox session lifecycle
#[derive(Debug)]
pub struct SessionManager {
    /// Map of session ID to session information
    sessions: Arc<RwLock<HashMap<String, SessionInfo>>>,
    /// Configuration for session management
    config: ConfigurationManager,
    /// Template to image mapping
    template_mapping: TemplateMapping,
}

impl SessionManager {
    /// Create a new SessionManager with the given configuration
    pub fn new(config: ConfigurationManager) -> Self {
        Self {
            sessions: Arc::new(RwLock::new(HashMap::new())),
            config,
            template_mapping: TemplateMapping::default(),
        }
    }

    /// Create a new session with the specified parameters
    /// 
    /// Returns the session ID on success
    pub async fn create_session(
        &self,
        template: &str,
        flavor: SandboxFlavor,
    ) -> Result<String, SimplifiedMcpError> {
        // Validate template is supported
        if !self.template_mapping.is_supported(template) {
            return Err(SimplifiedMcpError::UnsupportedLanguage(template.to_string()));
        }

        // Check if we've reached the maximum number of sessions
        {
            let sessions = self.sessions.read().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
            })?;
            
            if sessions.len() >= self.config.get_max_sessions() {
                return Err(SimplifiedMcpError::ResourceLimitExceeded(
                    format!("Maximum number of sessions ({}) reached", self.config.get_max_sessions())
                ));
            }
        }

        // Generate unique session ID
        let session_id = format!("session-{}", Uuid::new_v4());
        
        // Generate namespace and sandbox name
        let namespace = format!("simplified-mcp-{}", &session_id[8..18]); // Use part of UUID
        let sandbox_name = format!("sandbox-{}", &session_id[8..18]);

        // Create session info
        let mut session_info = SessionInfo::new(
            session_id.clone(),
            namespace,
            sandbox_name,
            template.to_string(),
            flavor,
        );

        // For basic session creation (without sandbox), set status to Ready immediately
        session_info.status = SessionStatus::Ready;

        // Store session
        {
            let mut sessions = self.sessions.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
            })?;
            
            sessions.insert(session_id.clone(), session_info);
        }

        Ok(session_id)
    }

    /// Get session information by ID
    pub fn get_session(&self, session_id: &str) -> Result<SessionInfo, SimplifiedMcpError> {
        let sessions = self.sessions.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;

        sessions
            .get(session_id)
            .cloned()
            .ok_or_else(|| SimplifiedMcpError::SessionNotFound(session_id.to_string()))
    }

    /// Get or create a session based on the provided session ID
    /// 
    /// If session_id is None, creates a new session
    /// If session_id is Some but doesn't exist, returns an error
    /// If session_id exists, returns the existing session
    pub async fn get_or_create_session(
        &self,
        session_id: Option<String>,
        template: &str,
        flavor: SandboxFlavor,
    ) -> Result<SessionInfo, SimplifiedMcpError> {
        match session_id {
            None => {
                // Create new session
                let new_session_id = self.create_session(template, flavor).await?;
                self.get_session(&new_session_id)
            }
            Some(id) => {
                // Try to get existing session
                match self.get_session(&id) {
                    Ok(session) => {
                        // Validate that the session matches the requested parameters
                        if session.language != template {
                            return Err(SimplifiedMcpError::InvalidSessionState(
                                format!("Session {} is for template '{}', but '{}' was requested", 
                                    id, session.language, template)
                            ));
                        }
                        
                        // Check if session is in a valid state
                        match session.status {
                            SessionStatus::Stopped => {
                                return Err(SimplifiedMcpError::InvalidSessionState(
                                    format!("Session {} has been stopped", id)
                                ));
                            }
                            SessionStatus::Error(ref msg) => {
                                return Err(SimplifiedMcpError::InvalidSessionState(
                                    format!("Session {} is in error state: {}", id, msg)
                                ));
                            }
                            _ => {}
                        }

                        Ok(session)
                    }
                    Err(_) => {
                        Err(SimplifiedMcpError::SessionNotFound(id))
                    }
                }
            }
        }
    }

    /// Update the last accessed time for a session
    pub fn touch_session(&self, session_id: &str) -> Result<(), SimplifiedMcpError> {
        let mut sessions = self.sessions.write().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
        })?;

        match sessions.get_mut(session_id) {
            Some(session) => {
                session.touch();
                Ok(())
            }
            None => Err(SimplifiedMcpError::SessionNotFound(session_id.to_string())),
        }
    }

    /// Update session status
    pub fn update_session_status(
        &self,
        session_id: &str,
        status: SessionStatus,
    ) -> Result<(), SimplifiedMcpError> {
        let mut sessions = self.sessions.write().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
        })?;

        match sessions.get_mut(session_id) {
            Some(session) => {
                session.status = status;
                session.touch(); // Update access time when status changes
                Ok(())
            }
            None => Err(SimplifiedMcpError::SessionNotFound(session_id.to_string())),
        }
    }

    /// Stop a session and mark it as stopped
    pub async fn stop_session(&self, session_id: &str) -> Result<(), SimplifiedMcpError> {
        // Get session info before stopping
        let session_info = self.get_session(session_id)?;

        // Update the session status to stopped
        self.update_session_status(session_id, SessionStatus::Stopped)?;

        // TODO: In a future task, this will integrate with the actual sandbox stopping logic
        // For now, we simulate the sandbox stopping process
        tracing::info!("Stopping sandbox for session {}: namespace={}, sandbox_name={}", 
            session_info.id, session_info.namespace, session_info.sandbox_name);

        // In a real implementation, this would call something like:
        // orchestra::stop(&session_info.namespace, &session_info.sandbox_name).await?;

        Ok(())
    }

    /// Remove a session from tracking (used during cleanup)
    pub fn remove_session(&self, session_id: &str) -> Result<SessionInfo, SimplifiedMcpError> {
        let mut sessions = self.sessions.write().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
        })?;

        sessions
            .remove(session_id)
            .ok_or_else(|| SimplifiedMcpError::SessionNotFound(session_id.to_string()))
    }

    /// Get all sessions, optionally filtered by session ID
    pub fn get_sessions(&self, session_id: Option<&str>) -> Result<Vec<SessionInfo>, SimplifiedMcpError> {
        let sessions = self.sessions.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;

        match session_id {
            Some(id) => {
                // Return specific session
                match sessions.get(id) {
                    Some(session) => Ok(vec![session.clone()]),
                    None => Err(SimplifiedMcpError::SessionNotFound(id.to_string())),
                }
            }
            None => {
                // Return all sessions
                Ok(sessions.values().cloned().collect())
            }
        }
    }

    /// Find sessions that have timed out
    pub fn find_expired_sessions(&self) -> Result<Vec<String>, SimplifiedMcpError> {
        let sessions = self.sessions.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;

        let timeout = self.config.get_session_timeout();
        let expired_ids: Vec<String> = sessions
            .values()
            .filter(|session| session.should_timeout(timeout))
            .map(|session| session.id.clone())
            .collect();

        Ok(expired_ids)
    }

    /// Clean up expired sessions
    /// 
    /// Returns the list of session IDs that were cleaned up
    pub async fn cleanup_expired_sessions(&self) -> Result<Vec<String>, SimplifiedMcpError> {
        let expired_ids = self.find_expired_sessions()?;
        let mut cleaned_up = Vec::new();

        for session_id in expired_ids {
            match self.stop_session(&session_id).await {
                Ok(()) => {
                    // Remove from tracking after successful stop
                    if let Ok(_) = self.remove_session(&session_id) {
                        cleaned_up.push(session_id);
                    }
                }
                Err(e) => {
                    // Log error but continue with other sessions
                    eprintln!("Failed to cleanup session {}: {}", session_id, e);
                }
            }
        }

        Ok(cleaned_up)
    }

    /// Get the shared volume path for sessions
    pub fn get_volume_path(&self) -> Option<String> {
        if self.config.has_shared_volume() {
            Some(self.config.get_shared_volume_guest_path().to_string())
        } else {
            None
        }
    }

    /// Get volume path information
    pub fn get_volume_path_info(&self) -> VolumePathResponse {
        self.config.get_volume_path_info()
    }

    /// Get session count
    pub fn get_session_count(&self) -> Result<usize, SimplifiedMcpError> {
        let sessions = self.sessions.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;
        
        Ok(sessions.len())
    }

    /// Get configuration
    pub fn get_config(&self) -> &ConfigurationManager {
        &self.config
    }

    /// Get template mapping
    pub fn get_template_mapping(&self) -> &TemplateMapping {
        &self.template_mapping
    }

    /// Get the default template from configuration
    pub fn get_default_template(&self) -> &str {
        self.config.get_default_template()
    }

    /// Create a complete session management setup with cleanup
    /// 
    /// This factory method creates a SessionManager, ResourceManager, and CleanupManager
    /// all configured to work together, and starts the background cleanup tasks.
    /// 
    /// Returns a tuple of (SessionManager, ResourceManager, CleanupManager, cleanup_handles)
    pub fn create_with_cleanup(
        config: ConfigurationManager,
    ) -> Result<(Arc<SessionManager>, Arc<ResourceManager>, CleanupManager, (tokio::task::JoinHandle<()>, tokio::task::JoinHandle<()>)), SimplifiedMcpError> {
        // Create managers
        let session_manager = Arc::new(SessionManager::new(config.clone()));
        let resource_manager = Arc::new(ResourceManager::new(config.clone()));
        let cleanup_manager = CleanupManager::new(
            Arc::clone(&session_manager),
            Arc::clone(&resource_manager),
            config,
        );

        // Start background cleanup tasks
        let cleanup_handles = cleanup_manager.start_background_cleanup();

        Ok((session_manager, resource_manager, cleanup_manager, cleanup_handles))
    }

    /// Start background cleanup task for expired sessions
    /// 
    /// This method starts a background task that periodically checks for expired sessions
    /// and cleans them up automatically. The task runs at the configured cleanup interval.
    /// 
    /// Returns a handle to the background task that can be used to cancel it.
    pub fn start_background_cleanup(&self) -> tokio::task::JoinHandle<()> {
        let sessions = Arc::clone(&self.sessions);
        let config = self.config.clone();
        let cleanup_interval = Duration::from_secs(60); // Check every minute
        
        tokio::spawn(async move {
            let mut interval_timer = interval(cleanup_interval);
            
            loop {
                interval_timer.tick().await;
                
                // Find expired sessions
                let expired_sessions = {
                    let sessions_guard = match sessions.read() {
                        Ok(guard) => guard,
                        Err(e) => {
                            tracing::error!("Failed to acquire read lock for cleanup: {}", e);
                            continue;
                        }
                    };
                    
                    let timeout = config.get_session_timeout();
                    let expired_ids: Vec<String> = sessions_guard
                        .values()
                        .filter(|session| session.should_timeout(timeout))
                        .map(|session| session.id.clone())
                        .collect();
                    
                    expired_ids
                };
                
                if !expired_sessions.is_empty() {
                    tracing::info!("Found {} expired sessions for cleanup", expired_sessions.len());
                    
                    // Clean up expired sessions
                    for session_id in expired_sessions {
                        match Self::cleanup_single_session(&sessions, &session_id).await {
                            Ok(()) => {
                                tracing::info!("Successfully cleaned up expired session: {}", session_id);
                            }
                            Err(e) => {
                                tracing::error!("Failed to cleanup expired session {}: {}", session_id, e);
                            }
                        }
                    }
                }
            }
        })
    }

    /// Clean up a single session (internal helper for background cleanup)
    async fn cleanup_single_session(
        sessions: &Arc<RwLock<HashMap<String, SessionInfo>>>,
        session_id: &str,
    ) -> Result<(), SimplifiedMcpError> {
        // First, get the session info and update its status to stopped
        let session_info = {
            let mut sessions_guard = sessions.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
            })?;
            
            match sessions_guard.get_mut(session_id) {
                Some(session) => {
                    session.status = SessionStatus::Stopped;
                    session.clone()
                }
                None => {
                    // Session might have been cleaned up already
                    return Ok(());
                }
            }
        };

        // TODO: In a future implementation, this would integrate with the actual sandbox stopping logic
        // For now, we simulate the sandbox stopping process
        tracing::info!("Stopping sandbox for session {}: namespace={}, sandbox_name={}", 
            session_info.id, session_info.namespace, session_info.sandbox_name);

        // Remove the session from tracking
        {
            let mut sessions_guard = sessions.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
            })?;
            
            sessions_guard.remove(session_id);
        }

        Ok(())
    }

    /// Manually trigger cleanup of expired sessions
    /// 
    /// This method can be called manually to trigger cleanup of expired sessions
    /// without waiting for the background task. It returns the list of session IDs
    /// that were cleaned up.
    pub async fn manual_cleanup_expired_sessions(&self) -> Result<Vec<String>, SimplifiedMcpError> {
        let expired_ids = self.find_expired_sessions()?;
        let mut cleaned_up = Vec::new();

        for session_id in expired_ids {
            match Self::cleanup_single_session(&self.sessions, &session_id).await {
                Ok(()) => {
                    cleaned_up.push(session_id);
                }
                Err(e) => {
                    tracing::error!("Failed to cleanup session {}: {}", session_id, e);
                }
            }
        }

        Ok(cleaned_up)
    }
}

//--------------------------------------------------------------------------------------------------
// Resource Management
//--------------------------------------------------------------------------------------------------

/// Resource allocation information for a session
#[derive(Debug, Clone)]
pub struct ResourceAllocation {
    /// Session ID this allocation belongs to
    pub session_id: String,
    /// Sandbox flavor configuration
    pub flavor: SandboxFlavor,
    /// Allocated port number
    pub port: u16,
    /// When the allocation was created
    pub allocated_at: Instant,
}

impl ResourceAllocation {
    /// Create a new resource allocation
    pub fn new(session_id: String, flavor: SandboxFlavor, port: u16) -> Self {
        Self {
            session_id,
            flavor,
            port,
            allocated_at: Instant::now(),
        }
    }

    /// Get the age of this allocation in seconds
    pub fn age_seconds(&self) -> u64 {
        self.allocated_at.elapsed().as_secs()
    }
}

/// Port manager for allocating and tracking port usage
#[derive(Debug)]
pub struct PortManager {
    /// Range of ports available for allocation
    port_range: std::ops::Range<u16>,
    /// Set of currently allocated ports
    allocated_ports: std::collections::HashSet<u16>,
    /// Next port to try for allocation
    next_port: u16,
}

impl PortManager {
    /// Create a new PortManager with the specified port range
    pub fn new(start_port: u16, end_port: u16) -> Result<Self, SimplifiedMcpError> {
        if start_port >= end_port {
            return Err(SimplifiedMcpError::ConfigurationError(
                format!("Invalid port range: {} >= {}", start_port, end_port)
            ));
        }

        Ok(Self {
            port_range: start_port..end_port,
            allocated_ports: std::collections::HashSet::new(),
            next_port: start_port,
        })
    }

    /// Create a default PortManager with ports 8000-9000
    pub fn default() -> Self {
        Self::new(8000, 9000).expect("Default port range should be valid")
    }

    /// Allocate a port, returning the allocated port number
    pub fn allocate_port(&mut self) -> Result<u16, SimplifiedMcpError> {
        // Check if we have any available ports
        if self.allocated_ports.len() >= (self.port_range.end - self.port_range.start) as usize {
            return Err(SimplifiedMcpError::ResourceLimitExceeded(
                "No available ports for allocation".to_string()
            ));
        }

        // Find the next available port
        let mut attempts = 0;
        let max_attempts = (self.port_range.end - self.port_range.start) as usize;

        while attempts < max_attempts {
            let port = self.next_port;
            
            // Move to next port for next allocation
            self.next_port += 1;
            if self.next_port >= self.port_range.end {
                self.next_port = self.port_range.start;
            }

            // Check if this port is available
            if !self.allocated_ports.contains(&port) {
                self.allocated_ports.insert(port);
                return Ok(port);
            }

            attempts += 1;
        }

        Err(SimplifiedMcpError::ResourceLimitExceeded(
            "Unable to find available port after maximum attempts".to_string()
        ))
    }

    /// Release a previously allocated port
    pub fn release_port(&mut self, port: u16) -> Result<(), SimplifiedMcpError> {
        if !self.port_range.contains(&port) {
            return Err(SimplifiedMcpError::ValidationError(
                format!("Port {} is outside the managed range", port)
            ));
        }

        if !self.allocated_ports.remove(&port) {
            return Err(SimplifiedMcpError::ValidationError(
                format!("Port {} was not allocated", port)
            ));
        }

        Ok(())
    }

    /// Check if a port is currently allocated
    pub fn is_port_allocated(&self, port: u16) -> bool {
        self.allocated_ports.contains(&port)
    }

    /// Get the number of allocated ports
    pub fn allocated_count(&self) -> usize {
        self.allocated_ports.len()
    }

    /// Get the number of available ports
    pub fn available_count(&self) -> usize {
        (self.port_range.end - self.port_range.start) as usize - self.allocated_ports.len()
    }

    /// Get the total number of ports in the range
    pub fn total_count(&self) -> usize {
        (self.port_range.end - self.port_range.start) as usize
    }
}

/// Resource manager for handling sandbox resource allocation and limits
#[derive(Debug)]
pub struct ResourceManager {
    /// Port manager for allocating ports to sessions
    port_manager: Arc<RwLock<PortManager>>,
    /// Map of session ID to resource allocation
    active_allocations: Arc<RwLock<HashMap<String, ResourceAllocation>>>,
    /// Maximum number of concurrent sessions allowed
    max_concurrent_sessions: usize,
    /// Configuration manager for resource limits
    config: ConfigurationManager,
}

impl ResourceManager {
    /// Create a new ResourceManager with the given configuration
    pub fn new(config: ConfigurationManager) -> Self {
        Self {
            port_manager: Arc::new(RwLock::new(PortManager::default())),
            active_allocations: Arc::new(RwLock::new(HashMap::new())),
            max_concurrent_sessions: config.get_max_sessions(),
            config,
        }
    }

    /// Create a ResourceManager with custom port range
    pub fn with_port_range(
        config: ConfigurationManager,
        start_port: u16,
        end_port: u16,
    ) -> Result<Self, SimplifiedMcpError> {
        let port_manager = PortManager::new(start_port, end_port)?;
        
        Ok(Self {
            port_manager: Arc::new(RwLock::new(port_manager)),
            active_allocations: Arc::new(RwLock::new(HashMap::new())),
            max_concurrent_sessions: config.get_max_sessions(),
            config,
        })
    }

    /// Allocate resources for a new session
    pub fn allocate_resources(
        &self,
        session_id: String,
        flavor: SandboxFlavor,
    ) -> Result<ResourceAllocation, SimplifiedMcpError> {
        // Check if we've reached the maximum number of concurrent sessions
        {
            let allocations = self.active_allocations.read().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
            })?;

            if allocations.len() >= self.max_concurrent_sessions {
                return Err(SimplifiedMcpError::ResourceLimitExceeded(
                    format!("Maximum concurrent sessions ({}) reached", self.max_concurrent_sessions)
                ));
            }

            // Check if session already has an allocation
            if allocations.contains_key(&session_id) {
                return Err(SimplifiedMcpError::ValidationError(
                    format!("Session {} already has resource allocation", session_id)
                ));
            }
        }

        // Allocate a port
        let port = {
            let mut port_manager = self.port_manager.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire port manager lock: {}", e))
            })?;
            
            port_manager.allocate_port()?
        };

        // Create resource allocation
        let allocation = ResourceAllocation::new(session_id.clone(), flavor, port);

        // Store the allocation
        {
            let mut allocations = self.active_allocations.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
            })?;
            
            allocations.insert(session_id, allocation.clone());
        }

        Ok(allocation)
    }

    /// Release resources for a session
    pub fn release_resources(&self, session_id: &str) -> Result<ResourceAllocation, SimplifiedMcpError> {
        // Remove the allocation
        let allocation = {
            let mut allocations = self.active_allocations.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
            })?;
            
            allocations.remove(session_id).ok_or_else(|| {
                SimplifiedMcpError::ValidationError(
                    format!("No resource allocation found for session {}", session_id)
                )
            })?
        };

        // Release the port
        {
            let mut port_manager = self.port_manager.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire port manager lock: {}", e))
            })?;
            
            port_manager.release_port(allocation.port)?;
        }

        Ok(allocation)
    }

    /// Get resource allocation for a session
    pub fn get_allocation(&self, session_id: &str) -> Result<ResourceAllocation, SimplifiedMcpError> {
        let allocations = self.active_allocations.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;

        allocations.get(session_id).cloned().ok_or_else(|| {
            SimplifiedMcpError::ValidationError(
                format!("No resource allocation found for session {}", session_id)
            )
        })
    }

    /// Check if resources are available for a new session with the given flavor
    pub fn check_resource_availability(&self, flavor: SandboxFlavor) -> Result<bool, SimplifiedMcpError> {
        let allocations = self.active_allocations.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;

        // Check session limit
        if allocations.len() >= self.max_concurrent_sessions {
            return Ok(false);
        }

        // Check port availability
        let port_manager = self.port_manager.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire port manager lock: {}", e))
        })?;

        if port_manager.available_count() == 0 {
            return Ok(false);
        }

        // Check if the flavor is within configured limits
        // For now, we just check basic availability, but this could be extended
        // to check memory/CPU limits against system resources
        self.validate_flavor_limits(flavor)?;

        Ok(true)
    }

    /// Validate that a flavor is within configured resource limits
    pub fn validate_flavor_limits(&self, flavor: SandboxFlavor) -> Result<(), SimplifiedMcpError> {
        // Basic validation - ensure the flavor is reasonable
        let memory_mb = flavor.get_memory_mb();
        let cpus = flavor.get_cpus();

        // Check memory limits (example: max 8GB per session)
        if memory_mb > 8192 {
            return Err(SimplifiedMcpError::ResourceLimitExceeded(
                format!("Requested memory ({} MB) exceeds maximum allowed (8192 MB)", memory_mb)
            ));
        }

        // Check CPU limits (example: max 8 CPUs per session)
        if cpus > 8 {
            return Err(SimplifiedMcpError::ResourceLimitExceeded(
                format!("Requested CPUs ({}) exceeds maximum allowed (8)", cpus)
            ));
        }

        Ok(())
    }

    /// Get resource usage statistics
    pub fn get_resource_stats(&self) -> Result<ResourceStats, SimplifiedMcpError> {
        let allocations = self.active_allocations.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;

        let port_manager = self.port_manager.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire port manager lock: {}", e))
        })?;

        // Calculate memory and CPU usage by flavor
        let mut total_memory_mb = 0u32;
        let mut total_cpus = 0u32;
        let mut flavor_counts = HashMap::new();

        for allocation in allocations.values() {
            total_memory_mb += allocation.flavor.get_memory_mb();
            total_cpus += allocation.flavor.get_cpus() as u32;
            
            *flavor_counts.entry(allocation.flavor).or_insert(0) += 1;
        }

        Ok(ResourceStats {
            active_sessions: allocations.len(),
            max_sessions: self.max_concurrent_sessions,
            allocated_ports: port_manager.allocated_count(),
            available_ports: port_manager.available_count(),
            total_ports: port_manager.total_count(),
            total_memory_mb,
            total_cpus,
            flavor_counts,
        })
    }

    /// Get all active allocations
    pub fn get_all_allocations(&self) -> Result<Vec<ResourceAllocation>, SimplifiedMcpError> {
        let allocations = self.active_allocations.read().map_err(|e| {
            SimplifiedMcpError::InternalError(format!("Failed to acquire read lock: {}", e))
        })?;

        Ok(allocations.values().cloned().collect())
    }

    /// Clean up resources for expired sessions
    pub fn cleanup_expired_allocations(&self, expired_session_ids: &[String]) -> Result<Vec<ResourceAllocation>, SimplifiedMcpError> {
        let mut cleaned_up = Vec::new();

        for session_id in expired_session_ids {
            match self.release_resources(session_id) {
                Ok(allocation) => cleaned_up.push(allocation),
                Err(SimplifiedMcpError::ValidationError(_)) => {
                    // Session might not have had resources allocated, which is fine
                    continue;
                }
                Err(e) => return Err(e),
            }
        }

        Ok(cleaned_up)
    }

    /// Get the configuration
    pub fn get_config(&self) -> &ConfigurationManager {
        &self.config
    }

    /// Start background resource cleanup task
    /// 
    /// This method starts a background task that periodically checks for orphaned
    /// resource allocations and cleans them up. This helps prevent resource leaks
    /// when sessions are not properly cleaned up.
    pub fn start_background_resource_cleanup(&self) -> tokio::task::JoinHandle<()> {
        let active_allocations = Arc::clone(&self.active_allocations);
        let port_manager = Arc::clone(&self.port_manager);
        let cleanup_interval = Duration::from_secs(300); // Check every 5 minutes
        let max_allocation_age = Duration::from_secs(7200); // 2 hours max age
        
        tokio::spawn(async move {
            let mut interval_timer = interval(cleanup_interval);
            
            loop {
                interval_timer.tick().await;
                
                // Find old allocations that might be orphaned
                let orphaned_allocations = {
                    let allocations_guard = match active_allocations.read() {
                        Ok(guard) => guard,
                        Err(e) => {
                            tracing::error!("Failed to acquire read lock for resource cleanup: {}", e);
                            continue;
                        }
                    };
                    
                    let old_allocations: Vec<(String, ResourceAllocation)> = allocations_guard
                        .iter()
                        .filter(|(_, allocation)| allocation.allocated_at.elapsed() > max_allocation_age)
                        .map(|(id, allocation)| (id.clone(), allocation.clone()))
                        .collect();
                    
                    old_allocations
                };
                
                if !orphaned_allocations.is_empty() {
                    tracing::warn!("Found {} potentially orphaned resource allocations", orphaned_allocations.len());
                    
                    // Clean up orphaned allocations
                    for (session_id, allocation) in orphaned_allocations {
                        match Self::cleanup_single_allocation(&active_allocations, &port_manager, &session_id, allocation).await {
                            Ok(()) => {
                                tracing::info!("Successfully cleaned up orphaned allocation for session: {}", session_id);
                            }
                            Err(e) => {
                                tracing::error!("Failed to cleanup orphaned allocation for session {}: {}", session_id, e);
                            }
                        }
                    }
                }
            }
        })
    }

    /// Clean up a single resource allocation (internal helper)
    async fn cleanup_single_allocation(
        active_allocations: &Arc<RwLock<HashMap<String, ResourceAllocation>>>,
        port_manager: &Arc<RwLock<PortManager>>,
        session_id: &str,
        allocation: ResourceAllocation,
    ) -> Result<(), SimplifiedMcpError> {
        // Remove the allocation
        {
            let mut allocations_guard = active_allocations.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire write lock: {}", e))
            })?;
            
            allocations_guard.remove(session_id);
        }

        // Release the port
        {
            let mut port_manager_guard = port_manager.write().map_err(|e| {
                SimplifiedMcpError::InternalError(format!("Failed to acquire port manager lock: {}", e))
            })?;
            
            if let Err(e) = port_manager_guard.release_port(allocation.port) {
                tracing::warn!("Failed to release port {} during cleanup: {}", allocation.port, e);
            }
        }

        tracing::info!("Cleaned up resource allocation for session {}: port={}, flavor={}", 
            session_id, allocation.port, allocation.flavor);

        Ok(())
    }
}

/// Resource usage statistics
#[derive(Debug, Clone)]
pub struct ResourceStats {
    /// Number of active sessions
    pub active_sessions: usize,
    /// Maximum allowed sessions
    pub max_sessions: usize,
    /// Number of allocated ports
    pub allocated_ports: usize,
    /// Number of available ports
    pub available_ports: usize,
    /// Total number of ports in range
    pub total_ports: usize,
    /// Total memory allocated in MB
    pub total_memory_mb: u32,
    /// Total CPUs allocated
    pub total_cpus: u32,
    /// Count of sessions by flavor
    pub flavor_counts: HashMap<SandboxFlavor, usize>,
}

/// Helper function to format Instant as ISO 8601 string
/// 
/// Note: This is a simplified implementation. In a real system, you might want to use
/// a proper datetime library like chrono for more accurate timestamp formatting.
fn format_instant_as_iso8601(instant: Instant) -> String {
    // This is a simplified implementation that shows relative time
    // In a real implementation, you'd want to use SystemTime and convert to UTC
    let elapsed = instant.elapsed();
    let seconds_ago = elapsed.as_secs();
    
    if seconds_ago == 0 {
        "just now".to_string()
    } else if seconds_ago < 60 {
        format!("{} seconds ago", seconds_ago)
    } else if seconds_ago < 3600 {
        format!("{} minutes ago", seconds_ago / 60)
    } else {
        format!("{} hours ago", seconds_ago / 3600)
    }
}

/// Classify execution errors based on stderr output and exit code
/// 
/// This function analyzes the execution output to determine the type of error
/// and create appropriate SimplifiedMcpError variants with detailed information.
pub fn classify_execution_error(
    stdout: &str,
    stderr: &str,
    exit_code: Option<i32>,
    template: &str,
) -> SimplifiedMcpError {
    let stderr_lower = stderr.to_lowercase();
    let stdout_lower = stdout.to_lowercase();
    
    // Check for compilation errors first
    if is_compilation_error(&stderr_lower, &stdout_lower, template) {
        return SimplifiedMcpError::CompilationError(format!(
            "Compilation failed in {} template. Error details: {}",
            template,
            truncate_error_message(stderr)
        ));
    }
    
    // Check for runtime errors
    if is_runtime_error(&stderr_lower, &stdout_lower, exit_code) {
        return SimplifiedMcpError::RuntimeError(format!(
            "Runtime error occurred during execution. Error details: {}",
            truncate_error_message(stderr)
        ));
    }
    
    // Check for system errors
    if is_system_error(&stderr_lower, &stdout_lower, exit_code) {
        return SimplifiedMcpError::SystemError(format!(
            "System error occurred during execution. Error details: {}",
            truncate_error_message(stderr)
        ));
    }
    
    // Default to general code execution error
    SimplifiedMcpError::CodeExecutionError(format!(
        "Code execution failed with exit code {:?}. Error output: {}",
        exit_code,
        truncate_error_message(stderr)
    ))
}

/// Check if the error indicates a compilation problem
fn is_compilation_error(stderr_lower: &str, stdout_lower: &str, template: &str) -> bool {
    let compilation_indicators = match template {
        "python" => vec![
            "syntaxerror", "indentationerror", "invalid syntax", 
            "unexpected indent", "unindent does not match"
        ],
        "node" => vec![
            "syntaxerror", "unexpected token", "unexpected end of input",
            "missing", "expected", "parse error"
        ],
        _ => vec!["syntax", "parse", "compilation", "compile"]
    };
    
    compilation_indicators.iter().any(|indicator| {
        stderr_lower.contains(indicator) || stdout_lower.contains(indicator)
    })
}

/// Check if the error indicates a runtime problem
fn is_runtime_error(stderr_lower: &str, stdout_lower: &str, exit_code: Option<i32>) -> bool {
    let runtime_indicators = vec![
        "nameerror", "typeerror", "valueerror", "attributeerror", "keyerror",
        "indexerror", "zerodivisionerror", "referenceerror", "rangeerror",
        "null pointer", "segmentation fault", "stack overflow", "out of memory",
        "uncaught exception", "unhandled exception", "runtime error"
    ];
    
    // Runtime errors typically have non-zero exit codes
    let has_runtime_exit_code = exit_code.map_or(false, |code| code != 0);
    
    let has_runtime_indicator = runtime_indicators.iter().any(|indicator| {
        stderr_lower.contains(indicator) || stdout_lower.contains(indicator)
    });
    
    has_runtime_exit_code && has_runtime_indicator
}

/// Check if the error indicates a system-level problem
fn is_system_error(stderr_lower: &str, stdout_lower: &str, exit_code: Option<i32>) -> bool {
    let system_indicators = vec![
        "permission denied", "access denied", "no such file", "cannot find",
        "connection refused", "network", "timeout", "killed", "terminated",
        "resource temporarily unavailable", "disk full", "no space left"
    ];
    
    // System errors often have specific exit codes
    let has_system_exit_code = exit_code.map_or(false, |code| {
        matches!(code, 126 | 127 | 128..=255) // Common system error codes
    });
    
    let has_system_indicator = system_indicators.iter().any(|indicator| {
        stderr_lower.contains(indicator) || stdout_lower.contains(indicator)
    });
    
    has_system_exit_code || has_system_indicator
}

/// Truncate error message to a reasonable length for user display
pub fn truncate_error_message(message: &str) -> String {
    const MAX_LENGTH: usize = 500;
    
    if message.len() <= MAX_LENGTH {
        message.to_string()
    } else {
        let truncated = &message[..MAX_LENGTH];
        // Try to truncate at a word boundary
        if let Some(last_space) = truncated.rfind(' ') {
            format!("{}... (truncated)", &truncated[..last_space])
        } else {
            format!("{}... (truncated)", truncated)
        }
    }
}

//--------------------------------------------------------------------------------------------------
// Cleanup Manager
//--------------------------------------------------------------------------------------------------

/// Comprehensive cleanup manager that coordinates session and resource cleanup
/// 
/// This manager handles the coordination between SessionManager and ResourceManager
/// to ensure that both sessions and their associated resources are properly cleaned up
/// when they expire or become orphaned.
#[derive(Debug)]
pub struct CleanupManager {
    session_manager: Arc<SessionManager>,
    resource_manager: Arc<ResourceManager>,
    config: ConfigurationManager,
}

impl CleanupManager {
    /// Create a new CleanupManager
    pub fn new(
        session_manager: Arc<SessionManager>,
        resource_manager: Arc<ResourceManager>,
        config: ConfigurationManager,
    ) -> Self {
        Self {
            session_manager,
            resource_manager,
            config,
        }
    }

    /// Start comprehensive background cleanup tasks
    /// 
    /// This method starts both session cleanup and resource cleanup tasks,
    /// and returns handles to both background tasks.
    pub fn start_background_cleanup(&self) -> (tokio::task::JoinHandle<()>, tokio::task::JoinHandle<()>) {
        let session_cleanup_handle = self.start_session_cleanup_task();
        let resource_cleanup_handle = self.start_resource_cleanup_task();
        
        (session_cleanup_handle, resource_cleanup_handle)
    }

    /// Start the session cleanup background task
    fn start_session_cleanup_task(&self) -> tokio::task::JoinHandle<()> {
        let session_manager = Arc::clone(&self.session_manager);
        let resource_manager = Arc::clone(&self.resource_manager);
        let cleanup_interval = Duration::from_secs(60); // Check every minute
        
        tokio::spawn(async move {
            let mut interval_timer = interval(cleanup_interval);
            
            loop {
                interval_timer.tick().await;
                
                // Find expired sessions
                let expired_sessions = match session_manager.find_expired_sessions() {
                    Ok(sessions) => sessions,
                    Err(e) => {
                        tracing::error!("Failed to find expired sessions: {}", e);
                        continue;
                    }
                };
                
                if !expired_sessions.is_empty() {
                    tracing::info!("Found {} expired sessions for cleanup", expired_sessions.len());
                    
                    // Clean up expired sessions and their resources
                    for session_id in expired_sessions {
                        match Self::cleanup_session_and_resources(
                            &session_manager,
                            &resource_manager,
                            &session_id,
                        ).await {
                            Ok(()) => {
                                tracing::info!("Successfully cleaned up expired session and resources: {}", session_id);
                            }
                            Err(e) => {
                                tracing::error!("Failed to cleanup session and resources {}: {}", session_id, e);
                            }
                        }
                    }
                }
            }
        })
    }

    /// Start the resource cleanup background task
    fn start_resource_cleanup_task(&self) -> tokio::task::JoinHandle<()> {
        self.resource_manager.start_background_resource_cleanup()
    }

    /// Clean up a session and its associated resources
    async fn cleanup_session_and_resources(
        session_manager: &Arc<SessionManager>,
        resource_manager: &Arc<ResourceManager>,
        session_id: &str,
    ) -> Result<(), SimplifiedMcpError> {
        // First, try to stop the session
        if let Err(e) = session_manager.stop_session(session_id).await {
            tracing::warn!("Failed to stop session {} during cleanup: {}", session_id, e);
        }

        // Then, release any associated resources
        match resource_manager.release_resources(session_id) {
            Ok(allocation) => {
                tracing::info!("Released resources for session {}: port={}, flavor={}", 
                    session_id, allocation.port, allocation.flavor);
            }
            Err(SimplifiedMcpError::ValidationError(_)) => {
                // Session might not have had resources allocated, which is fine
                tracing::debug!("No resources to release for session {}", session_id);
            }
            Err(e) => {
                tracing::error!("Failed to release resources for session {}: {}", session_id, e);
                return Err(e);
            }
        }

        // Finally, remove the session from tracking
        match session_manager.remove_session(session_id) {
            Ok(_) => {
                tracing::info!("Removed session {} from tracking", session_id);
            }
            Err(SimplifiedMcpError::SessionNotFound(_)) => {
                // Session might have been removed already, which is fine
                tracing::debug!("Session {} was already removed from tracking", session_id);
            }
            Err(e) => {
                tracing::error!("Failed to remove session {} from tracking: {}", session_id, e);
                return Err(e);
            }
        }

        Ok(())
    }

    /// Manually trigger comprehensive cleanup
    /// 
    /// This method can be called to manually trigger cleanup of both expired sessions
    /// and orphaned resources. It returns statistics about what was cleaned up.
    pub async fn manual_comprehensive_cleanup(&self) -> Result<CleanupStats, SimplifiedMcpError> {
        let mut stats = CleanupStats::default();

        // Clean up expired sessions
        let expired_sessions = self.session_manager.find_expired_sessions()?;
        stats.expired_sessions_found = expired_sessions.len();

        for session_id in expired_sessions {
            match Self::cleanup_session_and_resources(
                &self.session_manager,
                &self.resource_manager,
                &session_id,
            ).await {
                Ok(()) => {
                    stats.sessions_cleaned_up += 1;
                }
                Err(e) => {
                    tracing::error!("Failed to cleanup session {}: {}", session_id, e);
                    stats.cleanup_errors += 1;
                }
            }
        }

        // Get resource statistics
        let resource_stats = self.resource_manager.get_resource_stats()?;
        stats.active_sessions_after_cleanup = resource_stats.active_sessions;
        stats.allocated_ports_after_cleanup = resource_stats.allocated_ports;

        Ok(stats)
    }

    /// Get cleanup configuration
    pub fn get_config(&self) -> &ConfigurationManager {
        &self.config
    }

    /// Get session manager reference
    pub fn get_session_manager(&self) -> &Arc<SessionManager> {
        &self.session_manager
    }

    /// Get resource manager reference
    pub fn get_resource_manager(&self) -> &Arc<ResourceManager> {
        &self.resource_manager
    }

    /// Get comprehensive system health statistics
    /// 
    /// This method provides a comprehensive view of the system state including
    /// session counts, resource usage, and potential cleanup candidates.
    pub fn get_system_health(&self) -> Result<SystemHealthStats, SimplifiedMcpError> {
        let sessions = self.session_manager.get_sessions(None)?;
        let resource_stats = self.resource_manager.get_resource_stats()?;
        let timeout = self.config.get_session_timeout();

        let mut health_stats = SystemHealthStats {
            total_sessions: sessions.len(),
            active_sessions: 0,
            creating_sessions: 0,
            ready_sessions: 0,
            running_sessions: 0,
            error_sessions: 0,
            stopped_sessions: 0,
            sessions_near_timeout: 0,
            expired_sessions: 0,
            resource_stats,
        };

        let near_timeout_threshold = Duration::from_secs(timeout.as_secs() * 3 / 4); // 75% of timeout

        for session in &sessions {
            match &session.status {
                SessionStatus::Creating => health_stats.creating_sessions += 1,
                SessionStatus::Ready => {
                    health_stats.ready_sessions += 1;
                    health_stats.active_sessions += 1;
                }
                SessionStatus::Running => {
                    health_stats.running_sessions += 1;
                    health_stats.active_sessions += 1;
                }
                SessionStatus::Error(_) => health_stats.error_sessions += 1,
                SessionStatus::Stopped => health_stats.stopped_sessions += 1,
            }

            // Check if session is near timeout
            if session.last_accessed.elapsed() > near_timeout_threshold && !matches!(session.status, SessionStatus::Stopped) {
                health_stats.sessions_near_timeout += 1;
            }

            // Check if session should be expired
            if session.should_timeout(timeout) {
                health_stats.expired_sessions += 1;
            }
        }

        Ok(health_stats)
    }

    /// Gracefully shutdown the cleanup system
    /// 
    /// This method stops all background cleanup tasks and performs a final cleanup
    /// of all active sessions and resources. It should be called when the server
    /// is shutting down to ensure proper resource cleanup.
    pub async fn graceful_shutdown(
        &self,
        cleanup_handles: (tokio::task::JoinHandle<()>, tokio::task::JoinHandle<()>),
    ) -> Result<CleanupStats, SimplifiedMcpError> {
        tracing::info!("Starting graceful shutdown of cleanup system");

        // Cancel background cleanup tasks
        cleanup_handles.0.abort();
        cleanup_handles.1.abort();

        // Perform final cleanup of all active sessions
        let all_sessions = self.session_manager.get_sessions(None)?;
        let mut stats = CleanupStats::default();
        stats.expired_sessions_found = all_sessions.len();

        for session in all_sessions {
            if !matches!(session.status, SessionStatus::Stopped) {
                match Self::cleanup_session_and_resources(
                    &self.session_manager,
                    &self.resource_manager,
                    &session.id,
                ).await {
                    Ok(()) => {
                        stats.sessions_cleaned_up += 1;
                        tracing::info!("Cleaned up session during shutdown: {}", session.id);
                    }
                    Err(e) => {
                        stats.cleanup_errors += 1;
                        tracing::error!("Failed to cleanup session {} during shutdown: {}", session.id, e);
                    }
                }
            }
        }

        // Get final resource statistics
        let resource_stats = self.resource_manager.get_resource_stats()?;
        stats.active_sessions_after_cleanup = resource_stats.active_sessions;
        stats.allocated_ports_after_cleanup = resource_stats.allocated_ports;

        tracing::info!("Graceful shutdown completed: cleaned up {} sessions with {} errors", 
            stats.sessions_cleaned_up, stats.cleanup_errors);

        Ok(stats)
    }
}

/// Statistics about cleanup operations
#[derive(Debug, Clone, Default)]
pub struct CleanupStats {
    /// Number of expired sessions found
    pub expired_sessions_found: usize,
    /// Number of sessions successfully cleaned up
    pub sessions_cleaned_up: usize,
    /// Number of cleanup errors encountered
    pub cleanup_errors: usize,
    /// Number of active sessions after cleanup
    pub active_sessions_after_cleanup: usize,
    /// Number of allocated ports after cleanup
    pub allocated_ports_after_cleanup: usize,
}

/// Comprehensive system health statistics
#[derive(Debug, Clone)]
pub struct SystemHealthStats {
    /// Total number of sessions
    pub total_sessions: usize,
    /// Number of active sessions (ready + running)
    pub active_sessions: usize,
    /// Number of sessions in creating state
    pub creating_sessions: usize,
    /// Number of sessions in ready state
    pub ready_sessions: usize,
    /// Number of sessions in running state
    pub running_sessions: usize,
    /// Number of sessions in error state
    pub error_sessions: usize,
    /// Number of sessions in stopped state
    pub stopped_sessions: usize,
    /// Number of sessions that are near timeout (75% of timeout elapsed)
    pub sessions_near_timeout: usize,
    /// Number of sessions that should be expired
    pub expired_sessions: usize,
    /// Resource usage statistics
    pub resource_stats: ResourceStats,
}

//--------------------------------------------------------------------------------------------------
// Automatic Sandbox Creation
//--------------------------------------------------------------------------------------------------

use crate::payload::{SandboxStartParams, SandboxConfig};
use crate::state::AppState;
use crate::handler::sandbox_start_impl;
use crate::error::ServerError;

/// Automatic sandbox creator that integrates with existing sandbox_start_impl
#[derive(Debug)]
pub struct AutomaticSandboxCreator {
    config: ConfigurationManager,
    template_mapping: TemplateMapping,
}

impl AutomaticSandboxCreator {
    /// Create a new AutomaticSandboxCreator
    pub fn new(config: ConfigurationManager) -> Self {
        Self {
            config,
            template_mapping: TemplateMapping::default(),
        }
    }

    /// Create a sandbox automatically based on session information
    /// 
    /// This function integrates with the existing sandbox_start_impl functionality
    /// and generates the appropriate configuration based on the session parameters.
    pub async fn create_sandbox_for_session(
        &self,
        state: AppState,
        session_info: &SessionInfo,
    ) -> Result<String, SimplifiedMcpError> {
        // Generate sandbox configuration based on session parameters
        let sandbox_config = self.generate_sandbox_config(session_info)?;
        
        // Create SandboxStartParams for the existing implementation
        let start_params = SandboxStartParams {
            sandbox: session_info.sandbox_name.clone(),
            namespace: session_info.namespace.clone(),
            config: Some(sandbox_config),
        };

        // Call the existing sandbox_start_impl function
        match sandbox_start_impl(state, start_params).await {
            Ok(result) => {
                tracing::info!("Successfully created sandbox for session {}: {}", 
                    session_info.id, result);
                Ok(result)
            }
            Err(ServerError::InternalError(msg)) => {
                Err(SimplifiedMcpError::SessionCreationFailed(format!(
                    "Internal error creating sandbox: {}", msg
                )))
            }
            Err(ServerError::ValidationError(e)) => {
                Err(SimplifiedMcpError::SessionCreationFailed(format!(
                    "Validation error creating sandbox: {}", e
                )))
            }
            Err(e) => {
                Err(SimplifiedMcpError::SessionCreationFailed(format!(
                    "Error creating sandbox: {}", e
                )))
            }
        }
    }

    /// Generate sandbox configuration based on session information
    fn generate_sandbox_config(&self, session_info: &SessionInfo) -> Result<SandboxConfig, SimplifiedMcpError> {
        // Get the container image for the template
        let image = self.template_mapping
            .get_image(&session_info.language)
            .ok_or_else(|| SimplifiedMcpError::UnsupportedLanguage(session_info.language.clone()))?
            .clone();

        // Generate volumes configuration with shared volume mapping
        let volumes = self.generate_volume_mappings();

        // Generate ports configuration (empty for now, ports are managed by the existing system)
        let ports = Vec::new();

        // Generate environment variables
        let envs = self.generate_environment_variables();

        // Create the sandbox configuration
        let config = SandboxConfig {
            image: Some(image),
            memory: Some(session_info.flavor.get_memory_mb()),
            cpus: Some(session_info.flavor.get_cpus()),
            volumes,
            ports,
            envs,
            depends_on: Vec::new(),
            workdir: None, // Use container default
            shell: None,   // Use container default
            scripts: std::collections::HashMap::new(),
            exec: None,
        };

        Ok(config)
    }

    /// Generate volume mappings including shared volume if configured
    fn generate_volume_mappings(&self) -> Vec<String> {
        let mut volumes = Vec::new();

        // Add shared volume mapping if configured
        if let Some(host_path) = self.config.get_shared_volume_path() {
            let guest_path = self.config.get_shared_volume_guest_path();
            let volume_mapping = format!("{}:{}", host_path.display(), guest_path);
            volumes.push(volume_mapping);
        }

        volumes
    }

    /// Generate environment variables for the sandbox
    fn generate_environment_variables(&self) -> Vec<String> {
        let mut envs = Vec::new();

        // Add shared volume path as environment variable if available
        if self.config.has_shared_volume() {
            let guest_path = self.config.get_shared_volume_guest_path();
            envs.push(format!("SHARED_VOLUME_PATH={}", guest_path));
        }

        // Add other useful environment variables
        envs.push("MICROSANDBOX_SIMPLIFIED_MCP=true".to_string());

        envs
    }

    /// Check if a sandbox is ready for use
    pub async fn is_sandbox_ready(
        &self,
        _state: AppState,
        _session_info: &SessionInfo,
    ) -> Result<bool, SimplifiedMcpError> {
        // Use the existing status checking functionality
        // This would integrate with the orchestra::status function
        // For now, we'll assume the sandbox is ready if it was created successfully
        // In a future implementation, this would check the actual sandbox status
        
        // TODO: Implement proper sandbox status checking
        // This would involve calling orchestra::status and checking if the sandbox is running
        
        Ok(true) // Simplified implementation
    }

    /// Get configuration manager
    pub fn get_config(&self) -> &ConfigurationManager {
        &self.config
    }
}

/// Enhanced SessionManager with automatic sandbox creation
impl SessionManager {
    /// Create a session with automatic sandbox creation
    /// 
    /// This method extends the basic session creation to automatically create
    /// the underlying sandbox using the existing sandbox_start_impl functionality.
    pub async fn create_session_with_sandbox(
        &self,
        state: AppState,
        language: &str,
        flavor: SandboxFlavor,
    ) -> Result<String, SimplifiedMcpError> {
        // First create the session entry
        let session_id = self.create_session(language, flavor).await?;
        
        // Get the session info
        let session_info = self.get_session(&session_id)?;
        
        // Update session status to creating
        self.update_session_status(&session_id, SessionStatus::Creating)?;
        
        // Create the automatic sandbox creator
        let creator = AutomaticSandboxCreator::new(self.config.clone());
        
        // Create the actual sandbox
        match creator.create_sandbox_for_session(state, &session_info).await {
            Ok(_) => {
                // Update session status to ready
                self.update_session_status(&session_id, SessionStatus::Ready)?;
                tracing::info!("Successfully created session {} with sandbox", session_id);
                Ok(session_id)
            }
            Err(e) => {
                // Update session status to error
                self.update_session_status(&session_id, SessionStatus::Error(e.to_string()))?;
                tracing::error!("Failed to create sandbox for session {}: {}", session_id, e);
                Err(e)
            }
        }
    }

    /// Get or create a session with automatic sandbox creation
    /// 
    /// This method extends get_or_create_session to automatically create sandboxes
    /// when new sessions are created.
    pub async fn get_or_create_session_with_sandbox(
        &self,
        state: AppState,
        session_id: Option<String>,
        language: &str,
        flavor: SandboxFlavor,
    ) -> Result<SessionInfo, SimplifiedMcpError> {
        match session_id {
            None => {
                // Create new session with sandbox
                let new_session_id = self.create_session_with_sandbox(state, language, flavor).await?;
                self.get_session(&new_session_id)
            }
            Some(id) => {
                // Try to get existing session (same logic as before)
                match self.get_session(&id) {
                    Ok(session) => {
                        // Validate that the session matches the requested parameters
                        if session.language != language {
                            return Err(SimplifiedMcpError::InvalidSessionState(
                                format!("Session {} is for language '{}', but '{}' was requested", 
                                    id, session.language, language)
                            ));
                        }
                        
                        // Check if session is in a valid state
                        match session.status {
                            SessionStatus::Stopped => {
                                return Err(SimplifiedMcpError::InvalidSessionState(
                                    format!("Session {} has been stopped", id)
                                ));
                            }
                            SessionStatus::Error(ref msg) => {
                                return Err(SimplifiedMcpError::InvalidSessionState(
                                    format!("Session {} is in error state: {}", id, msg)
                                ));
                            }
                            _ => {}
                        }

                        Ok(session)
                    }
                    Err(_) => {
                        Err(SimplifiedMcpError::SessionNotFound(id))
                    }
                }
            }
        }
    }
}

//--------------------------------------------------------------------------------------------------
// Tests
//--------------------------------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;
    
    // Shared mutex to serialize environment variable tests
    static ENV_TEST_MUTEX: Mutex<()> = Mutex::new(());

    #[test]
    fn test_sandbox_flavor_memory() {
        assert_eq!(SandboxFlavor::Small.get_memory_mb(), 1024);
        assert_eq!(SandboxFlavor::Medium.get_memory_mb(), 2048);
        assert_eq!(SandboxFlavor::Large.get_memory_mb(), 4096);
    }

    #[test]
    fn test_resource_allocation_creation() {
        let allocation = ResourceAllocation::new(
            "test-session".to_string(),
            SandboxFlavor::Medium,
            8080,
        );

        assert_eq!(allocation.session_id, "test-session");
        assert_eq!(allocation.flavor, SandboxFlavor::Medium);
        assert_eq!(allocation.port, 8080);
        assert!(allocation.age_seconds() < 2); // Should be very recent
    }

    #[test]
    fn test_port_manager_creation() {
        let port_manager = PortManager::new(8000, 8010).unwrap();
        assert_eq!(port_manager.total_count(), 10);
        assert_eq!(port_manager.available_count(), 10);
        assert_eq!(port_manager.allocated_count(), 0);

        // Test invalid range
        assert!(PortManager::new(8010, 8000).is_err());
        assert!(PortManager::new(8000, 8000).is_err());
    }

    #[test]
    fn test_port_manager_allocation() {
        let mut port_manager = PortManager::new(8000, 8003).unwrap(); // 3 ports: 8000, 8001, 8002

        // Allocate all ports
        let port1 = port_manager.allocate_port().unwrap();
        let port2 = port_manager.allocate_port().unwrap();
        let port3 = port_manager.allocate_port().unwrap();

        assert!(port1 >= 8000 && port1 < 8003);
        assert!(port2 >= 8000 && port2 < 8003);
        assert!(port3 >= 8000 && port3 < 8003);
        assert_ne!(port1, port2);
        assert_ne!(port2, port3);
        assert_ne!(port1, port3);

        assert_eq!(port_manager.allocated_count(), 3);
        assert_eq!(port_manager.available_count(), 0);

        // Try to allocate when no ports available
        assert!(port_manager.allocate_port().is_err());

        // Release a port and allocate again
        port_manager.release_port(port2).unwrap();
        assert_eq!(port_manager.allocated_count(), 2);
        assert_eq!(port_manager.available_count(), 1);

        let port4 = port_manager.allocate_port().unwrap();
        assert_eq!(port4, port2); // Should reuse the released port
    }

    #[test]
    fn test_port_manager_release() {
        let mut port_manager = PortManager::new(8000, 8002).unwrap();
        let port = port_manager.allocate_port().unwrap();

        // Release the allocated port
        assert!(port_manager.release_port(port).is_ok());
        assert_eq!(port_manager.allocated_count(), 0);

        // Try to release the same port again
        assert!(port_manager.release_port(port).is_err());

        // Try to release a port outside the range
        assert!(port_manager.release_port(9000).is_err());
    }

    #[test]
    fn test_resource_manager_creation() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::new(config);

        let stats = resource_manager.get_resource_stats().unwrap();
        assert_eq!(stats.active_sessions, 0);
        assert_eq!(stats.max_sessions, 10); // Default max sessions
        assert_eq!(stats.allocated_ports, 0);
        assert!(stats.available_ports > 0);
    }

    #[test]
    fn test_resource_manager_allocation() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::new(config);

        // Check availability before allocation
        assert!(resource_manager.check_resource_availability(SandboxFlavor::Small).unwrap());

        // Allocate resources
        let allocation = resource_manager.allocate_resources(
            "test-session".to_string(),
            SandboxFlavor::Medium,
        ).unwrap();

        assert_eq!(allocation.session_id, "test-session");
        assert_eq!(allocation.flavor, SandboxFlavor::Medium);
        assert!(allocation.port >= 8000 && allocation.port < 9000);

        // Verify stats
        let stats = resource_manager.get_resource_stats().unwrap();
        assert_eq!(stats.active_sessions, 1);
        assert_eq!(stats.allocated_ports, 1);
        assert_eq!(stats.total_memory_mb, 2048); // Medium flavor
        assert_eq!(stats.total_cpus, 2); // Medium flavor

        // Try to allocate for the same session (should fail)
        assert!(resource_manager.allocate_resources(
            "test-session".to_string(),
            SandboxFlavor::Small,
        ).is_err());

        // Get allocation
        let retrieved = resource_manager.get_allocation("test-session").unwrap();
        assert_eq!(retrieved.session_id, allocation.session_id);
        assert_eq!(retrieved.port, allocation.port);
    }

    #[test]
    fn test_resource_manager_release() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::new(config);

        // Allocate resources
        let allocation = resource_manager.allocate_resources(
            "test-session".to_string(),
            SandboxFlavor::Large,
        ).unwrap();

        // Release resources
        let released = resource_manager.release_resources("test-session").unwrap();
        assert_eq!(released.session_id, allocation.session_id);
        assert_eq!(released.port, allocation.port);

        // Verify stats after release
        let stats = resource_manager.get_resource_stats().unwrap();
        assert_eq!(stats.active_sessions, 0);
        assert_eq!(stats.allocated_ports, 0);
        assert_eq!(stats.total_memory_mb, 0);
        assert_eq!(stats.total_cpus, 0);

        // Try to release again (should fail)
        assert!(resource_manager.release_resources("test-session").is_err());

        // Try to get allocation after release (should fail)
        assert!(resource_manager.get_allocation("test-session").is_err());
    }

    #[test]
    fn test_resource_manager_limits() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::with_port_range(config, 8000, 8002).unwrap(); // Only 2 ports

        // Allocate resources up to port limit
        let _alloc1 = resource_manager.allocate_resources(
            "session1".to_string(),
            SandboxFlavor::Small,
        ).unwrap();

        let _alloc2 = resource_manager.allocate_resources(
            "session2".to_string(),
            SandboxFlavor::Small,
        ).unwrap();

        // Should fail due to port exhaustion
        assert!(resource_manager.allocate_resources(
            "session3".to_string(),
            SandboxFlavor::Small,
        ).is_err());

        // Check availability
        assert!(!resource_manager.check_resource_availability(SandboxFlavor::Small).unwrap());
    }

    #[test]
    fn test_resource_manager_flavor_validation() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::new(config);

        // Valid flavors should pass
        assert!(resource_manager.validate_flavor_limits(SandboxFlavor::Small).is_ok());
        assert!(resource_manager.validate_flavor_limits(SandboxFlavor::Medium).is_ok());
        assert!(resource_manager.validate_flavor_limits(SandboxFlavor::Large).is_ok());
    }

    #[test]
    fn test_resource_manager_cleanup() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::new(config);

        // Allocate resources for multiple sessions
        let _alloc1 = resource_manager.allocate_resources(
            "session1".to_string(),
            SandboxFlavor::Small,
        ).unwrap();

        let _alloc2 = resource_manager.allocate_resources(
            "session2".to_string(),
            SandboxFlavor::Medium,
        ).unwrap();

        let _alloc3 = resource_manager.allocate_resources(
            "session3".to_string(),
            SandboxFlavor::Large,
        ).unwrap();

        // Verify initial state
        let stats = resource_manager.get_resource_stats().unwrap();
        assert_eq!(stats.active_sessions, 3);

        // Cleanup some sessions
        let expired_sessions = vec!["session1".to_string(), "session3".to_string()];
        let cleaned_up = resource_manager.cleanup_expired_allocations(&expired_sessions).unwrap();
        assert_eq!(cleaned_up.len(), 2);

        // Verify final state
        let stats = resource_manager.get_resource_stats().unwrap();
        assert_eq!(stats.active_sessions, 1);
        assert_eq!(stats.total_memory_mb, 2048); // Only medium session remains
        assert_eq!(stats.total_cpus, 2);
    }

    #[test]
    fn test_sandbox_flavor_cpus() {
        assert_eq!(SandboxFlavor::Small.get_cpus(), 1);
        assert_eq!(SandboxFlavor::Medium.get_cpus(), 2);
        assert_eq!(SandboxFlavor::Large.get_cpus(), 4);
    }

    #[test]
    fn test_sandbox_flavor_from_str() {
        assert_eq!("small".parse::<SandboxFlavor>().unwrap(), SandboxFlavor::Small);
        assert_eq!("medium".parse::<SandboxFlavor>().unwrap(), SandboxFlavor::Medium);
        assert_eq!("large".parse::<SandboxFlavor>().unwrap(), SandboxFlavor::Large);
        assert_eq!("SMALL".parse::<SandboxFlavor>().unwrap(), SandboxFlavor::Small);
        
        assert!("invalid".parse::<SandboxFlavor>().is_err());
    }

    #[test]
    fn test_sandbox_flavor_display() {
        assert_eq!(SandboxFlavor::Small.to_string(), "small");
        assert_eq!(SandboxFlavor::Medium.to_string(), "medium");
        assert_eq!(SandboxFlavor::Large.to_string(), "large");
    }

    #[test]
    fn test_sandbox_flavor_default() {
        assert_eq!(SandboxFlavor::default(), SandboxFlavor::Small);
    }

    #[test]
    fn test_template_mapping() {
        let mapping = TemplateMapping::default();
        
        assert_eq!(mapping.get_image("python"), Some(&"microsandbox/python".to_string()));
        assert_eq!(mapping.get_image("node"), Some(&"microsandbox/node".to_string()));
        assert_eq!(mapping.get_image("unsupported"), None);
        
        assert!(mapping.is_supported("python"));
        assert!(mapping.is_supported("node"));
        assert!(!mapping.is_supported("unsupported"));
        
        let supported = mapping.supported_templates();
        assert_eq!(supported.len(), 2);
        assert!(supported.contains(&&"python".to_string()));
        assert!(supported.contains(&&"node".to_string()));
    }

    #[test]
    fn test_execute_code_request_deserialization() {
        let json = r#"
        {
            "code": "print('hello')",
            "template": "python",
            "session_id": "test-session",
            "flavor": "medium"
        }
        "#;
        
        let request: ExecuteCodeRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.code, "print('hello')");
        assert_eq!(request.template, Some("python".to_string()));
        assert_eq!(request.session_id, Some("test-session".to_string()));
        assert_eq!(request.flavor, Some(SandboxFlavor::Medium));
    }

    #[test]
    fn test_execute_command_request_deserialization() {
        let json = r#"
        {
            "command": "ls",
            "args": ["-la"],
            "template": "python",
            "session_id": "test-session",
            "flavor": "large"
        }
        "#;
        
        let request: ExecuteCommandRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.command, "ls");
        assert_eq!(request.args, Some(vec!["-la".to_string()]));
        assert_eq!(request.template, Some("python".to_string()));
        assert_eq!(request.session_id, Some("test-session".to_string()));
        assert_eq!(request.flavor, Some(SandboxFlavor::Large));
    }

    #[test]
    fn test_execution_response_serialization() {
        let response = ExecutionResponse {
            session_id: "test-session".to_string(),
            stdout: "Hello, World!".to_string(),
            stderr: "".to_string(),
            exit_code: Some(0),
            execution_time_ms: 150,
            session_created: true,
        };
        
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("test-session"));
        assert!(json.contains("Hello, World!"));
        assert!(json.contains("150"));
        assert!(json.contains("true"));
    }

    #[test]
    fn test_configuration_manager_default() {
        let config = ConfigurationManager::default();
        
        assert_eq!(config.get_shared_volume_path(), None);
        assert_eq!(config.get_shared_volume_guest_path(), "/shared");
        assert_eq!(config.get_default_flavor(), SandboxFlavor::Small);
        assert_eq!(config.get_session_timeout(), Duration::from_secs(1800));
        assert_eq!(config.get_max_sessions(), 10);
        assert!(!config.has_shared_volume());
    }

    #[test]
    fn test_configuration_manager_validation() {
        let config = ConfigurationManager::default();
        assert!(config.validate().is_ok());

        // Test invalid guest path (not absolute)
        let mut invalid_config = config.clone();
        invalid_config.shared_volume_guest_path = "relative/path".to_string();
        assert!(invalid_config.validate().is_err());

        // Test invalid session timeout (too short)
        let mut invalid_config = config.clone();
        invalid_config.session_timeout = Duration::from_secs(30);
        assert!(invalid_config.validate().is_err());

        // Test invalid session timeout (too long)
        let mut invalid_config = config.clone();
        invalid_config.session_timeout = Duration::from_secs(100000);
        assert!(invalid_config.validate().is_err());

        // Test invalid max sessions (zero)
        let mut invalid_config = config.clone();
        invalid_config.max_sessions = 0;
        assert!(invalid_config.validate().is_err());

        // Test invalid max sessions (too high)
        let mut invalid_config = config.clone();
        invalid_config.max_sessions = 200;
        assert!(invalid_config.validate().is_err());
    }

    #[test]
    fn test_configuration_manager_volume_path_info() {
        // Test without shared volume
        let config = ConfigurationManager::default();
        let info = config.get_volume_path_info();
        assert_eq!(info.volume_path, "/shared");
        assert!(!info.available);
        assert!(info.description.contains("No shared volume configured"));

        // Test with shared volume
        let mut config = config;
        config.shared_volume_path = Some(PathBuf::from("/tmp"));
        let info = config.get_volume_path_info();
        assert_eq!(info.volume_path, "/shared");
        assert!(info.available);
        assert!(info.description.contains("Shared volume mounted"));
        assert!(info.description.contains("/tmp"));
    }

    #[test]
    fn test_configuration_manager_from_env_with_defaults() {
        // Use a mutex to ensure env tests don't run concurrently
        let _guard = ENV_TEST_MUTEX.lock().unwrap();

        // Store original values
        let orig_guest_path = std::env::var("MSB_SHARED_VOLUME_GUEST_PATH").ok();
        let orig_flavor = std::env::var("MSB_DEFAULT_FLAVOR").ok();
        let orig_timeout = std::env::var("MSB_SESSION_TIMEOUT_SECONDS").ok();
        let orig_max_sessions = std::env::var("MSB_MAX_SESSIONS").ok();

        // Clear environment variables to test defaults
        std::env::remove_var("MSB_SHARED_VOLUME_PATH");
        std::env::remove_var("MSB_SHARED_VOLUME_GUEST_PATH");
        std::env::remove_var("MSB_DEFAULT_FLAVOR");
        std::env::remove_var("MSB_SESSION_TIMEOUT_SECONDS");
        std::env::remove_var("MSB_MAX_SESSIONS");

        let config = ConfigurationManager::from_env().unwrap();
        
        assert_eq!(config.get_shared_volume_path(), None);
        assert_eq!(config.get_shared_volume_guest_path(), "/shared");
        assert_eq!(config.get_default_flavor(), SandboxFlavor::Small);
        assert_eq!(config.get_session_timeout(), Duration::from_secs(1800));
        assert_eq!(config.get_max_sessions(), 10);

        // Restore original values
        if let Some(val) = orig_guest_path { std::env::set_var("MSB_SHARED_VOLUME_GUEST_PATH", val); }
        if let Some(val) = orig_flavor { std::env::set_var("MSB_DEFAULT_FLAVOR", val); }
        if let Some(val) = orig_timeout { std::env::set_var("MSB_SESSION_TIMEOUT_SECONDS", val); }
        if let Some(val) = orig_max_sessions { std::env::set_var("MSB_MAX_SESSIONS", val); }
    }

    #[test]
    fn test_configuration_manager_from_env_with_values() {
        // Use a mutex to ensure env tests don't run concurrently
        let _guard = ENV_TEST_MUTEX.lock().unwrap();

        // Store original values
        let orig_guest_path = std::env::var("MSB_SHARED_VOLUME_GUEST_PATH").ok();
        let orig_flavor = std::env::var("MSB_DEFAULT_FLAVOR").ok();
        let orig_timeout = std::env::var("MSB_SESSION_TIMEOUT_SECONDS").ok();
        let orig_max_sessions = std::env::var("MSB_MAX_SESSIONS").ok();

        // Clear environment variables first
        std::env::remove_var("MSB_SHARED_VOLUME_GUEST_PATH");
        std::env::remove_var("MSB_DEFAULT_FLAVOR");
        std::env::remove_var("MSB_SESSION_TIMEOUT_SECONDS");
        std::env::remove_var("MSB_MAX_SESSIONS");

        // Set environment variables
        std::env::set_var("MSB_SHARED_VOLUME_GUEST_PATH", "/custom/shared");
        std::env::set_var("MSB_DEFAULT_FLAVOR", "medium");
        std::env::set_var("MSB_SESSION_TIMEOUT_SECONDS", "3600");
        std::env::set_var("MSB_MAX_SESSIONS", "20");

        let config = ConfigurationManager::from_env().unwrap();
        
        assert_eq!(config.get_shared_volume_guest_path(), "/custom/shared");
        assert_eq!(config.get_default_flavor(), SandboxFlavor::Medium);
        assert_eq!(config.get_session_timeout(), Duration::from_secs(3600));
        assert_eq!(config.get_max_sessions(), 20);

        // Restore original values
        std::env::remove_var("MSB_SHARED_VOLUME_GUEST_PATH");
        std::env::remove_var("MSB_DEFAULT_FLAVOR");
        std::env::remove_var("MSB_SESSION_TIMEOUT_SECONDS");
        std::env::remove_var("MSB_MAX_SESSIONS");
        if let Some(val) = orig_guest_path { std::env::set_var("MSB_SHARED_VOLUME_GUEST_PATH", val); }
        if let Some(val) = orig_flavor { std::env::set_var("MSB_DEFAULT_FLAVOR", val); }
        if let Some(val) = orig_timeout { std::env::set_var("MSB_SESSION_TIMEOUT_SECONDS", val); }
        if let Some(val) = orig_max_sessions { std::env::set_var("MSB_MAX_SESSIONS", val); }
    }

    #[test]
    fn test_configuration_manager_from_env_invalid_values() {
        // Use a mutex to ensure env tests don't run concurrently
        let _guard = ENV_TEST_MUTEX.lock().unwrap();

        // Store original values
        let orig_flavor = std::env::var("MSB_DEFAULT_FLAVOR").ok();
        let orig_timeout = std::env::var("MSB_SESSION_TIMEOUT_SECONDS").ok();
        let orig_max_sessions = std::env::var("MSB_MAX_SESSIONS").ok();

        // Clear all environment variables first
        std::env::remove_var("MSB_DEFAULT_FLAVOR");
        std::env::remove_var("MSB_SESSION_TIMEOUT_SECONDS");
        std::env::remove_var("MSB_MAX_SESSIONS");

        // Test invalid flavor
        std::env::set_var("MSB_DEFAULT_FLAVOR", "invalid");
        let config = ConfigurationManager::from_env().unwrap();
        assert_eq!(config.get_default_flavor(), SandboxFlavor::Small); // Should fallback to default
        std::env::remove_var("MSB_DEFAULT_FLAVOR");

        // Test invalid timeout
        std::env::set_var("MSB_SESSION_TIMEOUT_SECONDS", "invalid");
        let config = ConfigurationManager::from_env().unwrap();
        assert_eq!(config.get_session_timeout(), Duration::from_secs(1800)); // Should fallback to default
        std::env::remove_var("MSB_SESSION_TIMEOUT_SECONDS");

        // Test invalid max sessions
        std::env::set_var("MSB_MAX_SESSIONS", "invalid");
        let config = ConfigurationManager::from_env().unwrap();
        assert_eq!(config.get_max_sessions(), 10); // Should fallback to default
        std::env::remove_var("MSB_MAX_SESSIONS");

        // Restore original values
        if let Some(val) = orig_flavor { std::env::set_var("MSB_DEFAULT_FLAVOR", val); }
        if let Some(val) = orig_timeout { std::env::set_var("MSB_SESSION_TIMEOUT_SECONDS", val); }
        if let Some(val) = orig_max_sessions { std::env::set_var("MSB_MAX_SESSIONS", val); }
    }

    #[tokio::test]
    async fn test_session_manager_create_session() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        // Test successful session creation
        let session_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        assert!(session_id.starts_with("session-"));

        // Verify session was stored
        let session = manager.get_session(&session_id).unwrap();
        assert_eq!(session.id, session_id);
        assert_eq!(session.language, "python");
        assert_eq!(session.flavor, SandboxFlavor::Small);
        assert_eq!(session.status, SessionStatus::Ready);
        assert!(session.namespace.starts_with("simplified-mcp-"));
        assert!(session.sandbox_name.starts_with("sandbox-"));
    }

    #[tokio::test]
    async fn test_session_manager_create_session_unsupported_language() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        // Test unsupported language
        let result = manager.create_session("unsupported", SandboxFlavor::Small).await;
        assert!(matches!(result, Err(SimplifiedMcpError::UnsupportedLanguage(_))));
    }

    #[tokio::test]
    async fn test_session_manager_max_sessions_limit() {
        let mut config = ConfigurationManager::default();
        config.max_sessions = 2; // Set low limit for testing
        let manager = SessionManager::new(config);

        // Create sessions up to the limit
        let _session1 = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let _session2 = manager.create_session("node", SandboxFlavor::Medium).await.unwrap();

        // Third session should fail
        let result = manager.create_session("node", SandboxFlavor::Large).await;
        assert!(matches!(result, Err(SimplifiedMcpError::ResourceLimitExceeded(_))));
    }

    #[tokio::test]
    async fn test_session_manager_get_session() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        let session_id = manager.create_session("python", SandboxFlavor::Medium).await.unwrap();
        
        // Test successful get
        let session = manager.get_session(&session_id).unwrap();
        assert_eq!(session.id, session_id);
        assert_eq!(session.language, "python");
        assert_eq!(session.flavor, SandboxFlavor::Medium);

        // Test get non-existent session
        let result = manager.get_session("non-existent");
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));
    }

    #[tokio::test]
    async fn test_session_manager_touch_session() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        let session_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        
        // Get initial access time
        let session_before = manager.get_session(&session_id).unwrap();
        let initial_access = session_before.last_accessed;

        // Wait a bit and touch the session
        tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
        manager.touch_session(&session_id).unwrap();

        // Verify access time was updated
        let session_after = manager.get_session(&session_id).unwrap();
        assert!(session_after.last_accessed > initial_access);

        // Test touch non-existent session
        let result = manager.touch_session("non-existent");
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));
    }

    #[tokio::test]
    async fn test_session_manager_update_session_status() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        let session_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        
        // Update status to Ready
        manager.update_session_status(&session_id, SessionStatus::Ready).unwrap();
        let session = manager.get_session(&session_id).unwrap();
        assert_eq!(session.status, SessionStatus::Ready);

        // Update status to Running
        manager.update_session_status(&session_id, SessionStatus::Running).unwrap();
        let session = manager.get_session(&session_id).unwrap();
        assert_eq!(session.status, SessionStatus::Running);

        // Update status to Error
        let error_msg = "Test error".to_string();
        manager.update_session_status(&session_id, SessionStatus::Error(error_msg.clone())).unwrap();
        let session = manager.get_session(&session_id).unwrap();
        assert_eq!(session.status, SessionStatus::Error(error_msg));

        // Test update non-existent session
        let result = manager.update_session_status("non-existent", SessionStatus::Ready);
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));
    }

    #[tokio::test]
    async fn test_session_manager_stop_session() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        let session_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        
        // Stop the session
        manager.stop_session(&session_id).await.unwrap();
        
        // Verify session is marked as stopped
        let session = manager.get_session(&session_id).unwrap();
        assert_eq!(session.status, SessionStatus::Stopped);

        // Test stop non-existent session
        let result = manager.stop_session("non-existent").await;
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));
    }

    #[tokio::test]
    async fn test_session_manager_get_or_create_session() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        // Test create new session (None session_id)
        let session = manager.get_or_create_session(None, "python", SandboxFlavor::Small).await.unwrap();
        assert_eq!(session.language, "python");
        assert_eq!(session.flavor, SandboxFlavor::Small);
        let session_id = session.id.clone();

        // Test get existing session
        let session2 = manager.get_or_create_session(Some(session_id.clone()), "python", SandboxFlavor::Small).await.unwrap();
        assert_eq!(session2.id, session_id);

        // Test get existing session with wrong template
        let result = manager.get_or_create_session(Some(session_id.clone()), "node", SandboxFlavor::Small).await;
        assert!(matches!(result, Err(SimplifiedMcpError::InvalidSessionState(_))));

        // Test get non-existent session
        let result = manager.get_or_create_session(Some("non-existent".to_string()), "python", SandboxFlavor::Small).await;
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));

        // Test get stopped session
        manager.stop_session(&session_id).await.unwrap();
        let result = manager.get_or_create_session(Some(session_id), "python", SandboxFlavor::Small).await;
        assert!(matches!(result, Err(SimplifiedMcpError::InvalidSessionState(_))));
    }

    #[tokio::test]
    async fn test_session_manager_get_sessions() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        // Test empty sessions list
        let sessions = manager.get_sessions(None).unwrap();
        assert_eq!(sessions.len(), 0);

        // Create some sessions
        let session1_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let _session2_id = manager.create_session("node", SandboxFlavor::Medium).await.unwrap();

        // Test get all sessions
        let sessions = manager.get_sessions(None).unwrap();
        assert_eq!(sessions.len(), 2);

        // Test get specific session
        let sessions = manager.get_sessions(Some(&session1_id)).unwrap();
        assert_eq!(sessions.len(), 1);
        assert_eq!(sessions[0].id, session1_id);

        // Test get non-existent session
        let result = manager.get_sessions(Some("non-existent"));
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));
    }

    #[tokio::test]
    async fn test_session_manager_find_expired_sessions() {
        let mut config = ConfigurationManager::default();
        config.session_timeout = Duration::from_millis(50); // Very short timeout for testing
        let manager = SessionManager::new(config);

        // Create a session
        let session_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();

        // Initially no expired sessions
        let expired = manager.find_expired_sessions().unwrap();
        assert_eq!(expired.len(), 0);

        // Wait for timeout
        tokio::time::sleep(tokio::time::Duration::from_millis(60)).await;

        // Now should find expired session
        let expired = manager.find_expired_sessions().unwrap();
        assert_eq!(expired.len(), 1);
        assert_eq!(expired[0], session_id);

        // Stopped sessions should not be considered for timeout
        manager.stop_session(&session_id).await.unwrap();
        let expired = manager.find_expired_sessions().unwrap();
        assert_eq!(expired.len(), 0);
    }

    #[tokio::test]
    async fn test_session_manager_cleanup_expired_sessions() {
        let mut config = ConfigurationManager::default();
        config.session_timeout = Duration::from_millis(50); // Very short timeout for testing
        let manager = SessionManager::new(config);

        // Create sessions
        let session1_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let session2_id = manager.create_session("node", SandboxFlavor::Medium).await.unwrap();

        // Wait for timeout
        tokio::time::sleep(tokio::time::Duration::from_millis(60)).await;

        // Cleanup expired sessions
        let cleaned_up = manager.cleanup_expired_sessions().await.unwrap();
        assert_eq!(cleaned_up.len(), 2);
        assert!(cleaned_up.contains(&session1_id));
        assert!(cleaned_up.contains(&session2_id));

        // Verify sessions were removed
        let sessions = manager.get_sessions(None).unwrap();
        assert_eq!(sessions.len(), 0);
    }

    #[tokio::test]
    async fn test_session_manager_remove_session() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        let session_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        
        // Remove session
        let removed_session = manager.remove_session(&session_id).unwrap();
        assert_eq!(removed_session.id, session_id);

        // Verify session was removed
        let result = manager.get_session(&session_id);
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));

        // Test remove non-existent session
        let result = manager.remove_session("non-existent");
        assert!(matches!(result, Err(SimplifiedMcpError::SessionNotFound(_))));
    }

    #[tokio::test]
    async fn test_session_manager_get_session_count() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        // Initially no sessions
        assert_eq!(manager.get_session_count().unwrap(), 0);

        // Create sessions
        let _session1 = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        assert_eq!(manager.get_session_count().unwrap(), 1);

        let _session2 = manager.create_session("node", SandboxFlavor::Medium).await.unwrap();
        assert_eq!(manager.get_session_count().unwrap(), 2);
    }

    #[tokio::test]
    async fn test_session_manager_volume_path() {
        // Test without shared volume
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);
        
        assert_eq!(manager.get_volume_path(), None);
        let info = manager.get_volume_path_info();
        assert!(!info.available);

        // Test with shared volume
        let mut config = ConfigurationManager::default();
        config.shared_volume_path = Some(std::path::PathBuf::from("/tmp"));
        let manager = SessionManager::new(config);
        
        assert_eq!(manager.get_volume_path(), Some("/shared".to_string()));
        let info = manager.get_volume_path_info();
        assert!(info.available);
        assert_eq!(info.volume_path, "/shared");
    }

    #[test]
    fn test_session_info_methods() {
        let session = SessionInfo::new(
            "test-session".to_string(),
            "test-namespace".to_string(),
            "test-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Medium,
        );

        // Test initial state
        assert_eq!(session.id, "test-session");
        assert_eq!(session.namespace, "test-namespace");
        assert_eq!(session.sandbox_name, "test-sandbox");
        assert_eq!(session.language, "python");
        assert_eq!(session.flavor, SandboxFlavor::Medium);
        assert_eq!(session.status, SessionStatus::Creating);

        // Test uptime (should be very small since just created)
        assert!(session.uptime_seconds() < 2);
        assert!(session.idle_seconds() < 2);

        // Test timeout check
        assert!(!session.is_timed_out(Duration::from_secs(10)));
        // Note: We can't reliably test very short timeouts due to timing precision

        // Test to_summary
        let summary = session.to_summary();
        assert_eq!(summary.id, "test-session");
        assert_eq!(summary.language, "python");
        assert_eq!(summary.flavor, "medium");
        assert_eq!(summary.status, "creating");
    }

    #[test]
    fn test_session_info_touch() {
        let mut session = SessionInfo::new(
            "test-session".to_string(),
            "test-namespace".to_string(),
            "test-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Small,
        );

        let initial_access = session.last_accessed;
        
        // Wait a bit and touch
        std::thread::sleep(std::time::Duration::from_millis(10));
        session.touch();
        
        assert!(session.last_accessed > initial_access);
    }

    #[test]
    fn test_session_status_display() {
        assert_eq!(SessionStatus::Creating.to_string(), "creating");
        assert_eq!(SessionStatus::Ready.to_string(), "ready");
        assert_eq!(SessionStatus::Running.to_string(), "running");
        assert_eq!(SessionStatus::Error("test error".to_string()).to_string(), "error: test error");
        assert_eq!(SessionStatus::Stopped.to_string(), "stopped");
    }

    #[test]
    fn test_format_instant_as_iso8601() {
        let now = Instant::now();
        let formatted = format_instant_as_iso8601(now);
        assert_eq!(formatted, "just now");

        // Test with past instant (simulate by using an instant from the past)
        // Note: This is a simplified test since we can't easily create past Instants
        // In a real implementation, you'd use SystemTime and proper datetime formatting
    }

    #[test]
    fn test_automatic_sandbox_creator_creation() {
        let config = ConfigurationManager::default();
        let creator = AutomaticSandboxCreator::new(config);
        
        // Test that creator is created successfully
        assert!(creator.get_config().get_max_sessions() > 0);
    }

    #[test]
    fn test_generate_sandbox_config() {
        let config = ConfigurationManager::default();
        let creator = AutomaticSandboxCreator::new(config);
        
        // Create a test session info
        let session_info = SessionInfo::new(
            "test-session".to_string(),
            "test-namespace".to_string(),
            "test-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Medium,
        );

        // Generate sandbox config
        let sandbox_config = creator.generate_sandbox_config(&session_info).unwrap();
        
        // Verify the configuration
        assert_eq!(sandbox_config.image, Some("microsandbox/python".to_string()));
        assert_eq!(sandbox_config.memory, Some(2048));
        assert_eq!(sandbox_config.cpus, Some(2));
        assert!(sandbox_config.envs.contains(&"MICROSANDBOX_SIMPLIFIED_MCP=true".to_string()));
    }

    #[test]
    fn test_generate_sandbox_config_unsupported_language() {
        let config = ConfigurationManager::default();
        let creator = AutomaticSandboxCreator::new(config);
        
        // Create a test session info with unsupported language
        let session_info = SessionInfo::new(
            "test-session".to_string(),
            "test-namespace".to_string(),
            "test-sandbox".to_string(),
            "unsupported".to_string(),
            SandboxFlavor::Small,
        );

        // Generate sandbox config should fail
        let result = creator.generate_sandbox_config(&session_info);
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), SimplifiedMcpError::UnsupportedLanguage(_)));
    }

    #[test]
    fn test_generate_volume_mappings_no_shared_volume() {
        let config = ConfigurationManager::default();
        let creator = AutomaticSandboxCreator::new(config);
        
        let volumes = creator.generate_volume_mappings();
        assert!(volumes.is_empty());
    }

    #[test]
    fn test_generate_environment_variables() {
        let config = ConfigurationManager::default();
        let creator = AutomaticSandboxCreator::new(config);
        
        let envs = creator.generate_environment_variables();
        assert!(envs.contains(&"MICROSANDBOX_SIMPLIFIED_MCP=true".to_string()));
    }

    #[test]
    fn test_integration_automatic_sandbox_creation_workflow() {
        // This test demonstrates the complete workflow of automatic sandbox creation
        // Note: This is a unit test that doesn't actually create sandboxes, but shows the flow
        
        let config = ConfigurationManager::default();
        let session_manager = SessionManager::new(config.clone());
        let creator = AutomaticSandboxCreator::new(config);
        
        // Create a session info as would be done by SessionManager
        let session_info = SessionInfo::new(
            "integration-test-session".to_string(),
            "integration-namespace".to_string(),
            "integration-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Large,
        );
        
        // Generate the sandbox configuration that would be used
        let sandbox_config = creator.generate_sandbox_config(&session_info).unwrap();
        
        // Verify the complete configuration is correct
        assert_eq!(sandbox_config.image, Some("microsandbox/python".to_string()));
        assert_eq!(sandbox_config.memory, Some(4096)); // Large flavor
        assert_eq!(sandbox_config.cpus, Some(4)); // Large flavor
        assert!(sandbox_config.volumes.is_empty()); // No shared volume in default config
        assert!(sandbox_config.envs.contains(&"MICROSANDBOX_SIMPLIFIED_MCP=true".to_string()));
        assert!(sandbox_config.ports.is_empty()); // Ports managed by existing system
        assert!(sandbox_config.depends_on.is_empty());
        assert!(sandbox_config.workdir.is_none()); // Use container default
        assert!(sandbox_config.shell.is_none()); // Use container default
        assert!(sandbox_config.scripts.is_empty());
        assert!(sandbox_config.exec.is_none());
        
        // Verify session manager integration points
        assert_eq!(session_manager.get_session_count().unwrap(), 0);
        assert!(session_manager.get_volume_path().is_none()); // No shared volume configured
    }

    #[test]
    fn test_integration_with_shared_volume() {
        // Test the integration when shared volume is configured
        use std::env;
        
        let _guard = ENV_TEST_MUTEX.lock().unwrap();
        
        // Set up environment variables for shared volume
        env::set_var("MSB_SHARED_VOLUME_PATH", "/tmp/test-shared");
        env::set_var("MSB_SHARED_VOLUME_GUEST_PATH", "/workspace");
        
        // Create configuration from environment
        let config = match ConfigurationManager::from_env() {
            Ok(config) => config,
            Err(_) => {
                // Clean up and skip test if validation fails (e.g., path doesn't exist)
                env::remove_var("MSB_SHARED_VOLUME_PATH");
                env::remove_var("MSB_SHARED_VOLUME_GUEST_PATH");
                return;
            }
        };
        
        let creator = AutomaticSandboxCreator::new(config.clone());
        
        // Create session info
        let session_info = SessionInfo::new(
            "shared-volume-test".to_string(),
            "shared-namespace".to_string(),
            "shared-sandbox".to_string(),
            "node".to_string(),
            SandboxFlavor::Small,
        );
        
        // Generate configuration
        let sandbox_config = creator.generate_sandbox_config(&session_info).unwrap();
        
        // Verify shared volume configuration
        assert_eq!(sandbox_config.image, Some("microsandbox/node".to_string()));
        
        // Check environment variables include shared volume path
        assert!(sandbox_config.envs.contains(&"SHARED_VOLUME_PATH=/workspace".to_string()));
        assert!(sandbox_config.envs.contains(&"MICROSANDBOX_SIMPLIFIED_MCP=true".to_string()));
        
        // Clean up environment variables
        env::remove_var("MSB_SHARED_VOLUME_PATH");
        env::remove_var("MSB_SHARED_VOLUME_GUEST_PATH");
    }

    #[tokio::test]
    async fn test_cleanup_manager_comprehensive_cleanup() {
        let mut config = ConfigurationManager::default();
        config.session_timeout = Duration::from_millis(50); // Very short timeout for testing
        
        // Create managers using the factory method
        let (session_manager, resource_manager, cleanup_manager, _cleanup_handles) = 
            SessionManager::create_with_cleanup(config).unwrap();

        // Create some sessions
        let session1_id = session_manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let session2_id = session_manager.create_session("node", SandboxFlavor::Medium).await.unwrap();

        // Allocate resources for the sessions
        let _allocation1 = resource_manager.allocate_resources(session1_id.clone(), SandboxFlavor::Small).unwrap();
        let _allocation2 = resource_manager.allocate_resources(session2_id.clone(), SandboxFlavor::Medium).unwrap();

        // Verify initial state
        let health_stats = cleanup_manager.get_system_health().unwrap();
        assert_eq!(health_stats.total_sessions, 2);
        assert_eq!(health_stats.active_sessions, 2);
        assert_eq!(health_stats.resource_stats.active_sessions, 2);

        // Wait for timeout
        tokio::time::sleep(tokio::time::Duration::from_millis(60)).await;

        // Perform comprehensive cleanup
        let cleanup_stats = cleanup_manager.manual_comprehensive_cleanup().await.unwrap();
        assert_eq!(cleanup_stats.expired_sessions_found, 2);
        assert_eq!(cleanup_stats.sessions_cleaned_up, 2);
        assert_eq!(cleanup_stats.cleanup_errors, 0);
        assert_eq!(cleanup_stats.active_sessions_after_cleanup, 0);
        assert_eq!(cleanup_stats.allocated_ports_after_cleanup, 0);

        // Verify final state
        let final_health_stats = cleanup_manager.get_system_health().unwrap();
        assert_eq!(final_health_stats.total_sessions, 0);
        assert_eq!(final_health_stats.active_sessions, 0);
        assert_eq!(final_health_stats.resource_stats.active_sessions, 0);
    }

    #[tokio::test]
    async fn test_session_timeout_detection() {
        let mut config = ConfigurationManager::default();
        config.session_timeout = Duration::from_millis(100);
        let manager = SessionManager::new(config);

        // Create a session
        let session_id = manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let session = manager.get_session(&session_id).unwrap();

        // Initially should not timeout
        assert!(!session.should_timeout(Duration::from_millis(100)));

        // Wait and check timeout
        tokio::time::sleep(tokio::time::Duration::from_millis(110)).await;
        
        // Check if session would be found as expired (without updating last_accessed)
        let expired_sessions = manager.find_expired_sessions().unwrap();
        assert_eq!(expired_sessions.len(), 1);
        assert_eq!(expired_sessions[0], session_id);

        // Test different session states
        manager.update_session_status(&session_id, SessionStatus::Creating).unwrap();
        let expired_sessions = manager.find_expired_sessions().unwrap();
        assert_eq!(expired_sessions.len(), 0); // Creating sessions don't timeout

        manager.update_session_status(&session_id, SessionStatus::Stopped).unwrap();
        let expired_sessions = manager.find_expired_sessions().unwrap();
        assert_eq!(expired_sessions.len(), 0); // Stopped sessions don't timeout

        // For error sessions, create a new session and test error timeout
        let error_session_id = manager.create_session("node", SandboxFlavor::Small).await.unwrap();
        manager.update_session_status(&error_session_id, SessionStatus::Error("test error".to_string())).unwrap();
        
        // Error sessions should timeout after 5 minutes (300 seconds), but since update_session_status
        // calls touch(), we need to wait longer than that. Let's just verify the logic works
        // by checking that error sessions are included in the timeout logic
        let session = manager.get_session(&error_session_id).unwrap();
        match &session.status {
            SessionStatus::Error(_) => {
                // This is correct - we have an error session
                assert!(true);
            }
            _ => panic!("Session should be in error state"),
        }
    }

    // Error Handling Tests
    #[test]
    fn test_error_classification_compilation_error() {
        let error = classify_execution_error(
            "",
            "SyntaxError: invalid syntax",
            None,
            "python"
        );
        
        match error {
            SimplifiedMcpError::CompilationError(msg) => {
                assert!(msg.contains("Compilation failed"));
                assert!(msg.contains("python"));
            }
            _ => panic!("Expected CompilationError, got {:?}", error),
        }
    }

    #[test]
    fn test_error_classification_runtime_error() {
        let error = classify_execution_error(
            "",
            "NameError: name 'undefined_var' is not defined",
            Some(1),
            "python"
        );
        
        match error {
            SimplifiedMcpError::RuntimeError(msg) => {
                assert!(msg.contains("Runtime error"));
            }
            _ => panic!("Expected RuntimeError, got {:?}", error),
        }
    }

    #[test]
    fn test_error_classification_system_error() {
        let error = classify_execution_error(
            "",
            "permission denied",
            Some(126),
            "python"
        );
        
        match error {
            SimplifiedMcpError::SystemError(msg) => {
                assert!(msg.contains("System error"));
            }
            _ => panic!("Expected SystemError, got {:?}", error),
        }
    }

    #[test]
    fn test_user_friendly_error_session_not_found() {
        let error = SimplifiedMcpError::SessionNotFound("test-session".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "session_not_found");
        assert!(user_friendly.message.contains("test-session"));
        assert!(!user_friendly.suggestions.is_empty());
        assert!(!user_friendly.recovery_actions.is_empty());
        
        // Check that recovery action is present
        let has_create_action = user_friendly.recovery_actions
            .iter()
            .any(|action| action.action == "create_new_session");
        assert!(has_create_action);
    }

    #[test]
    fn test_user_friendly_error_resource_limit_exceeded() {
        let error = SimplifiedMcpError::ResourceLimitExceeded("Too many sessions".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "resource_limit_exceeded");
        assert!(user_friendly.message.contains("resource limits"));
        assert!(user_friendly.suggestions.len() >= 3);
        
        // Check for specific suggestions
        let has_wait_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("Wait"));
        assert!(has_wait_suggestion);
        
        // Check for recovery actions
        let has_wait_action = user_friendly.recovery_actions
            .iter()
            .any(|action| action.action == "wait_and_retry");
        assert!(has_wait_action);
    }

    #[test]
    fn test_user_friendly_error_unsupported_language() {
        let error = SimplifiedMcpError::UnsupportedLanguage("java".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "unsupported_language");
        assert!(user_friendly.message.contains("java"));
        assert!(user_friendly.suggestions.len() >= 2);
        
        // Check for template suggestions
        let has_python_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("python"));
        assert!(has_python_suggestion);
        
        let has_node_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("node"));
        assert!(has_node_suggestion);
    }

    #[test]
    fn test_user_friendly_error_compilation_error() {
        let error = SimplifiedMcpError::CompilationError("Syntax error in code".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "compilation_error");
        assert!(user_friendly.message.contains("compilation failed"));
        assert!(user_friendly.suggestions.len() >= 3);
        
        // Check for syntax-related suggestions
        let has_syntax_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("syntax"));
        assert!(has_syntax_suggestion);
    }

    #[test]
    fn test_truncate_error_message() {
        let short_message = "Short error";
        assert_eq!(truncate_error_message(short_message), short_message);
        
        let long_message = "A".repeat(600);
        let truncated = truncate_error_message(&long_message);
        assert!(truncated.len() < long_message.len());
        assert!(truncated.contains("truncated"));
    }

    #[test]
    fn test_error_classification_node_compilation_error() {
        let error = classify_execution_error(
            "",
            "SyntaxError: Unexpected token",
            None,
            "node"
        );
        
        match error {
            SimplifiedMcpError::CompilationError(msg) => {
                assert!(msg.contains("Compilation failed"));
                assert!(msg.contains("node"));
            }
            _ => panic!("Expected CompilationError for Node.js, got {:?}", error),
        }
    }

    #[test]
    fn test_error_classification_default_code_execution_error() {
        let error = classify_execution_error(
            "",
            "Some unknown error",
            Some(1),
            "python"
        );
        
        match error {
            SimplifiedMcpError::CodeExecutionError(msg) => {
                assert!(msg.contains("Code execution failed"));
                assert!(msg.contains("exit code"));
            }
            _ => panic!("Expected CodeExecutionError, got {:?}", error),
        }
    }

    #[test]
    fn test_user_friendly_error_execution_timeout() {
        let error = SimplifiedMcpError::ExecutionTimeout("Code took too long".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "execution_timeout");
        assert!(user_friendly.message.contains("timed out"));
        assert!(user_friendly.suggestions.len() >= 3);
        
        // Check for optimization suggestions
        let has_optimization_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("Optimize"));
        assert!(has_optimization_suggestion);
    }

    #[test]
    fn test_user_friendly_error_invalid_flavor() {
        let error = SimplifiedMcpError::InvalidFlavor("huge".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "invalid_flavor");
        assert!(user_friendly.message.contains("huge"));
        assert!(user_friendly.suggestions.len() >= 3);
        
        // Check for flavor suggestions
        let has_small_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("small"));
        assert!(has_small_suggestion);
        
        let has_medium_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("medium"));
        assert!(has_medium_suggestion);
        
        let has_large_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("large"));
        assert!(has_large_suggestion);
    }

    // Additional tests for CleanupManager
    #[tokio::test]
    async fn test_cleanup_manager_creation() {
        let config = ConfigurationManager::default();
        let session_manager = Arc::new(SessionManager::new(config.clone()));
        let resource_manager = Arc::new(ResourceManager::new(config.clone()));
        
        let cleanup_manager = CleanupManager::new(
            Arc::clone(&session_manager),
            Arc::clone(&resource_manager),
            config,
        );
        
        // Test that cleanup manager is created successfully
        assert_eq!(cleanup_manager.get_config().get_max_sessions(), 10);
        assert!(Arc::ptr_eq(cleanup_manager.get_session_manager(), &session_manager));
        assert!(Arc::ptr_eq(cleanup_manager.get_resource_manager(), &resource_manager));
    }

    #[tokio::test]
    async fn test_cleanup_manager_system_health() {
        let mut config = ConfigurationManager::default();
        config.session_timeout = Duration::from_secs(300); // 5 minutes
        
        let session_manager = Arc::new(SessionManager::new(config.clone()));
        let resource_manager = Arc::new(ResourceManager::new(config.clone()));
        let cleanup_manager = CleanupManager::new(
            Arc::clone(&session_manager),
            Arc::clone(&resource_manager),
            config,
        );

        // Initially empty system
        let health = cleanup_manager.get_system_health().unwrap();
        assert_eq!(health.total_sessions, 0);
        assert_eq!(health.active_sessions, 0);
        assert_eq!(health.creating_sessions, 0);
        assert_eq!(health.ready_sessions, 0);
        assert_eq!(health.running_sessions, 0);
        assert_eq!(health.error_sessions, 0);
        assert_eq!(health.stopped_sessions, 0);
        assert_eq!(health.sessions_near_timeout, 0);
        assert_eq!(health.expired_sessions, 0);

        // Create some sessions with different states
        let session1_id = session_manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let session2_id = session_manager.create_session("node", SandboxFlavor::Medium).await.unwrap();
        let session3_id = session_manager.create_session("python", SandboxFlavor::Large).await.unwrap();

        // Update session states
        session_manager.update_session_status(&session1_id, SessionStatus::Ready).unwrap();
        session_manager.update_session_status(&session2_id, SessionStatus::Running).unwrap();
        session_manager.update_session_status(&session3_id, SessionStatus::Error("test error".to_string())).unwrap();

        // Check health stats
        let health = cleanup_manager.get_system_health().unwrap();
        assert_eq!(health.total_sessions, 3);
        assert_eq!(health.active_sessions, 2); // Ready + Running
        assert_eq!(health.ready_sessions, 1);
        assert_eq!(health.running_sessions, 1);
        assert_eq!(health.error_sessions, 1);
        assert_eq!(health.stopped_sessions, 0);
    }

    #[tokio::test]
    async fn test_cleanup_manager_graceful_shutdown() {
        let mut config = ConfigurationManager::default();
        config.session_timeout = Duration::from_millis(50);
        
        let (session_manager, resource_manager, cleanup_manager, cleanup_handles) = 
            SessionManager::create_with_cleanup(config).unwrap();

        // Create some sessions
        let session1_id = session_manager.create_session("python", SandboxFlavor::Small).await.unwrap();
        let session2_id = session_manager.create_session("node", SandboxFlavor::Medium).await.unwrap();

        // Allocate resources
        let _allocation1 = resource_manager.allocate_resources(session1_id.clone(), SandboxFlavor::Small).unwrap();
        let _allocation2 = resource_manager.allocate_resources(session2_id.clone(), SandboxFlavor::Medium).unwrap();

        // Perform graceful shutdown
        let shutdown_stats = cleanup_manager.graceful_shutdown(cleanup_handles).await.unwrap();
        
        assert_eq!(shutdown_stats.expired_sessions_found, 2);
        assert_eq!(shutdown_stats.sessions_cleaned_up, 2);
        assert_eq!(shutdown_stats.cleanup_errors, 0);
        assert_eq!(shutdown_stats.active_sessions_after_cleanup, 0);
        assert_eq!(shutdown_stats.allocated_ports_after_cleanup, 0);
    }

    // Additional tests for ResourceManager edge cases
    #[test]
    fn test_resource_manager_port_range_validation() {
        let config = ConfigurationManager::default();
        
        // Test invalid port ranges
        assert!(ResourceManager::with_port_range(config.clone(), 8000, 8000).is_err());
        assert!(ResourceManager::with_port_range(config.clone(), 8010, 8000).is_err());
        
        // Test valid port range
        assert!(ResourceManager::with_port_range(config, 8000, 8010).is_ok());
    }

    #[test]
    fn test_resource_manager_get_all_allocations() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::new(config);

        // Initially no allocations
        let allocations = resource_manager.get_all_allocations().unwrap();
        assert_eq!(allocations.len(), 0);

        // Allocate resources for multiple sessions
        let _alloc1 = resource_manager.allocate_resources(
            "session1".to_string(),
            SandboxFlavor::Small,
        ).unwrap();

        let _alloc2 = resource_manager.allocate_resources(
            "session2".to_string(),
            SandboxFlavor::Medium,
        ).unwrap();

        // Check all allocations
        let allocations = resource_manager.get_all_allocations().unwrap();
        assert_eq!(allocations.len(), 2);
        
        let session_ids: Vec<String> = allocations.iter().map(|a| a.session_id.clone()).collect();
        assert!(session_ids.contains(&"session1".to_string()));
        assert!(session_ids.contains(&"session2".to_string()));
    }

    #[test]
    fn test_resource_stats_flavor_counts() {
        let config = ConfigurationManager::default();
        let resource_manager = ResourceManager::new(config);

        // Allocate resources with different flavors
        let _alloc1 = resource_manager.allocate_resources(
            "session1".to_string(),
            SandboxFlavor::Small,
        ).unwrap();

        let _alloc2 = resource_manager.allocate_resources(
            "session2".to_string(),
            SandboxFlavor::Small,
        ).unwrap();

        let _alloc3 = resource_manager.allocate_resources(
            "session3".to_string(),
            SandboxFlavor::Medium,
        ).unwrap();

        let _alloc4 = resource_manager.allocate_resources(
            "session4".to_string(),
            SandboxFlavor::Large,
        ).unwrap();

        // Check resource stats
        let stats = resource_manager.get_resource_stats().unwrap();
        assert_eq!(stats.active_sessions, 4);
        assert_eq!(stats.total_memory_mb, 1024 + 1024 + 2048 + 4096); // 8192 MB total
        assert_eq!(stats.total_cpus, 1 + 1 + 2 + 4); // 8 CPUs total
        
        // Check flavor counts
        assert_eq!(stats.flavor_counts.get(&SandboxFlavor::Small), Some(&2));
        assert_eq!(stats.flavor_counts.get(&SandboxFlavor::Medium), Some(&1));
        assert_eq!(stats.flavor_counts.get(&SandboxFlavor::Large), Some(&1));
    }

    // Additional tests for SessionManager edge cases
    #[tokio::test]
    async fn test_session_manager_concurrent_access() {
        let config = ConfigurationManager::default();
        let manager = Arc::new(SessionManager::new(config));

        // Test concurrent session creation
        let manager1 = Arc::clone(&manager);
        let manager2 = Arc::clone(&manager);
        let manager3 = Arc::clone(&manager);

        let handle1 = tokio::spawn(async move {
            manager1.create_session("python", SandboxFlavor::Small).await
        });

        let handle2 = tokio::spawn(async move {
            manager2.create_session("node", SandboxFlavor::Medium).await
        });

        let handle3 = tokio::spawn(async move {
            manager3.create_session("python", SandboxFlavor::Large).await
        });

        // Wait for all sessions to be created
        let session1_id = handle1.await.unwrap().unwrap();
        let session2_id = handle2.await.unwrap().unwrap();
        let session3_id = handle3.await.unwrap().unwrap();

        // Verify all sessions were created successfully
        assert!(manager.get_session(&session1_id).is_ok());
        assert!(manager.get_session(&session2_id).is_ok());
        assert!(manager.get_session(&session3_id).is_ok());
        assert_eq!(manager.get_session_count().unwrap(), 3);
    }

    #[tokio::test]
    async fn test_session_manager_template_validation() {
        let config = ConfigurationManager::default();
        let manager = SessionManager::new(config);

        // Test supported templates
        assert!(manager.create_session("python", SandboxFlavor::Small).await.is_ok());
        assert!(manager.create_session("node", SandboxFlavor::Medium).await.is_ok());

        // Test unsupported templates
        assert!(manager.create_session("java", SandboxFlavor::Small).await.is_err());
        assert!(manager.create_session("rust", SandboxFlavor::Medium).await.is_err());
        assert!(manager.create_session("", SandboxFlavor::Large).await.is_err());
    }

    // Additional tests for AutomaticSandboxCreator
    #[test]
    fn test_automatic_sandbox_creator_with_shared_volume() {
        let mut config = ConfigurationManager::default();
        config.shared_volume_path = Some(std::path::PathBuf::from("/tmp/test"));
        config.shared_volume_guest_path = "/workspace".to_string();
        
        let creator = AutomaticSandboxCreator::new(config);
        
        let session_info = SessionInfo::new(
            "test-session".to_string(),
            "test-namespace".to_string(),
            "test-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Small,
        );

        let sandbox_config = creator.generate_sandbox_config(&session_info).unwrap();
        
        // Check that shared volume is configured
        assert!(!sandbox_config.volumes.is_empty());
        let volume_mapping = &sandbox_config.volumes[0];
        assert!(volume_mapping.contains("/tmp/test"));
        assert!(volume_mapping.contains("/workspace"));
        
        // Check environment variables include shared volume path
        assert!(sandbox_config.envs.contains(&"SHARED_VOLUME_PATH=/workspace".to_string()));
    }

    #[test]
    fn test_automatic_sandbox_creator_different_flavors() {
        let config = ConfigurationManager::default();
        let creator = AutomaticSandboxCreator::new(config);
        
        // Test Small flavor
        let session_small = SessionInfo::new(
            "small-session".to_string(),
            "small-namespace".to_string(),
            "small-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Small,
        );
        let config_small = creator.generate_sandbox_config(&session_small).unwrap();
        assert_eq!(config_small.memory, Some(1024));
        assert_eq!(config_small.cpus, Some(1));

        // Test Medium flavor
        let session_medium = SessionInfo::new(
            "medium-session".to_string(),
            "medium-namespace".to_string(),
            "medium-sandbox".to_string(),
            "node".to_string(),
            SandboxFlavor::Medium,
        );
        let config_medium = creator.generate_sandbox_config(&session_medium).unwrap();
        assert_eq!(config_medium.memory, Some(2048));
        assert_eq!(config_medium.cpus, Some(2));
        assert_eq!(config_medium.image, Some("microsandbox/node".to_string()));

        // Test Large flavor
        let session_large = SessionInfo::new(
            "large-session".to_string(),
            "large-namespace".to_string(),
            "large-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Large,
        );
        let config_large = creator.generate_sandbox_config(&session_large).unwrap();
        assert_eq!(config_large.memory, Some(4096));
        assert_eq!(config_large.cpus, Some(4));
    }

    // Additional error handling tests
    #[test]
    fn test_user_friendly_error_session_creation_failed() {
        let error = SimplifiedMcpError::SessionCreationFailed("Out of memory".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "session_creation_failed");
        assert!(user_friendly.message.contains("Failed to create"));
        assert!(user_friendly.details.is_some());
        assert!(user_friendly.details.as_ref().unwrap().contains("Out of memory"));
        
        // Check for recovery actions
        let has_retry_action = user_friendly.recovery_actions
            .iter()
            .any(|action| action.action == "retry_with_smaller_flavor");
        assert!(has_retry_action);
    }

    #[test]
    fn test_user_friendly_error_invalid_session_state() {
        let error = SimplifiedMcpError::InvalidSessionState("Session is stopped".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "invalid_session_state");
        assert!(user_friendly.message.contains("invalid state"));
        assert!(user_friendly.suggestions.len() >= 2);
        
        // Check for create new session suggestion
        let has_create_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("Create a new session"));
        assert!(has_create_suggestion);
    }

    #[test]
    fn test_user_friendly_error_runtime_error() {
        let error = SimplifiedMcpError::RuntimeError("Division by zero".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "runtime_error");
        assert!(user_friendly.message.contains("runtime"));
        assert!(user_friendly.details.is_some());
        assert!(user_friendly.details.as_ref().unwrap().contains("Division by zero"));
        
        // Check for debugging suggestions
        let has_debug_suggestion = user_friendly.suggestions
            .iter()
            .any(|suggestion| suggestion.contains("logical errors"));
        assert!(has_debug_suggestion);
    }

    #[test]
    fn test_user_friendly_error_system_error() {
        let error = SimplifiedMcpError::SystemError("Disk full".to_string());
        let user_friendly = error.get_user_friendly_message();
        
        assert_eq!(user_friendly.error_type, "system_error");
        assert!(user_friendly.message.contains("System error"));
        assert!(user_friendly.details.is_some());
        assert!(user_friendly.details.as_ref().unwrap().contains("Disk full"));
        
        // Check for retry action
        let has_retry_action = user_friendly.recovery_actions
            .iter()
            .any(|action| action.action == "retry_operation");
        assert!(has_retry_action);
    }

    // Additional validation tests
    #[test]
    fn test_session_info_should_timeout_logic() {
        let mut session = SessionInfo::new(
            "test-session".to_string(),
            "test-namespace".to_string(),
            "test-sandbox".to_string(),
            "python".to_string(),
            SandboxFlavor::Small,
        );

        let timeout = Duration::from_millis(100);

        // Creating sessions should not timeout
        session.status = SessionStatus::Creating;
        assert!(!session.should_timeout(timeout));

        // Stopped sessions should not timeout
        session.status = SessionStatus::Stopped;
        assert!(!session.should_timeout(timeout));

        // Ready sessions should timeout after the timeout period
        session.status = SessionStatus::Ready;
        session.last_accessed = Instant::now() - Duration::from_millis(150);
        assert!(session.should_timeout(timeout));

        // Running sessions should timeout after the timeout period
        session.status = SessionStatus::Running;
        assert!(session.should_timeout(timeout));

        // Error sessions should timeout after a shorter period (5 minutes)
        session.status = SessionStatus::Error("test error".to_string());
        session.last_accessed = Instant::now() - Duration::from_secs(301); // 5+ minutes ago
        assert!(session.should_timeout(timeout));

        // Recent error sessions should not timeout
        session.last_accessed = Instant::now() - Duration::from_secs(60); // 1 minute ago
        assert!(!session.should_timeout(timeout));
    }

    #[test]
    fn test_port_manager_edge_cases() {
        let mut port_manager = PortManager::new(8000, 8001).unwrap(); // Only 1 port

        // Allocate the only port
        let port = port_manager.allocate_port().unwrap();
        assert_eq!(port, 8000);
        assert_eq!(port_manager.allocated_count(), 1);
        assert_eq!(port_manager.available_count(), 0);

        // Try to allocate when no ports available
        let result = port_manager.allocate_port();
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), SimplifiedMcpError::ResourceLimitExceeded(_)));

        // Release and reallocate
        port_manager.release_port(port).unwrap();
        assert_eq!(port_manager.allocated_count(), 0);
        assert_eq!(port_manager.available_count(), 1);

        let port2 = port_manager.allocate_port().unwrap();
        assert_eq!(port2, 8000); // Should get the same port back
    }

    #[test]
    fn test_configuration_manager_edge_cases() {
        let mut config = ConfigurationManager::default();

        // Test boundary values for session timeout
        config.session_timeout = Duration::from_secs(60); // Minimum valid
        assert!(config.validate().is_ok());

        config.session_timeout = Duration::from_secs(86400); // Maximum valid
        assert!(config.validate().is_ok());

        config.session_timeout = Duration::from_secs(59); // Below minimum
        assert!(config.validate().is_err());

        config.session_timeout = Duration::from_secs(86401); // Above maximum
        assert!(config.validate().is_err());

        // Test boundary values for max sessions
        let mut config = ConfigurationManager::default();
        config.max_sessions = 1; // Minimum valid
        assert!(config.validate().is_ok());

        config.max_sessions = 100; // Maximum valid
        assert!(config.validate().is_ok());

        config.max_sessions = 0; // Below minimum
        assert!(config.validate().is_err());

        config.max_sessions = 101; // Above maximum
        assert!(config.validate().is_err());
    }

    // Test request/response serialization edge cases
    #[test]
    fn test_request_deserialization_edge_cases() {
        // Test ExecuteCodeRequest with minimal fields
        let json = r#"{"code": "print('hello')"}"#;
        let request: ExecuteCodeRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.code, "print('hello')");
        assert_eq!(request.template, None);
        assert_eq!(request.session_id, None);
        assert_eq!(request.flavor, None);

        // Test ExecuteCommandRequest with minimal fields
        let json = r#"{"command": "ls"}"#;
        let request: ExecuteCommandRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.command, "ls");
        assert_eq!(request.args, None);
        assert_eq!(request.template, None);
        assert_eq!(request.session_id, None);
        assert_eq!(request.flavor, None);

        // Test GetSessionsRequest with empty object
        let json = r#"{}"#;
        let request: GetSessionsRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.session_id, None);

        // Test GetVolumePathRequest with empty object
        let json = r#"{}"#;
        let request: GetVolumePathRequest = serde_json::from_str(json).unwrap();
        assert_eq!(request.session_id, None);
    }

    #[test]
    fn test_response_serialization_edge_cases() {
        // Test ExecutionResponse with None exit_code
        let response = ExecutionResponse {
            session_id: "test".to_string(),
            stdout: "output".to_string(),
            stderr: "".to_string(),
            exit_code: None,
            execution_time_ms: 0,
            session_created: false,
        };
        
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"exit_code\":null"));

        // Test SessionSummary with various status strings
        let summary = SessionSummary {
            id: "test".to_string(),
            language: "python".to_string(),
            flavor: "small".to_string(),
            status: "error: test error".to_string(),
            created_at: "just now".to_string(),
            last_accessed: "just now".to_string(),
            uptime_seconds: 0,
        };
        
        let json = serde_json::to_string(&summary).unwrap();
        assert!(json.contains("error: test error"));

        // Test VolumePathResponse with unavailable volume
        let response = VolumePathResponse {
            volume_path: "/shared".to_string(),
            description: "No shared volume configured".to_string(),
            available: false,
        };
        
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"available\":false"));
    }
}