#!/bin/bash

# ci_build.sh
# CI/CD 环境下的构建脚本，专为自动化构建优化

set -e

# 环境变量
export RUST_BACKTRACE=1
export CARGO_TERM_COLOR=always

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检测平台
detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    case $ARCH in
        x86_64) ARCH="x86_64" ;;
        arm64|aarch64) ARCH="arm64" ;;
        *) error "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    
    info "Building for: $OS-$ARCH"
}

# 安装系统依赖
install_system_deps() {
    step "Installing system dependencies..."
    
    case $OS in
        linux)
            # 检测 Linux 发行版
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y patchelf bc libelf-dev gcc flex bison git python3 python3-pip curl
                pip3 install pyelftools
            elif command -v yum &> /dev/null; then
                sudo yum install -y patchelf bc elfutils-libelf-devel gcc flex bison git python3 python3-pip curl
                pip3 install pyelftools
            elif command -v pacman &> /dev/null; then
                sudo pacman -S --noconfirm patchelf bc libelf gcc flex bison git python3 python-pip curl
                pip3 install pyelftools
            else
                error "Unsupported Linux distribution"
                exit 1
            fi
            ;;
        darwin)
            # macOS 在 CI 中通常已经有基本工具
            if ! command -v brew &> /dev/null; then
                error "Homebrew not found on macOS"
                exit 1
            fi
            
            # 安装 krunvm
            brew tap slp/krun || true
            brew install krunvm || true
            
            # 安装 pyelftools
            pip3 install --break-system-packages pyelftools || pip3 install --user pyelftools
            ;;
        *)
            error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
}

# 下载预编译库
download_prebuilt_libs() {
    step "Downloading prebuilt libraries..."
    
    local version="0.2.6"
    local platform_suffix
    
    if [[ "$OS" == "darwin" ]]; then
        platform_suffix="darwin-arm64"
    else
        platform_suffix="linux-$ARCH"
    fi
    
    local archive_name="microsandbox-${version}-${platform_suffix}.tar.gz"
    local download_url="https://github.com/microsandbox/microsandbox/releases/download/microsandbox-v${version}/${archive_name}"
    
    mkdir -p build
    cd build
    
    info "Downloading: $download_url"
    curl -L -f -o "$archive_name" "$download_url" || {
        warn "Failed to download prebuilt libraries, will build from source"
        return 1
    }
    
    tar -xzf "$archive_name" || {
        warn "Failed to extract prebuilt libraries"
        return 1
    }
    
    local extract_dir="microsandbox-${version}-${platform_suffix}"
    
    if [[ "$OS" == "darwin" ]]; then
        cp "$extract_dir/libkrun.1.dylib" ./ || return 1
        cp "$extract_dir/libkrunfw.4.dylib" ./ || return 1
        ln -sf libkrun.1.dylib libkrun.dylib
        ln -sf libkrunfw.4.dylib libkrunfw.dylib
    else
        cp "$extract_dir"/*.so.* ./ || return 1
        ln -sf libkrun.so.* libkrun.so 2>/dev/null || true
        ln -sf libkrunfw.so.* libkrunfw.so 2>/dev/null || true
    fi
    
    rm -rf "$extract_dir" "$archive_name"
    cd ..
    
    info "Prebuilt libraries installed successfully"
    return 0
}

# 构建项目
build_project() {
    step "Building microsandbox..."
    
    # 设置构建环境
    if [[ "$OS" == "darwin" ]]; then
        export DYLD_LIBRARY_PATH="$(pwd)/build:$DYLD_LIBRARY_PATH"
        export RUSTFLAGS="-C link-args=-Wl,-rpath,@executable_path/../lib,-rpath,@executable_path"
    else
        export LD_LIBRARY_PATH="$(pwd)/build:$LD_LIBRARY_PATH"
        export RUSTFLAGS="-C link-args=-Wl,-rpath,\$ORIGIN/../lib,-rpath,\$ORIGIN"
    fi
    
    export LIBRARY_PATH="$(pwd)/build:$LIBRARY_PATH"
    
    # 构建所有组件
    info "Building msb..."
    cargo build --release --bin msb --features cli
    
    info "Building msbrun..."
    cargo build --release --bin msbrun --features cli
    
    info "Building msbserver..."
    cargo build --release --bin msbserver --features cli
    
    # 复制到 build 目录
    cp target/release/msb build/
    cp target/release/msbrun build/
    cp target/release/msbserver build/
    
    # 复制别名脚本
    cp scripts/aliases/* build/
    
    # macOS 需要代码签名
    if [[ "$OS" == "darwin" ]]; then
        codesign --entitlements microsandbox.entitlements --force -s - build/msbrun || true
    fi
    
    info "Build completed successfully"
}

# 运行测试
run_tests() {
    step "Running tests..."
    
    # 单元测试
    cargo test --all --release
    
    # 基本功能测试
    if [[ -f "build/msb" ]]; then
        ./build/msb --version
        info "Basic functionality test passed"
    fi
}

# 创建发布包
create_release_package() {
    if [[ -z "$1" ]]; then
        warn "No version specified, skipping package creation"
        return
    fi
    
    local version="$1"
    step "Creating release package for version $version..."
    
    local platform_suffix
    if [[ "$OS" == "darwin" ]]; then
        platform_suffix="darwin-arm64"
    else
        platform_suffix="linux-$ARCH"
    fi
    
    local package_name="microsandbox-${version}-${platform_suffix}"
    local package_dir="build/$package_name"
    
    mkdir -p "$package_dir"
    
    # 复制二进制文件
    cp build/msb "$package_dir/"
    cp build/msbrun "$package_dir/"
    cp build/msbserver "$package_dir/"
    cp build/msr "$package_dir/"
    cp build/msx "$package_dir/"
    cp build/msi "$package_dir/"
    
    # 复制库文件
    if [[ "$OS" == "darwin" ]]; then
        cp build/*.dylib "$package_dir/"
    else
        cp build/*.so.* "$package_dir/"
    fi
    
    # 创建压缩包
    cd build
    tar -czf "${package_name}.tar.gz" "$package_name"
    
    # 创建校验和
    if command -v shasum &> /dev/null; then
        shasum -a 256 "${package_name}.tar.gz" > "${package_name}.tar.gz.sha256"
    elif command -v sha256sum &> /dev/null; then
        sha256sum "${package_name}.tar.gz" > "${package_name}.tar.gz.sha256"
    fi
    
    cd ..
    
    info "Release package created: build/${package_name}.tar.gz"
}

# 主函数
main() {
    local version=""
    local skip_tests=false
    local create_package=false
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --version)
                version="$2"
                shift 2
                ;;
            --skip-tests)
                skip_tests=true
                shift
                ;;
            --create-package)
                create_package=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --version VERSION     Set version for package creation"
                echo "  --skip-tests         Skip running tests"
                echo "  --create-package     Create release package"
                echo "  --help               Show this help"
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    info "Starting CI build process..."
    
    detect_platform
    install_system_deps
    
    if ! download_prebuilt_libs; then
        warn "Will attempt to build libkrun from source (may fail in CI)"
    fi
    
    build_project
    
    if [[ "$skip_tests" != true ]]; then
        run_tests
    fi
    
    if [[ "$create_package" == true ]]; then
        create_release_package "$version"
    fi
    
    info "CI build completed successfully! 🎉"
}

# 运行主函数
main "$@"