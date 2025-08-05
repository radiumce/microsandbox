# Implementation Plan

- [x] 1. 创建项目结构和基础模块
  - 在 `mcp-server` 目录下创建 `microsandbox_wrapper` Python 包目录结构
  - 设置 `mcp-server/microsandbox_wrapper/__init__.py` 文件和基本导入
  - 创建 `mcp-server/microsandbox_wrapper/exceptions.py` 模块定义所有异常类型
  - 创建 `mcp-server/microsandbox_wrapper/models.py` 模块定义数据模型（SandboxFlavor, ExecutionResult, SessionInfo 等）
  - _Requirements: 1.1, 6.1_

- [x] 2. 实现配置管理模块
  - 创建 `mcp-server/microsandbox_wrapper/config.py` 模块
  - 实现 WrapperConfig 数据类
  - 实现 from_env() 类方法解析环境变量
  - 添加 MSB_SHARED_VOLUME_PATH 的 JSON 数组解析逻辑
  - 实现配置验证和默认值处理
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 3. 实现会话管理核心功能
  - 创建 `mcp-server/microsandbox_wrapper/session_manager.py` 模块
  - 实现 ManagedSession 类的基础结构
  - 实现沙箱创建逻辑（根据 template 选择 PythonSandbox 或 NodeSandbox）
  - 实现会话状态管理和访问时间更新
  - 添加会话锁机制防止并发问题
  - _Requirements: 2.1, 2.2, 2.3, 3.1_

- [x] 4. 实现代码执行功能
  - 在 ManagedSession 中实现 execute_code 方法
  - 集成底层 microsandbox SDK 的代码执行功能
  - 实现执行超时控制
  - 添加执行时间统计
  - 实现 ExecutionResult 的构建和返回
  - _Requirements: 1.1, 5.1, 5.2_

- [x] 5. 实现命令执行功能
  - 在 ManagedSession 中实现 execute_command 方法
  - 集成底层 microsandbox SDK 的命令执行功能
  - 实现命令超时控制
  - 添加命令执行时间统计
  - 实现 CommandResult 的构建和返回
  - _Requirements: 1.1, 5.1, 5.2_

- [x] 6. 实现 SessionManager 类
  - 创建 SessionManager 类的基础结构
  - 实现会话存储和检索功能（使用字典存储）
  - 实现 get_or_create_session 方法
  - 实现 touch_session 和 stop_session 方法
  - 实现 get_sessions 方法返回会话信息列表
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 7. 实现会话超时和清理机制
  - 在 SessionManager 中实现后台清理循环
  - 实现过期会话检测逻辑
  - 实现会话清理和资源释放
  - 添加清理任务的启动和停止控制
  - 实现优雅的会话停止流程
  - _Requirements: 2.4, 4.4_

- [x] 8. 实现资源管理器
  - 创建 `mcp-server/microsandbox_wrapper/resource_manager.py` 模块
  - 实现 ResourceManager 类的基础结构
  - 实现资源限制检查功能（最大并发会话数、内存限制）
  - 实现资源使用统计功能
  - 集成与 SessionManager 的交互
  - _Requirements: 4.1, 4.2, 4.5_

- [x] 9. 实现孤儿沙箱检测和清理
  - 在 ResourceManager 中实现孤儿沙箱检测逻辑
  - 实现获取运行中沙箱列表的功能（调用底层 API）
  - 实现孤儿沙箱清理逻辑
  - 添加后台孤儿清理循环任务
  - 实现清理日志和统计
  - _Requirements: 4.6, 4.7_

- [x] 10. 实现主封装接口类
  - 创建 `mcp-server/microsandbox_wrapper/wrapper.py` 模块
  - 实现 MicrosandboxWrapper 类的基础结构
  - 集成 SessionManager 和 ResourceManager
  - 实现 execute_code 方法（调用会话管理器）
  - 实现 execute_command 方法（调用会话管理器）
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 11. 实现封装接口的辅助方法
  - 实现 get_sessions 方法
  - 实现 stop_session 方法
  - 实现 get_volume_mappings 方法
  - 实现 get_resource_stats 方法
  - 实现 cleanup_orphan_sandboxes 方法
  - _Requirements: 2.3, 4.3, 4.5_

- [x] 12. 实现统一错误处理
  - 完善 exceptions.py 中的所有异常类型
  - 在各个模块中添加适当的异常处理
  - 实现错误信息的标准化格式
  - 添加错误恢复建议的生成逻辑
  - 实现错误日志记录
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 13. 实现日志和监控支持
  - 创建 `mcp-server/microsandbox_wrapper/logging_config.py` 模块
  - 配置标准的 Python logging
  - 在关键操作点添加日志记录
  - 实现性能指标收集（执行时间、资源使用等）
  - 添加调试级别的详细日志
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 14. 实现后台任务管理
  - 在 SessionManager 和 ResourceManager 中实现后台任务的启动和停止
  - 确保后台任务可以被上层 MCP server 控制
  - 实现优雅关闭时的资源清理（由上层调用）
  - 添加任务状态查询功能
  - 确保封装器本身是无状态的，状态由管理器维护
  - _Requirements: 5.1, 5.2, 4.4_

- [x] 15. 编写单元测试
- [x] 15.1 测试配置管理
  - 测试 WrapperConfig.from_env() 方法
  - 测试环境变量解析（包括 JSON 数组格式）
  - 测试配置验证和默认值
  - 测试 VolumeMapping.from_string() 方法
  - _Requirements: 7.1-7.5 的验证_

- [x] 15.2 测试会话管理
  - 测试 ManagedSession 的创建和状态管理
  - 测试会话超时和清理机制
  - 测试并发访问的安全性
  - 测试会话执行功能（mock 底层 SDK）
  - _Requirements: 2.1-2.4 的验证_

- [x] 15.3 测试资源管理
  - 测试资源限制检查
  - 测试资源使用统计
  - 测试孤儿沙箱检测逻辑（mock 底层 API）
  - 测试后台清理任务
  - _Requirements: 4.1-4.7 的验证_

- [x] 15.4 测试主封装接口
  - 测试 execute_code 和 execute_command 方法
  - 测试错误处理和异常传播
  - 测试会话复用逻辑
  - 测试超时控制
  - _Requirements: 1.1-1.5 的验证_

- [x] 16. 编写集成测试
- [x] 16.1 设置测试环境
  - 编写使用 start_msbserver_debug.sh 启动服务器的测试脚本
  - 配置测试环境变量
  - 创建测试用的共享卷目录
  - _Requirements: 端到端测试环境准备_

- [x] 16.2 端到端功能测试
  - 测试完整的代码执行流程（Python 和 Node 模板）
  - 测试完整的命令执行流程
  - 测试会话生命周期管理
  - 测试多卷映射功能
  - 测试资源清理验证
  - _Requirements: 所有功能需求的集成验证_

- [x] 16.3 错误场景测试
  - 测试配置错误处理
  - 测试孤儿沙箱清理
  - _Requirements: 6.1-6.5 的错误处理验证_

- [x] 17. 创建使用示例和文档
  - 创建基本使用示例（代码执行、命令执行）
  - 创建高级使用示例（会话管理、资源监控）
  - 编写 API 文档（docstring 和 README）
  - 创建配置指南（环境变量说明）
  - 编写故障排除指南
  - _Requirements: 用户体验改进_
