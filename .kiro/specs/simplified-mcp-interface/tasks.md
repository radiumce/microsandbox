# Implementation Plan

- [x] 1. 创建核心数据结构和错误类型
  - 定义SandboxFlavor枚举和相关方法
  - 实现SimplifiedMcpError错误类型
  - 创建请求和响应数据结构
  - _Requirements: 1.3, 1.4, 6.1, 6.2_

- [x] 2. 实现Configuration Manager
  - 创建ConfigurationManager结构体
  - 实现环境变量解析逻辑
  - 添加默认值处理和配置验证
  - 实现共享卷路径配置功能
  - _Requirements: 1.5, 5.1_

- [x] 3. 实现Session Manager基础功能
  - 创建SessionManager和SessionInfo结构体
  - 实现session创建和状态管理
  - 添加session存储和检索功能
  - 实现session访问时间更新机制
  - _Requirements: 2.1, 2.2, 3.1, 3.2_

- [x] 4. 实现Resource Manager
  - 创建ResourceManager和ResourceAllocation结构体
  - 实现端口分配和释放逻辑
  - 添加资源限制检查功能
  - 集成SandboxFlavor配置到资源分配
  - _Requirements: 1.3, 5.2_

- [x] 5. 实现语言到镜像映射
  - 创建LanguageMapping结构体
  - 定义支持的语言和对应镜像映射
  - 实现语言验证逻辑
  - _Requirements: 1.1, 1.2_

- [x] 6. 实现简化的MCP工具接口
- [x] 6.1 实现execute_code工具
  - 创建execute_code工具的JSON schema定义
  - 实现代码执行请求处理逻辑
  - 集成session管理和自动创建功能
  - 添加执行结果格式化
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 4.1, 4.3_

- [x] 6.2 实现execute_command工具
  - 创建execute_command工具的JSON schema定义
  - 实现命令执行请求处理逻辑
  - 集成session管理功能
  - 添加命令执行结果处理
  - _Requirements: 2.1, 2.2, 4.2, 4.5_

- [x] 6.3 实现get_sessions工具
  - 创建get_sessions工具的JSON schema定义
  - 实现session列表查询功能
  - 添加session状态信息格式化
  - _Requirements: 3.1, 3.2_

- [x] 6.4 实现stop_session工具
  - 创建stop_session工具的JSON schema定义
  - 实现session停止功能
  - 添加资源清理逻辑
  - _Requirements: 3.1, 3.2_

- [x] 6.5 实现get_volume_path工具
  - 创建get_volume_path工具的JSON schema定义
  - 实现共享卷路径查询功能
  - 添加路径可用性检查
  - _Requirements: 1.5_

- [x] 7. 实现自动沙箱创建逻辑
  - 集成现有的sandbox_start_impl功能
  - 实现按需沙箱创建机制
  - 添加沙箱配置自动生成
  - 实现共享卷自动映射
  - _Requirements: 2.1, 2.2, 2.3, 1.5_

- [x] 8. 实现session超时和清理机制
  - 创建后台清理任务
  - 实现session超时检测
  - 添加自动资源释放功能
  - 集成沙箱停止逻辑
  - _Requirements: 3.4, 5.1, 5.4_

- [x] 9. 更新MCP handler集成
  - 修改现有的mcp.rs模块
  - 集成新的简化工具接口
  - 更新工具列表和描述
  - 实现新的工具调用路由
  - _Requirements: 1.1, 1.2, 4.1, 4.2_

- [x] 10. 实现错误处理和用户友好消息
  - 添加详细的错误信息格式化
  - 实现错误恢复建议生成
  - 集成到所有工具接口中
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 11. 编写单元测试
  - 为SessionManager编写测试
  - 为ResourceManager编写测试
  - 为ConfigurationManager编写测试
  - 为工具接口编写测试
  - _Requirements: 所有需求的验证_

- [x] 12. 编写集成测试
  - 创建端到端测试场景
  - 测试session生命周期管理
  - 验证资源清理功能
  - 测试错误处理流程
  - _Requirements: 所有需求的集成验证_

- [x] 13. 更新文档和示例
  - 更新MCP.md文档
  - 添加新工具接口的使用示例
  - 创建环境变量配置指南
  - 编写故障排除指南
  - _Requirements: 用户体验改进_