# Project Structure

## Repository Organization

### Root Level Structure
```
microsandbox/
├── Cargo.toml                 # Workspace configuration
├── Makefile                   # Build system
├── README.md                  # Main project documentation
├── mcp-design.md             # MCP protocol design document
├── Sandboxfile               # Project sandbox configuration
└── rust-toolchain.toml      # Rust toolchain specification
```

## Core Rust Crates

### microsandbox-core/
**Purpose**: Core VM lifecycle, OCI image management, and orchestration
```
microsandbox-core/
├── Cargo.toml
├── lib/
│   ├── config/               # Configuration types and validation
│   ├── management/           # Orchestration and sandbox lifecycle
│   │   ├── sandbox.rs        # Sandbox management
│   │   ├── image.rs          # OCI image operations
│   │   ├── db.rs             # Database operations
│   │   └── orchestra.rs      # Service coordination
│   ├── models.rs             # Database models and schema
│   ├── oci/                  # OCI registry and image operations
│   ├── runtime/              # Process supervision
│   ├── utils/                # Common utilities
│   └── vm/                   # MicroVM configuration and control
└── tests/                    # Integration tests
```

### microsandbox-server/
**Purpose**: HTTP API server for sandbox management
```
microsandbox-server/
├── Cargo.toml
└── lib/
    ├── config.rs             # Server configuration
    ├── handler.rs            # HTTP request handlers
    ├── mcp.rs                # MCP protocol implementation
    ├── simplified_mcp.rs     # Simplified MCP interface
    ├── middleware.rs         # HTTP middleware
    ├── payload.rs            # Request/response types
    ├── route.rs              # Route definitions
    └── state.rs              # Application state
```

### microsandbox-portal/
**Purpose**: Execution environment and process supervision
```
microsandbox-portal/
├── Cargo.toml
├── lib/
│   ├── handler.rs            # Execution handlers
│   ├── payload.rs            # Execution payloads
│   ├── portal/               # Portal implementation
│   └── state.rs              # Portal state management
└── examples/                 # Usage examples
```

### microsandbox-cli/
**Purpose**: Command-line interface
```
microsandbox-cli/
├── Cargo.toml
└── lib/
    └── args/                 # CLI argument parsing
        ├── msb.rs            # Main CLI commands
        ├── msbrun.rs         # Run command
        └── msbserver.rs      # Server command
```

### microsandbox-utils/
**Purpose**: Common utilities and helpers
```
microsandbox-utils/
├── Cargo.toml
└── lib/
    ├── defaults.rs           # Default configurations
    ├── env.rs                # Environment utilities
    ├── log/                  # Logging configuration
    ├── path.rs               # Path utilities
    └── runtime/              # Runtime utilities
```

## MCP Server (Python)

### mcp-server/
**Purpose**: Model Context Protocol adapter for AI integration
```
mcp-server/
├── README.md                 # MCP server documentation
├── requirements.txt          # Python dependencies
├── setup.py                  # Package configuration
├── mcp_server/
│   ├── __init__.py
│   ├── main.py               # Server entry point
│   └── server.py             # MCP protocol implementation
├── microsandbox_wrapper/
│   ├── __init__.py
│   ├── config.py             # Configuration management
│   ├── exceptions.py         # Error handling
│   ├── models.py             # Data models
│   ├── resource_manager.py   # Resource management
│   ├── session_manager.py    # Session lifecycle
│   └── wrapper.py            # Main wrapper logic
├── tests/                    # Unit tests
├── integration_tests/        # Integration tests
└── examples/                 # Usage examples
```

## SDK Structure

### Multi-Language SDK Support
```
sdk/
├── README.md                 # SDK overview
├── python/                   # Python SDK (primary)
│   ├── microsandbox/         # Package source
│   ├── examples/             # Usage examples
│   └── README.md
├── javascript/               # Node.js/JavaScript SDK
├── rust/                     # Rust SDK
├── go/                       # Go SDK
├── java/                     # Java SDK
└── [20+ other languages]     # Additional language support
```

## Documentation Structure

### docs/
```
docs/
├── index.md                  # Documentation home
├── guides/                   # User guides
│   ├── getting-started.md
│   ├── architecture.md
│   ├── sandboxes.md
│   ├── projects.md
│   └── mcp.md
├── references/               # API references
│   ├── api.md
│   ├── cli.md
│   ├── python-sdk.md
│   └── rust-sdk.md
└── dev/                      # Developer documentation
    ├── DEVELOPMENT.md
    ├── DEVELOPMENT_QUICKSTART.md
    ├── PROJECTS.md
    └── TROUBLESHOOTING.md
```

## Configuration Files

### Build and Development
- **Cargo.toml**: Workspace configuration with shared dependencies
- **Makefile**: Primary build system with dev-install target
- **rust-toolchain.toml**: Rust version specification
- **.rustfmt.toml**: Code formatting rules
- **deny.toml**: Dependency security and licensing checks

### Project Configuration
- **Sandboxfile**: Project-level sandbox definitions (YAML)
- **.env**: Environment variables for development
- **test-python-local.toml**: Local testing configuration

### CI/CD and Quality
- **.github/**: GitHub Actions workflows
- **.pre-commit-config.yaml**: Pre-commit hooks
- **release-please-config.json**: Automated release configuration

## Key Directories

### Build Artifacts
- **build/**: Compiled binaries and libraries
- **target/**: Cargo build artifacts
- **tmp-build/**: Temporary build files

### Runtime Data
- **.menv/**: Project sandbox environments
- **test_data/**: Test fixtures and data
- **logs/**: Application logs

### Scripts and Tools
- **scripts/**: Build and development scripts
  - **aliases/**: Command aliases (msr, msx, msi)
  - **build_libkrun.sh**: libkrun compilation
  - **setup_dev_env.sh**: Development environment setup

## Naming Conventions

### Rust Code
- **Crates**: kebab-case (microsandbox-core)
- **Modules**: snake_case (session_manager)
- **Types**: PascalCase (SandboxConfig)
- **Functions**: snake_case (create_sandbox)

### Python Code
- **Modules**: snake_case (microsandbox_wrapper)
- **Classes**: PascalCase (SessionManager)
- **Functions**: snake_case (execute_code)
- **Constants**: UPPER_SNAKE_CASE (MAX_SESSIONS)

### File Organization
- **Configuration**: Environment variables prefixed with MSB_
- **Binaries**: Installed to ~/.local/bin/
- **Libraries**: Installed to ~/.local/lib/
- **Documentation**: Markdown files with clear hierarchical structure

## Development Workflow

### Code Organization Principles
1. **Separation of Concerns**: Each crate has a specific responsibility
2. **Layered Architecture**: Core → Server → Portal → CLI
3. **Shared Utilities**: Common functionality in microsandbox-utils
4. **Language-Specific SDKs**: Independent SDK implementations
5. **Comprehensive Documentation**: Both user and developer focused

### Integration Points
- **HTTP API**: microsandbox-server exposes REST endpoints
- **MCP Protocol**: mcp-server provides AI integration layer
- **CLI Interface**: microsandbox-cli provides user commands
- **SDK Integration**: Language-specific SDKs call HTTP API
- **Database**: SQLite for persistent state management