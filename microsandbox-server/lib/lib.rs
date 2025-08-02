//! Microsandbox Server - A server for managing sandboxes.

#![warn(missing_docs)]

//--------------------------------------------------------------------------------------------------
// Exports
//--------------------------------------------------------------------------------------------------

pub mod config;
pub mod error;
pub mod handler;
pub mod management;
pub mod mcp;
#[cfg(test)]
mod mcp_tests;
#[cfg(test)]
mod simplified_mcp_integration_tests;
pub mod middleware;
pub mod payload;
pub mod port;
pub mod route;
pub mod simplified_mcp;
pub mod state;

pub use config::*;
pub use error::*;
pub use handler::*;
pub use management::*;
pub use mcp::*;
pub use middleware::*;
pub use payload::*;
pub use route::*;
pub use simplified_mcp::*;
pub use state::*;
