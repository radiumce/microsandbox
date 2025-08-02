# Requirements Document

## Introduction

当前的MCP Server实现存在以下问题：
1. 工具接口过于复杂，需要用户手动指定镜像、内存、CPU、卷映射等配置参数
2. 缺乏session支持，无法在多次请求中复用同一个沙箱
3. 需要显式创建沙箱的步骤，增加了使用复杂度
4. AI调用时需要记住和管理沙箱的生命周期

本需求旨在简化MCP接口，提供按需创建沙箱、自动session管理和更简洁的工具接口。

## Requirements

### Requirement 1: 简化的工具接口

**User Story:** 作为AI助手，我希望能够通过简单的工具调用执行代码，而无需手动配置复杂的沙箱参数，以便更容易地为用户提供代码执行服务。

#### Acceptance Criteria

1. WHEN AI调用代码执行工具 THEN 系统应该自动选择合适的镜像和配置
2. WHEN 指定编程语言时 THEN 系统应该自动映射到对应的沙箱镜像（python -> microsandbox/python, javascript/node -> microsandbox/node）
3. WHEN 需要指定沙箱规格时 THEN 系统应该支持预设的flavor：small(1CPU 1GB)、medium(2CPU 2GB)、large(4CPU 4GB)
4. WHEN 未指定具体配置时 THEN 系统应该使用small规格作为默认值
5. WHEN 需要卷映射时 THEN 系统应该通过环境变量配置共享卷目录，所有沙箱自动映射到该目录
6. WHEN 工具调用成功时 THEN 系统应该返回执行结果和session ID

### Requirement 2: 自动按需沙箱创建

**User Story:** 作为AI助手，我希望在调用工具时能够自动创建所需的沙箱，而不需要显式的创建步骤，以便简化交互流程。

#### Acceptance Criteria

1. WHEN 调用代码执行工具且指定session不存在时 THEN 系统应该自动创建新的沙箱
2. WHEN 自动创建沙箱时 THEN 系统应该生成唯一的session ID
3. WHEN 沙箱创建成功时 THEN 系统应该在响应中包含session ID
4. WHEN 沙箱创建失败时 THEN 系统应该返回清晰的错误信息

### Requirement 3: Session管理支持

**User Story:** 作为AI助手，我希望能够在多次工具调用中复用同一个沙箱session，以便维持代码执行的上下文和状态。

#### Acceptance Criteria

1. WHEN 提供有效的session ID时 THEN 系统应该在现有沙箱中执行代码
2. WHEN session ID无效或沙箱已停止时 THEN 系统应该返回适当的错误信息
3. WHEN 未提供session ID时 THEN 系统应该创建新的session
4. WHEN session空闲超过配置时间时 THEN 系统应该自动清理沙箱资源

### Requirement 4: 分离的执行接口

**User Story:** 作为AI助手，我希望有清晰分离的接口来执行代码和命令，以便根据不同的使用场景选择合适的工具。

#### Acceptance Criteria

1. WHEN 需要执行代码时 THEN 系统应该提供专门的代码执行工具
2. WHEN 需要执行shell命令时 THEN 系统应该提供专门的命令执行工具
3. WHEN 执行代码时 THEN 系统应该支持多种编程语言的代码执行
4. WHEN 执行命令时 THEN 系统应该在沙箱环境中安全执行shell命令
5. WHEN 执行完成时 THEN 系统应该返回标准输出、错误输出和退出码

### Requirement 5: 自动资源管理

**User Story:** 作为系统管理员，我希望MCP Server能够自动管理沙箱资源，防止资源泄漏和无限制的资源消耗，以便维护系统稳定性。

#### Acceptance Criteria

1. WHEN 沙箱空闲时间超过阈值时 THEN 系统应该自动停止并清理沙箱
2. WHEN 系统资源不足时 THEN 系统应该拒绝创建新的沙箱并返回错误
3. WHEN 沙箱执行时间超过限制时 THEN 系统应该终止执行并返回超时错误
4. WHEN 服务关闭时 THEN 系统应该清理所有活跃的沙箱session

### Requirement 6: 改进的错误处理

**User Story:** 作为AI助手，我希望收到清晰和可操作的错误信息，以便能够向用户提供有用的反馈和建议。

#### Acceptance Criteria

1. WHEN 沙箱创建失败时 THEN 系统应该返回具体的失败原因
2. WHEN 代码执行出错时 THEN 系统应该区分编译错误、运行时错误和系统错误
3. WHEN session无效时 THEN 系统应该提供创建新session的建议
4. WHEN 资源不足时 THEN 系统应该提供等待或重试的建议