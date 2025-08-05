#!/usr/bin/env python3.9

import asyncio
import aiohttp
import json
import yaml
import os
import time
from pathlib import Path
from typing import Dict, Optional
from microsandbox import PythonSandbox

class PortMappingTracker:
    """动态跟踪端口映射变化的类"""
    
    def __init__(self):
        self.portal_ports_file = Path.home() / ".microsandbox" / "namespaces" / "portal.ports"
        self.namespace_dir = Path.home() / ".microsandbox" / "namespaces" / "default"
        self.sandboxfile_path = self.namespace_dir / "Sandboxfile"
        
    def read_portal_ports(self) -> Dict[str, int]:
        """读取 portal.ports 文件"""
        try:
            if self.portal_ports_file.exists():
                with open(self.portal_ports_file, 'r') as f:
                    data = json.load(f)
                    return data.get("mappings", {})
            return {}
        except Exception as e:
            print(f"读取 portal.ports 文件时出错: {e}")
            return {}
    
    def read_sandboxfile(self) -> Dict:
        """读取 Sandboxfile"""
        try:
            if self.sandboxfile_path.exists():
                with open(self.sandboxfile_path, 'r') as f:
                    data = yaml.safe_load(f)
                    return data or {}
            return {}
        except Exception as e:
            print(f"读取 Sandboxfile 时出错: {e}")
            return {}
    
    def get_port_for_sandbox(self, namespace: str, sandbox_name: str) -> Optional[int]:
        """获取特定沙箱的端口映射"""
        key = f"{namespace}/{sandbox_name}"
        mappings = self.read_portal_ports()
        return mappings.get(key)
    
    def get_sandboxfile_port_mapping(self, sandbox_name: str) -> Optional[str]:
        """从 Sandboxfile 获取端口映射"""
        sandboxfile = self.read_sandboxfile()
        sandboxes = sandboxfile.get("sandboxes", {})
        sandbox_config = sandboxes.get(sandbox_name, {})
        ports = sandbox_config.get("ports", [])
        
        # 查找 portal 端口映射 (格式: host_port:4444)
        for port_mapping in ports:
            if isinstance(port_mapping, str) and ":4444" in port_mapping:
                return port_mapping
        return None
    
    def print_current_mappings(self):
        """打印当前所有端口映射"""
        print("\n=== 当前端口映射状态 ===")
        
        # 从 portal.ports 文件读取
        portal_mappings = self.read_portal_ports()
        print(f"Portal.ports 文件中的映射:")
        for key, port in portal_mappings.items():
            print(f"  {key} -> {port}")
        
        # 从 Sandboxfile 读取
        sandboxfile = self.read_sandboxfile()
        sandboxes = sandboxfile.get("sandboxes", {})
        print(f"\nSandboxfile 中的端口配置:")
        for sandbox_name, config in sandboxes.items():
            ports = config.get("ports", [])
            print(f"  {sandbox_name}: {ports}")
        
        print("=" * 40)

async def test_dynamic_port_mapping():
    """测试动态端口映射"""
    print("=== 动态端口映射跟踪测试 ===")
    
    tracker = PortMappingTracker()
    session = aiohttp.ClientSession()
    
    try:
        # 显示初始状态
        print("\n1. 初始端口映射状态:")
        tracker.print_current_mappings()
        
        # 创建多个沙箱来观察端口映射变化
        sandboxes = []
        sandbox_names = []
        
        for i in range(3):
            sandbox_name = f"dynamic-test-{i+1}"
            sandbox_names.append(sandbox_name)
            
            print(f"\n2.{i+1} 创建沙箱: {sandbox_name}")
            
            # 创建沙箱
            sandbox = PythonSandbox(name=sandbox_name)
            sandbox._session = session
            sandboxes.append(sandbox)
            
            # 启动前的状态
            print(f"启动前端口映射:")
            before_mappings = tracker.read_portal_ports()
            print(f"  Portal mappings: {len(before_mappings)} 个")
            
            # 启动沙箱
            print(f"启动沙箱 {sandbox_name}...")
            await sandbox.start(image="microsandbox/python", memory=256, cpus=1)
            
            # 等待端口映射更新
            await asyncio.sleep(2)
            
            # 启动后的状态
            print(f"启动后端口映射:")
            after_mappings = tracker.read_portal_ports()
            sandboxfile_mapping = tracker.get_sandboxfile_port_mapping(sandbox_name)
            
            # 显示变化
            key = f"default/{sandbox_name}"
            assigned_port = after_mappings.get(key)
            
            print(f"  新分配的端口: {assigned_port}")
            print(f"  Sandboxfile 中的映射: {sandboxfile_mapping}")
            
            if assigned_port:
                # 测试端口连通性
                await test_portal_connectivity(session, assigned_port, sandbox_name)
            
            # 显示完整的当前状态
            tracker.print_current_mappings()
            
            # 短暂暂停
            await asyncio.sleep(1)
        
        print(f"\n3. 全部沙箱创建完成，当前有 {len(sandboxes)} 个沙箱运行")
        tracker.print_current_mappings()
        
        # 测试代码执行
        print(f"\n4. 在所有沙箱中执行代码测试...")
        for i, (sandbox, name) in enumerate(zip(sandboxes, sandbox_names)):
            print(f"\n4.{i+1} 在沙箱 {name} 中执行代码:")
            try:
                code = f'''
import os
import socket
print(f"沙箱名称: {name}")
print(f"主机名: {{socket.gethostname()}}")
print(f"当前目录: {{os.getcwd()}}")
print(f"Python 进程 ID: {{os.getpid()}}")
'''
                exec_result = await sandbox.run(code)
                output = await exec_result.output()
                print(f"执行结果: {output}")
            except Exception as e:
                print(f"执行代码时出错: {e}")
        
        # 逐个停止沙箱并观察端口映射变化
        print(f"\n5. 逐个停止沙箱并观察端口映射变化...")
        for i, (sandbox, name) in enumerate(zip(sandboxes, sandbox_names)):
            print(f"\n5.{i+1} 停止沙箱 {name}")
            
            # 停止前的状态
            before_stop = tracker.read_portal_ports()
            print(f"停止前端口映射数量: {len(before_stop)}")
            
            # 停止沙箱
            await sandbox.stop()
            
            # 等待端口释放
            await asyncio.sleep(2)
            
            # 停止后的状态
            after_stop = tracker.read_portal_ports()
            print(f"停止后端口映射数量: {len(after_stop)}")
            
            # 显示释放的端口
            released_ports = set(before_stop.items()) - set(after_stop.items())
            if released_ports:
                print(f"释放的端口映射: {dict(released_ports)}")
            
            tracker.print_current_mappings()
            
            await asyncio.sleep(1)
        
        print(f"\n6. 所有沙箱已停止")
        tracker.print_current_mappings()
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 确保清理所有沙箱
        print(f"\n清理阶段...")
        for sandbox in sandboxes:
            try:
                if sandbox._is_started:
                    await sandbox.stop()
            except:
                pass
        
        await session.close()
        print("✓ 清理完成")

async def test_portal_connectivity(session: aiohttp.ClientSession, port: int, sandbox_name: str):
    """测试 portal 端口连通性"""
    print(f"  测试端口 {port} 的连通性...")
    
    try:
        # 测试基本连通性
        async with session.get(
            f"http://127.0.0.1:{port}",
            timeout=aiohttp.ClientTimeout(total=2)
        ) as response:
            print(f"  ✓ 端口 {port} 可访问 (HTTP {response.status})")
            
            # 测试 RPC 接口
            await test_portal_rpc(session, port, sandbox_name)
            
    except Exception as e:
        print(f"  ✗ 端口 {port} 连接失败: {e}")

async def test_portal_rpc(session: aiohttp.ClientSession, port: int, sandbox_name: str):
    """测试 portal RPC 接口"""
    try:
        test_request = {
            "jsonrpc": "2.0",
            "method": "sandbox.repl.run",
            "params": {
                "language": "python",
                "code": f"print(f'Hello from {sandbox_name} on port {port}!')"
            },
            "id": f"test-{sandbox_name}"
        }
        
        async with session.post(
            f"http://127.0.0.1:{port}/api/v1/rpc",
            json=test_request,
            timeout=aiohttp.ClientTimeout(total=5)
        ) as response:
            if response.status == 200:
                result = await response.json()
                if "result" in result:
                    print(f"  ✓ Portal RPC 测试成功")
                else:
                    print(f"  ✗ Portal RPC 返回错误: {result}")
            else:
                print(f"  ✗ Portal RPC HTTP 错误: {response.status}")
                
    except Exception as e:
        print(f"  ✗ Portal RPC 测试失败: {e}")

if __name__ == "__main__":
    # 安装 PyYAML 如果需要
    try:
        import yaml
    except ImportError:
        print("需要安装 PyYAML，请运行: pip install PyYAML")
        exit(1)
    
    asyncio.run(test_dynamic_port_mapping())
