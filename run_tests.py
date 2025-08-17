#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试运行器 - 运行所有测试用例
"""

import sys
import subprocess
from pathlib import Path
import asyncio
import httpx
from src.config import (
    SEARCH_MCP_URL, BROWSER_MCP_URL, HTML_PARSER_URL, DECISION_MODEL_URL
)

def check_server_status(url: str, name: str) -> bool:
    """
    检查服务器状态
    """
    try:
        import requests
        response = requests.get(f"{url}/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ {name} 服务器运行正常")
            return True
        else:
            print(f"✗ {name} 服务器响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ {name} 服务器连接失败: {str(e)}")
        return False

def check_all_servers():
    """
    检查所有MCP服务器状态
    """
    print("检查MCP服务器状态...")
    print("=" * 40)
    
    servers = [
        (SEARCH_MCP_URL, "搜索MCP"),
        (BROWSER_MCP_URL, "浏览器MCP"),
        (HTML_PARSER_URL, "HTML解析器MCP"),
        (DECISION_MODEL_URL, "决策模型MCP")
    ]
    
    running_servers = 0
    for url, name in servers:
        if check_server_status(url, name):
            running_servers += 1
    
    print(f"\n运行中的服务器: {running_servers}/{len(servers)}")
    
    if running_servers == 0:
        print("\n⚠️  没有MCP服务器在运行!")
        print("请先运行 'python start_servers.py' 启动服务器")
        return False
    elif running_servers < len(servers):
        print("\n⚠️  部分MCP服务器未运行，某些测试可能会被跳过")
    
    return True

def install_test_dependencies():
    """
    安装测试依赖
    """
    print("检查测试依赖...")
    try:
        import pytest
        import httpx
        print("✓ 测试依赖已安装")
        return True
    except ImportError as e:
        print(f"✗ 缺少测试依赖: {str(e)}")
        print("正在安装测试依赖...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest", "httpx"])
            print("✓ 测试依赖安装完成")
            return True
        except subprocess.CalledProcessError:
            print("✗ 测试依赖安装失败")
            return False

def run_unit_tests():
    """
    运行单元测试
    """
    print("\n运行单元测试...")
    print("=" * 40)
    
    test_file = Path(__file__).parent / "tests" / "test_mcp_servers.py"
    
    if not test_file.exists():
        print(f"✗ 测试文件不存在: {test_file}")
        return False
    
    try:
        # 运行pytest
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            str(test_file),
            "-v",  # 详细输出
            "-s",  # 不捕获输出
            "--tb=short",  # 简短的错误回溯
        ], capture_output=False, text=True)
        
        if result.returncode == 0:
            print("\n✓ 所有单元测试通过!")
            return True
        else:
            print(f"\n✗ 单元测试失败，退出码: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"✗ 运行测试时出错: {str(e)}")
        return False

def run_integration_tests():
    """
    运行集成测试
    """
    print("\n运行集成测试...")
    print("=" * 40)
    
    test_file = Path(__file__).parent / "tests" / "test_mcp_servers.py"
    
    try:
        # 只运行集成测试类
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            str(test_file) + "::TestIntegration",
            "-v",
            "-s",
            "--tb=short",
        ], capture_output=False, text=True)
        
        if result.returncode == 0:
            print("\n✓ 集成测试通过!")
            return True
        else:
            print(f"\n✗ 集成测试失败，退出码: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"✗ 运行集成测试时出错: {str(e)}")
        return False

def main():
    """
    主函数
    """
    print("MCP服务器测试运行器")
    print("=" * 50)
    
    # 检查测试依赖
    if not install_test_dependencies():
        sys.exit(1)
    
    # 检查服务器状态
    servers_running = check_all_servers()
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "unit":
            success = run_unit_tests()
        elif test_type == "integration":
            if not servers_running:
                print("\n✗ 集成测试需要所有服务器运行")
                sys.exit(1)
            success = run_integration_tests()
        elif test_type == "all":
            unit_success = run_unit_tests()
            integration_success = run_integration_tests() if servers_running else False
            success = unit_success and integration_success
        else:
            print(f"\n✗ 未知的测试类型: {test_type}")
            print("使用方法: python run_tests.py [unit|integration|all]")
            sys.exit(1)
    else:
        # 默认运行所有测试
        unit_success = run_unit_tests()
        integration_success = run_integration_tests() if servers_running else False
        success = unit_success and (integration_success or not servers_running)
    
    if success:
        print("\n🎉 测试完成!")
        sys.exit(0)
    else:
        print("\n❌ 测试失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()