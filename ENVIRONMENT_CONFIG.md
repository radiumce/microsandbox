# Environment Configuration Guide

This guide covers environment variable configuration for the microsandbox MCP server, particularly for the simplified interface features.

## Core Configuration

### MSB_SHARED_VOLUME_PATH

**Description:** Host directory path to share with sandbox containers

**Default:** None (shared volume disabled)

**Example:**
```bash
export MSB_SHARED_VOLUME_PATH="/Users/username/sandbox-shared"
```

**Usage:** When set, this directory will be automatically mounted in all sandbox containers at the guest path (see `MSB_SHARED_VOLUME_GUEST_PATH`). This allows easy file sharing between your host system and sandbox environments.

### MSB_SHARED_VOLUME_GUEST_PATH

**Description:** Path inside sandbox containers where the shared volume is mounted

**Default:** `/shared`

**Example:**
```bash
export MSB_SHARED_VOLUME_GUEST_PATH="/workspace"
```

**Usage:** This is the path where the shared volume appears inside sandbox containers. Code running in sandboxes can read/write files at this location.

## Session Management

### MSB_SESSION_TIMEOUT_SECONDS

**Description:** Automatic session timeout in seconds

**Default:** `1800` (30 minutes)

**Range:** 60 - 86400 seconds (1 minute to 24 hours)

**Example:**
```bash
export MSB_SESSION_TIMEOUT_SECONDS=3600  # 1 hour
```

**Usage:** Sessions that are idle for this duration will be automatically stopped and cleaned up to free resources.

### MSB_MAX_SESSIONS

**Description:** Maximum number of concurrent sessions

**Default:** `10`

**Example:**
```bash
export MSB_MAX_SESSIONS=5
```

**Usage:** Limits the total number of active sandbox sessions to prevent resource exhaustion. New session requests will be rejected when this limit is reached.

## Default Settings

### MSB_DEFAULT_FLAVOR

**Description:** Default resource flavor when not specified

**Default:** `small`

**Valid Values:** `small`, `medium`, `large`

**Example:**
```bash
export MSB_DEFAULT_FLAVOR=medium
```

**Usage:** When tools are called without specifying a `flavor` parameter, this default will be used.

### MSB_DEFAULT_TEMPLATE

**Description:** Default sandbox template when not specified

**Default:** `python`

**Valid Values:** `python`, `node`

**Example:**
```bash
export MSB_DEFAULT_TEMPLATE=node
```

**Usage:** When tools are called without specifying a `template` parameter, this default will be used.

## Complete Configuration Example

Here's a complete example configuration for a development environment:

```bash
#!/bin/bash
# microsandbox environment configuration

# Shared volume configuration
export MSB_SHARED_VOLUME_PATH="/Users/$(whoami)/microsandbox-shared"
export MSB_SHARED_VOLUME_GUEST_PATH="/shared"

# Session management
export MSB_SESSION_TIMEOUT_SECONDS=2700  # 45 minutes
export MSB_MAX_SESSIONS=8

# Default settings
export MSB_DEFAULT_FLAVOR=medium
export MSB_DEFAULT_TEMPLATE=python

# Create shared directory if it doesn't exist
mkdir -p "$MSB_SHARED_VOLUME_PATH"

echo "Microsandbox environment configured:"
echo "  Shared volume: $MSB_SHARED_VOLUME_PATH -> $MSB_SHARED_VOLUME_GUEST_PATH"
echo "  Session timeout: $MSB_SESSION_TIMEOUT_SECONDS seconds"
echo "  Max sessions: $MSB_MAX_SESSIONS"
echo "  Default flavor: $MSB_DEFAULT_FLAVOR"
echo "  Default template: $MSB_DEFAULT_TEMPLATE"
```

## Docker Compose Configuration

If you're running microsandbox with Docker Compose, you can set these environment variables in your `docker-compose.yml`:

```yaml
version: '3.8'
services:
  microsandbox:
    image: microsandbox/server:latest
    ports:
      - "5555:5555"
    environment:
      - MSB_SHARED_VOLUME_PATH=/host-shared
      - MSB_SHARED_VOLUME_GUEST_PATH=/shared
      - MSB_SESSION_TIMEOUT_SECONDS=3600
      - MSB_MAX_SESSIONS=10
      - MSB_DEFAULT_FLAVOR=medium
      - MSB_DEFAULT_TEMPLATE=python
    volumes:
      - ./shared:/host-shared
      - /var/run/docker.sock:/var/run/docker.sock
```

## Validation

The microsandbox server validates configuration on startup. Common validation errors:

- **Shared volume path doesn't exist:** Create the directory or update the path
- **Invalid timeout range:** Must be between 60 and 86400 seconds
- **Invalid flavor:** Must be `small`, `medium`, or `large`
- **Invalid template:** Must be `python` or `node`
- **Guest path not absolute:** Must start with `/`

## Environment Setup Script

Save this as `setup-microsandbox-env.sh`:

```bash
#!/bin/bash
set -e

# Configuration
SHARED_DIR="$HOME/microsandbox-shared"
TIMEOUT=1800
MAX_SESSIONS=10
DEFAULT_FLAVOR=small
DEFAULT_TEMPLATE=python

# Create shared directory
echo "Creating shared directory: $SHARED_DIR"
mkdir -p "$SHARED_DIR"

# Set environment variables
export MSB_SHARED_VOLUME_PATH="$SHARED_DIR"
export MSB_SHARED_VOLUME_GUEST_PATH="/shared"
export MSB_SESSION_TIMEOUT_SECONDS=$TIMEOUT
export MSB_MAX_SESSIONS=$MAX_SESSIONS
export MSB_DEFAULT_FLAVOR=$DEFAULT_FLAVOR
export MSB_DEFAULT_TEMPLATE=$DEFAULT_TEMPLATE

# Add to shell profile for persistence
SHELL_RC="$HOME/.$(basename $SHELL)rc"
echo "Adding configuration to $SHELL_RC"

cat >> "$SHELL_RC" << EOF

# Microsandbox configuration
export MSB_SHARED_VOLUME_PATH="$SHARED_DIR"
export MSB_SHARED_VOLUME_GUEST_PATH="/shared"
export MSB_SESSION_TIMEOUT_SECONDS=$TIMEOUT
export MSB_MAX_SESSIONS=$MAX_SESSIONS
export MSB_DEFAULT_FLAVOR=$DEFAULT_FLAVOR
export MSB_DEFAULT_TEMPLATE=$DEFAULT_TEMPLATE
EOF

echo "Environment configured successfully!"
echo "Run 'source $SHELL_RC' or restart your shell to apply changes."
```

Make it executable and run:

```bash
chmod +x setup-microsandbox-env.sh
./setup-microsandbox-env.sh
```