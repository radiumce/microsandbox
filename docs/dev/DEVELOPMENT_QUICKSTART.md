# 🚀 Microsandbox 开发快速入门

本文档为开发者提供最简化的 microsandbox 源码编译和开发环境搭建指南。

## 📋 系统要求

### macOS
- **硬件**: Apple Silicon (M1/M2/M3/M4)
- **软件**: 
  - Homebrew
  - Rust toolchain
  - Xcode Command Line Tools

### Linux
- **硬件**: x86_64 或 ARM64
- **软件**:
  - KVM 虚拟化支持
  - 基本开发工具 (gcc, make, git 等)
  - Rust toolchain

## ⚡ 一键安装 (推荐)

```bash
# 克隆项目
git clone https://github.com/microsandbox/microsandbox.git
cd microsandbox

# 一键设置开发环境并安装
make dev-install
```

这个命令会自动：
1. 检查系统依赖
2. 安装必要的工具 (krunvm, pyelftools 等)
3. 下载预编译的 libkrun 库
4. 编译 microsandbox
5. 安装到 `~/.local/bin`
6. 配置环境变量

## 🔧 分步安装

如果你想了解每个步骤或遇到问题，可以分步执行：

### 1. 设置开发环境
```bash
make dev-setup
```

### 2. 编译项目
```bash
make build
```

### 3. 安装
```bash
make install
```

## 🧪 验证安装

```bash
# 重启终端或执行
source ~/.zshrc  # 或 ~/.bashrc

# 检查版本
msb --version

# 启动服务器
msb server start --dev --detach

# 拉取测试镜像
msb pull microsandbox/python

# 运行测试
msx python -- -c "print('Hello from microsandbox!')"
```

## 🛠️ 开发工作流

### 日常开发
```bash
# 修改代码后重新编译
make build

# 安装更新
make install

# 清理构建产物
make clean
```

### 调试模式
```bash
# 编译调试版本
make DEBUG=1 build
make DEBUG=1 install
```

### 完全清理
```bash
# 清理所有构建产物和安装文件
make dev-clean
```

## 🔍 故障排除

### 常见问题

#### 1. krunvm 未找到 (macOS)
```bash
brew tap slp/krun
brew install krunvm
```

#### 2. pyelftools 缺失
```bash
pip3 install --break-system-packages pyelftools
```

#### 3. 权限问题
确保 `~/.local/bin` 在你的 PATH 中：
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

#### 4. 库文件找不到
设置库路径：
```bash
# macOS
echo 'export DYLD_LIBRARY_PATH="$HOME/.local/lib:$DYLD_LIBRARY_PATH"' >> ~/.zshrc

# Linux  
echo 'export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"' >> ~/.zshrc
```

### 获取帮助
```bash
# 查看所有可用命令
make help

# 查看详细的构建选项
make help | grep -A 20 "Build Modes"
```

## 📚 进阶开发

### 自定义构建选项
```bash
# 启用 LTO 优化 (更小的二进制文件)
make LTO=1 build

# 强制重新构建 libkrun
make clean
make FORCE_BUILD=1 build
```

### 修改 libkrun
如果你需要修改 libkrun 源码：
```bash
# 删除预编译库，强制从源码构建
rm -rf build/libkrun* build/libkrunfw*
make build
```

### 贡献代码
1. Fork 项目
2. 创建功能分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 创建 Pull Request

## 🎯 核心改进

相比原来的构建过程，新的开发环境具有以下优势：

### ✅ 自动化程度高
- **原来**: 需要手动安装 krunvm、pyelftools、创建配置文件
- **现在**: 一个命令自动处理所有依赖

### ✅ 智能依赖管理
- **原来**: 总是尝试从源码构建 libkrun，经常失败
- **现在**: 优先使用预编译库，失败时才回退到源码构建

### ✅ 错误处理完善
- **原来**: 构建失败时错误信息不清晰
- **现在**: 详细的错误提示和解决建议

### ✅ 开发者友好
- **原来**: 需要阅读复杂的文档才能开始开发
- **现在**: 一个命令即可开始开发

## 📞 支持

如果遇到问题：
1. 查看 [故障排除](#故障排除) 部分
2. 检查 [GitHub Issues](https://github.com/microsandbox/microsandbox/issues)
3. 创建新的 Issue 并提供详细信息

---

**Happy Coding! 🎉**