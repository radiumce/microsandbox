# MCP Server 启动脚本总结

经过简化和优化，现在只保留一个综合性的开发启动脚本，既简洁又功能强大。

## 当前文件

### 启动脚本
- **`start_mcp_dev.sh`** - 统一启动脚本
  - 开发友好的默认配置
  - 支持环境变量灵活配置，可用于开发和生产
  - 自动健康检查和验证
  - 自动启动microsandbox服务器（如果需要）
  - 详细的日志和错误处理
  - 自动目录创建和环境设置

### 4. 配置文件
- **`.env.template`** - 环境变量配置模板（完整版）
- **`.env.example`** - 简化的配置示例
- **`.env.dev`** - 开发环境预配置
- **`.env.prod`** - 生产环境预配置
- 所有脚本都支持自动加载 `.env` 文件

### 5. 文档
- **`STARTUP_SCRIPTS.md`** - 启动脚本使用指南
- **`SCRIPT_SUMMARY.md`** - 本总结文档

## 环境变量配置详解

### MCP服务器核心配置
```bash
# 服务器绑定地址（默认：localhost）
export MCP_SERVER_HOST="localhost"

# 服务器端口（默认：8000）
export MCP_SERVER_PORT="8000"

# 启用CORS支持（默认：false）
export MCP_ENABLE_CORS="false"
```

### Microsandbox连接配置
```bash
# Microsandbox服务器地址（默认：http://127.0.0.1:5555）
export MSB_SERVER_URL="http://127.0.0.1:5555"

# API密钥（默认：无）
# export MSB_API_KEY="your-api-key"

# 连接超时（默认：30秒）
# export MSB_CONNECTION_TIMEOUT="30"

# 请求超时（默认：300秒）
# export MSB_REQUEST_TIMEOUT="300"
```

### 会话管理配置
```bash
# 最大并发会话数（默认：10）
# export MSB_MAX_SESSIONS="10"

# 会话超时时间（默认：1800秒，30分钟）
# export MSB_SESSION_TIMEOUT="1800"

# 默认资源规格（默认：small）
# export MSB_DEFAULT_FLAVOR="small"

# 会话清理间隔（默认：300秒，5分钟）
# export MSB_SESSION_CLEANUP_INTERVAL="300"
```

### 资源限制配置
```bash
# 最大总内存限制（默认：8192MB，8GB）
# export MSB_MAX_TOTAL_MEMORY_MB="8192"

# 最大CPU核心数（默认：8）
# export MSB_MAX_TOTAL_CPU_CORES="8"

# 最大执行时间（默认：300秒，5分钟）
# export MSB_MAX_EXECUTION_TIME="300"
```

### Volume映射配置
```bash
# 启用volume映射（默认：true）
# export MSB_ENABLE_VOLUME_MAPPING="true"

# Volume映射配置（JSON数组格式）
# 单个映射示例：
export MSB_SHARED_VOLUME_PATH='["/tmp/shared:/sandbox/shared"]'

# 多个映射示例：
export MSB_SHARED_VOLUME_PATH='[
  "/home/user/data:/data",
  "/tmp/output:/results", 
  "./config:/app/config"
]'
```

### 日志配置
```bash
# 日志级别（默认：INFO）
# export MSB_LOG_LEVEL="INFO"

# 日志格式（默认：json）
# export MSB_LOG_FORMAT="json"

# 日志文件路径（默认：stdout）
# export MSB_LOG_FILE="/var/log/mcp-server.log"
```

## 使用示例

### 1. 开发环境快速启动
```bash
# 最简单的开发启动（使用默认配置）
./start_mcp_dev.sh
```

### 2. 生产环境部署
```bash
# 使用环境变量配置生产环境
export MCP_SERVER_HOST=0.0.0.0
export MCP_SERVER_PORT=8080
export MSB_MAX_SESSIONS=50
export MSB_LOG_LEVEL=WARNING
export MSB_LOG_FORMAT=json
./start_mcp_dev.sh
```

### 3. 自定义配置
```bash
# 使用环境变量自定义配置
export MCP_SERVER_PORT=9000
export MSB_MAX_SESSIONS=20
export MSB_SHARED_VOLUME_PATH='["/data:/workspace"]'
./start_mcp_dev.sh
```

### 4. 使用.env文件（自动加载）
```bash
# 方法1: 使用示例文件
cp .env.example .env
# 编辑 .env 文件
./start_mcp_dev.sh

# 方法2: 使用开发专用配置
# 脚本会自动加载 .env.dev（如果存在）
./start_mcp_dev.sh

# 方法3: 本地覆盖
echo "MCP_SERVER_PORT=9000" > .env.local
./start_mcp_dev.sh
```

## 脚本特性

### 安全特性
- 配置验证和健康检查
- 权限检查和安全警告
- 优雅关闭和信号处理
- 进程管理和PID文件

### 便利特性
- 自动目录创建
- 依赖检查和安装
- 彩色日志输出
- 详细的错误信息

### 生产特性
- 系统资源监控
- 服务健康检查
- 日志文件管理
- 后台进程管理

## 故障排除

### 常见问题
1. **端口被占用**: 修改`MCP_SERVER_PORT`
2. **无法连接microsandbox**: 确保microsandbox服务器运行
3. **权限问题**: 运行`chmod +x *.sh`
4. **依赖缺失**: 运行`pip install -r requirements.txt`

### 调试模式
```bash
# 启用调试日志（默认已启用DEBUG模式）
./start_mcp_dev.sh

# 或可以设置环境变量调整日志级别
export MSB_LOG_LEVEL=INFO  # 或 WARNING, ERROR
./start_mcp_dev.sh
```

这套启动脚本提供了从开发到生产的完整解决方案，支持灵活的配置和多种部署场景。