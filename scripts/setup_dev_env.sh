#!/bin/bash

# setup_dev_env.sh
# 自动化开发环境设置脚本，简化 microsandbox 的源码编译过程

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测操作系统和架构
detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    case $ARCH in
        x86_64) ARCH="x86_64" ;;
        arm64|aarch64) ARCH="arm64" ;;
        *) error "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    
    case $OS in
        darwin|linux) ;;
        *) error "Unsupported OS: $OS"; exit 1 ;;
    esac
    
    info "Detected platform: $OS-$ARCH"
}

# 检查必要的工具
check_prerequisites() {
    info "Checking prerequisites..."
    
    # 检查 Rust
    if ! command -v rustc &> /dev/null; then
        error "Rust is not installed. Please install Rust first: https://rustup.rs/"
        exit 1
    fi
    
    # 检查 make
    if ! command -v make &> /dev/null; then
        error "make is not installed"
        exit 1
    fi
    
    # macOS 特定检查
    if [[ "$OS" == "darwin" ]]; then
        # 检查 Homebrew
        if ! command -v brew &> /dev/null; then
            error "Homebrew is not installed. Please install it first: https://brew.sh/"
            exit 1
        fi
        
        # 检查 krunvm
        if ! command -v krunvm &> /dev/null; then
            info "Installing krunvm..."
            brew tap slp/krun
            brew install krunvm
        fi
        
        # 检查 pyelftools
        if ! python3 -c "import elftools" &> /dev/null; then
            info "Installing pyelftools..."
            pip3 install --break-system-packages pyelftools || pip3 install --user pyelftools
        fi
    fi
    
    # Linux 特定检查
    if [[ "$OS" == "linux" ]]; then
        # 检查 KVM
        if [[ ! -e /dev/kvm ]]; then
            error "KVM is not available. Please enable KVM virtualization."
            exit 1
        fi
        
        # 检查必要的包
        local missing_packages=""
        for pkg in patchelf bc gcc flex bison git python3 curl; do
            if ! command -v $pkg &> /dev/null; then
                missing_packages="$missing_packages $pkg"
            fi
        done
        
        if [[ -n "$missing_packages" ]]; then
            error "Missing packages:$missing_packages"
            info "Please install them using your package manager"
            exit 1
        fi
    fi
}

# 下载预编译的 libkrun 库
download_prebuilt_libs() {
    info "Downloading prebuilt libkrun libraries..."
    
    local version="0.2.6"
    local platform_suffix
    
    if [[ "$OS" == "darwin" ]]; then
        platform_suffix="darwin-arm64"
    else
        platform_suffix="linux-$ARCH"
    fi
    
    local archive_name="microsandbox-${version}-${platform_suffix}.tar.gz"
    local download_url="https://github.com/microsandbox/microsandbox/releases/download/microsandbox-v${version}/${archive_name}"
    local temp_dir="/tmp/microsandbox-libs"
    
    # 创建临时目录
    mkdir -p "$temp_dir"
    cd "$temp_dir"
    
    # 下载并解压
    info "Downloading from: $download_url"
    curl -L -o "$archive_name" "$download_url" || {
        error "Failed to download prebuilt libraries"
        exit 1
    }
    
    tar -xzf "$archive_name" || {
        error "Failed to extract archive"
        exit 1
    }
    
    # 复制库文件到项目构建目录
    local extract_dir="microsandbox-${version}-${platform_suffix}"
    local project_build_dir="$(pwd)/../../build"
    
    mkdir -p "$project_build_dir"
    
    if [[ "$OS" == "darwin" ]]; then
        cp "$extract_dir/libkrun.1.dylib" "$project_build_dir/"
        cp "$extract_dir/libkrunfw.4.dylib" "$project_build_dir/"
        
        cd "$project_build_dir"
        ln -sf libkrun.1.dylib libkrun.dylib
        ln -sf libkrunfw.4.dylib libkrunfw.dylib
    else
        cp "$extract_dir"/*.so.* "$project_build_dir/"
        
        cd "$project_build_dir"
        ln -sf libkrun.so.* libkrun.so
        ln -sf libkrunfw.so.* libkrunfw.so
    fi
    
    info "Prebuilt libraries installed to: $project_build_dir"
    
    # 清理临时文件
    rm -rf "$temp_dir"
}

# 设置容器配置（仅 macOS）
setup_container_config() {
    if [[ "$OS" != "darwin" ]]; then
        return
    fi
    
    info "Setting up container configuration for macOS..."
    
    local config_dir="/opt/homebrew/etc/containers"
    
    # 创建配置目录
    sudo mkdir -p "$config_dir"
    
    # 创建 registries.conf
    if [[ ! -f "$config_dir/registries.conf" ]]; then
        sudo tee "$config_dir/registries.conf" > /dev/null << 'EOF'
[registries.search]
registries = ['docker.io', 'registry.fedoraproject.org', 'quay.io', 'registry.access.redhat.com', 'registry.centos.org']

[registries.insecure]
registries = []

[registries.block]
registries = []
EOF
    fi
    
    # 创建 policy.json
    if [[ ! -f "$config_dir/policy.json" ]]; then
        sudo tee "$config_dir/policy.json" > /dev/null << 'EOF'
{
    "default": [
        {
            "type": "insecureAcceptAnything"
        }
    ],
    "transports":
        {
            "docker-daemon":
                {
                    "": [{"type":"insecureAcceptAnything"}]
                }
        }
}
EOF
    fi
}

# 设置环境变量
setup_environment() {
    info "Setting up environment variables..."
    
    local shell_rc=""
    if [[ -n "$ZSH_VERSION" ]]; then
        shell_rc="$HOME/.zshrc"
    elif [[ -n "$BASH_VERSION" ]]; then
        shell_rc="$HOME/.bashrc"
    else
        shell_rc="$HOME/.profile"
    fi
    
    # 添加 PATH
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$shell_rc" 2>/dev/null; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$shell_rc"
    fi
    
    # 添加库路径
    if [[ "$OS" == "darwin" ]]; then
        if ! grep -q 'export DYLD_LIBRARY_PATH="$HOME/.local/lib:$DYLD_LIBRARY_PATH"' "$shell_rc" 2>/dev/null; then
            echo 'export DYLD_LIBRARY_PATH="$HOME/.local/lib:$DYLD_LIBRARY_PATH"' >> "$shell_rc"
        fi
    else
        if ! grep -q 'export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"' "$shell_rc" 2>/dev/null; then
            echo 'export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"' >> "$shell_rc"
        fi
    fi
    
    # 设置当前会话的环境变量
    export PATH="$HOME/.local/bin:$PATH"
    if [[ "$OS" == "darwin" ]]; then
        export DYLD_LIBRARY_PATH="$HOME/.local/lib:$DYLD_LIBRARY_PATH"
    else
        export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"
    fi
    
    info "Environment variables added to: $shell_rc"
    warn "Please restart your shell or run: source $shell_rc"
}

# 主函数
main() {
    info "Setting up microsandbox development environment..."
    
    detect_platform
    check_prerequisites
    setup_container_config
    download_prebuilt_libs
    setup_environment
    
    info "Development environment setup complete!"
    info ""
    info "🎉 Next steps:"
    info "  1. Restart your shell or run: source ~/.zshrc (or ~/.bashrc)"
    info "  2. Build the project: make build"
    info "  3. Install: make install"
    info "  4. Test: msb --version"
    info ""
    info "💡 Or use the all-in-one command: make dev-install"
}

# 运行主函数
main "$@"