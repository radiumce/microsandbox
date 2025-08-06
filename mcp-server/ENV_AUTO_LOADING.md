# 环境变量自动加载功能

MCP服务器启动脚本现在支持自动加载 `.env` 文件，无需手动执行 `set -a && source .env && set +a`。

## 自动加载机制

### 加载顺序
脚本会按以下顺序自动查找并加载环境变量文件：

1. **Profile-specific files** (配置文件特定)
   - `.env.dev` (开发环境)
   - `.env.prod` (生产环境)

2. **General file** (通用配置)
   - `.env`

3. **Local overrides** (本地覆盖)
   - `.env.local`

### 加载规则
- 后加载的文件会覆盖先加载的变量
- 已设置的环境变量不会被覆盖
- 所有变量都会自动导出为环境变量

## 使用方法

### 1. 开发环境
```bash
# 创建开发配置
cp .env.template .env.dev
# 编辑 .env.dev

# 启动（自动加载 .env.dev）
./start_mcp_dev.sh
```

### 2. 生产环境
```bash
# 创建生产配置
cp .env.template .env.prod
# 编辑 .env.prod

# 启动（自动加载 .env.prod）
# 可以先复制到 .env 或使用环境变量方式加载
cp .env.prod .env
./start_mcp_dev.sh
```

### 3. 通用配置
```bash
# 创建通用配置
cp .env.template .env
# 编辑 .env

# 启动（自动加载 .env）
./start_mcp_dev.sh
```

### 4. 本地覆盖
```bash
# 创建本地覆盖（不提交到版本控制）
echo "MCP_SERVER_PORT=9000" > .env.local
echo "MSB_LOG_LEVEL=DEBUG" >> .env.local

# 启动（会加载基础配置 + 本地覆盖）
./start_mcp_dev.sh
```

## 配置文件示例

### .env.dev (开发环境)
```bash
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8000
MCP_ENABLE_CORS=true
MSB_MAX_SESSIONS=5
MSB_LOG_LEVEL=DEBUG
MSB_SHARED_VOLUME_PATH=["./tmp/mcp-dev:/sandbox/shared"]
```

### .env.prod (生产环境)
```bash
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8080
MCP_ENABLE_CORS=false
MSB_MAX_SESSIONS=50
MSB_LOG_LEVEL=WARNING
MSB_SHARED_VOLUME_PATH=["/data/input:/sandbox/input", "/data/output:/sandbox/output"]
```

### .env.local (本地覆盖)
```bash
# 本地开发覆盖
MCP_SERVER_PORT=9000
MSB_LOG_LEVEL=DEBUG
MSB_SHARED_VOLUME_PATH=["./my-local-data:/workspace"]
```

## 优先级示例

假设你有以下文件：

**`.env`:**
```bash
MCP_SERVER_PORT=8000
MSB_LOG_LEVEL=INFO
MSB_MAX_SESSIONS=10
```

**`.env.local`:**
```bash
MCP_SERVER_PORT=9000
MSB_LOG_LEVEL=DEBUG
```

**最终结果：**
- `MCP_SERVER_PORT=9000` (被 .env.local 覆盖)
- `MSB_LOG_LEVEL=DEBUG` (被 .env.local 覆盖)
- `MSB_MAX_SESSIONS=10` (来自 .env)

## 调试加载过程

启动脚本会显示加载的配置文件：

```bash
$ ./start_mcp_dev.sh
[INFO] Loading environment variables from: .env.dev
[INFO] ✓ Environment variables loaded successfully
[INFO] Loading environment variables from: .env
[INFO] ✓ Environment variables loaded successfully
[INFO] Loading environment variables from: .env.local
[INFO] ✓ Environment variables loaded successfully
```

## 版本控制建议

### 应该提交的文件：
- `.env.template` - 完整的配置模板
- `.env.dev` - 开发环境默认配置
- `.env.prod` - 生产环境默认配置

### 不应该提交的文件：
- `.env` - 个人配置
- `.env.local` - 本地覆盖
- 包含敏感信息的配置文件

### .gitignore 建议：
```gitignore
# Environment files
.env
.env.local
.env.*.local

# Keep templates and configs
!.env.template
!.env.dev
!.env.prod
```

## 迁移指南

### 从手动加载迁移
如果你之前使用：
```bash
set -a && source .env && set +a
./start_mcp_server.sh
```

现在只需要：
```bash
./start_mcp_dev.sh
```

### 现有配置文件
现有的 `.env` 文件无需修改，会自动被加载。

## 故障排除

### 配置文件不生效
1. 检查文件名是否正确
2. 检查文件格式（`KEY=value`）
3. 查看启动日志中的加载信息

### 变量被意外覆盖
1. 检查多个配置文件中的重复变量
2. 记住加载顺序：profile → .env → .env.local
3. 使用 `env | grep MCP_` 查看最终变量值

### 权限问题
```bash
chmod 644 .env*
```

这个自动加载功能让配置管理更加便捷，无需每次手动加载环境变量文件。