# Requirements Document

## Introduction

基于已实现的 Python MCP wrapper，需要创建一个支持 HTTP streamable transport 模式的 MCP server。该 server 应该是一个很薄的协议层，主要负责：
1. 实现 MCP 协议的 HTTP streamable transport
2. 将 MCP 协议消息转换为 wrapper 调用
3. 管理 wrapper 的生命周期，确保与 MCP server 一致

现有的 wrapper 已经实现了会话管理、资源管理、错误处理等复杂逻辑，MCP server 只需要作为协议适配层。

## Requirements

### Requirement 1: MCP 协议实现

**User Story:** 作为 MCP 客户端，我希望通过标准的 MCP HTTP streamable transport 协议与 microsandbox 服务交互，以便使用标准的 MCP 工具和客户端。

#### Acceptance Criteria

1. WHEN 客户端发送 MCP 请求时 THEN server 应该正确解析 JSON-RPC 2.0 格式的消息
2. WHEN 处理工具调用时 THEN server 应该支持 `tools/call` 方法
3. WHEN 处理工具列表请求时 THEN server 应该支持 `tools/list` 方法
4. WHEN 响应客户端时 THEN server 应该返回符合 MCP 协议规范的 JSON-RPC 响应
5. WHEN 使用 HTTP streamable transport 时 THEN server 应该支持标准的 HTTP 请求-响应模式

### Requirement 2: Wrapper 集成

**User Story:** 作为开发者，我希望 MCP server 能够无缝集成现有的 wrapper，以便复用已有的会话管理和资源管理功能。

#### Acceptance Criteria

1. WHEN MCP server 启动时 THEN 应该初始化并启动 wrapper 实例
2. WHEN MCP server 关闭时 THEN 应该优雅地关闭 wrapper 实例
3. WHEN 接收到工具调用时 THEN 应该调用 wrapper 的对应方法
4. WHEN wrapper 抛出异常时 THEN 应该转换为符合 MCP 协议的错误响应
5. WHEN wrapper 返回结果时 THEN 应该转换为符合 MCP 协议的成功响应

### Requirement 3: 工具接口映射

**User Story:** 作为 MCP 客户端，我希望能够调用 microsandbox 的核心功能，包括代码执行、命令执行和会话管理。

#### Acceptance Criteria

1. WHEN 调用 `execute_code` 工具时 THEN 应该映射到 wrapper 的 `execute_code` 方法
2. WHEN 调用 `execute_command` 工具时 THEN 应该映射到 wrapper 的 `execute_command` 方法
3. WHEN 调用 `get_sessions` 工具时 THEN 应该映射到 wrapper 的 `get_sessions` 方法
4. WHEN 调用 `stop_session` 工具时 THEN 应该映射到 wrapper 的 `stop_session` 方法
5. WHEN 调用 `get_volume_path` 工具时 THEN 应该映射到 wrapper 的 `get_volume_mappings` 方法

### Requirement 4: 错误处理转换

**User Story:** 作为 MCP 客户端，我希望接收到标准化的 MCP 错误响应，以便统一处理各种异常情况。

#### Acceptance Criteria

1. WHEN wrapper 抛出 `MicrosandboxWrapperError` 时 THEN 应该转换为 MCP 的 `InternalError`
2. WHEN wrapper 抛出 `ResourceLimitError` 时 THEN 应该转换为 MCP 的 `InvalidRequest` 错误
3. WHEN wrapper 抛出 `ConfigurationError` 时 THEN 应该转换为 MCP 的 `InternalError`
4. WHEN 工具参数无效时 THEN 应该返回 MCP 的 `InvalidParams` 错误
5. WHEN 工具不存在时 THEN 应该返回 MCP 的 `MethodNotFound` 错误

### Requirement 5: HTTP Transport 实现

**User Story:** 作为部署者，我希望 MCP server 支持标准的 HTTP streamable transport，以便与各种 MCP 客户端兼容。

#### Acceptance Criteria

1. WHEN 客户端发送 POST 请求时 THEN server 应该处理 JSON-RPC 消息并返回响应
2. WHEN 客户端发送 GET 请求时 THEN server 应该返回服务器状态信息
3. WHEN 工具参数包含 session_id 时 THEN server 应该将其透传给 wrapper
5. WHEN 需要 CORS 支持时 THEN server 应该正确处理跨域请求

### Requirement 6: 配置管理

**User Story:** 作为部署者，我希望能够通过环境变量配置 MCP server，以便在不同环境中灵活部署。

#### Acceptance Criteria

1. WHEN 设置 `MCP_SERVER_HOST` 环境变量时 THEN server 应该绑定到指定的主机地址
2. WHEN 设置 `MCP_SERVER_PORT` 环境变量时 THEN server 应该监听指定的端口
3. WHEN 设置 `MCP_ENABLE_CORS` 环境变量时 THEN server 应该启用 CORS 支持
4. WHEN 未设置配置时 THEN server 应该使用合理的默认值

### Requirement 7: 生命周期管理

**User Story:** 作为系统管理员，我希望 MCP server 能够优雅地启动和关闭，确保资源正确清理。

#### Acceptance Criteria

1. WHEN server 启动时 THEN 应该先启动 wrapper 再开始接受请求
2. WHEN server 接收到关闭信号时 THEN 应该停止接受新请求
3. WHEN server 关闭时 THEN 应该等待现有请求完成处理
4. WHEN server 关闭时 THEN 应该优雅地关闭 wrapper 实例
5. WHEN 启动失败时 THEN 应该记录错误并正确退出