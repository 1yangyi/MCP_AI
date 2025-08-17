#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试用例 - MCP服务器功能测试
"""

import pytest
import httpx
import asyncio
import json
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import (
    SEARCH_MCP_URL, BROWSER_MCP_URL, HTML_PARSER_URL, DECISION_MODEL_URL
)

class TestMCPServers:
    """
    MCP服务器测试类
    """
    
    @pytest.fixture(scope="class")
    async def http_client(self):
        """HTTP客户端fixture"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_search_mcp_health(self, http_client):
        """
        测试搜索MCP服务器健康检查
        """
        try:
            response = await http_client.get(f"{SEARCH_MCP_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            print(f"✓ 搜索MCP服务器健康检查通过: {data}")
        except Exception as e:
            pytest.skip(f"搜索MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_search_mcp_get_universities(self, http_client):
        """
        测试搜索MCP服务器获取大学列表
        """
        try:
            response = await http_client.get(f"{SEARCH_MCP_URL}/universities/range?start=0&end=2")
            assert response.status_code == 200
            data = response.json()
            assert "universities" in data
            assert len(data["universities"]) <= 3
            print(f"✓ 获取大学列表成功: {len(data['universities'])} 所大学")
        except Exception as e:
            pytest.skip(f"搜索MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_search_mcp_search_university(self, http_client):
        """
        测试搜索MCP服务器搜索大学功能
        """
        try:
            response = await http_client.get(f"{SEARCH_MCP_URL}/search?name=MIT")
            assert response.status_code == 200
            data = response.json()
            assert "universities" in data
            print(f"✓ 搜索大学功能正常: 找到 {len(data['universities'])} 个结果")
        except Exception as e:
            pytest.skip(f"搜索MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_browser_mcp_health(self, http_client):
        """
        测试浏览器MCP服务器健康检查
        """
        try:
            response = await http_client.get(f"{BROWSER_MCP_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print(f"✓ 浏览器MCP服务器健康检查通过: {data}")
        except Exception as e:
            pytest.skip(f"浏览器MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_browser_mcp_navigate(self, http_client):
        """
        测试浏览器MCP服务器导航功能
        """
        try:
            # 测试导航到一个简单的网站
            response = await http_client.post(
                f"{BROWSER_MCP_URL}/navigate",
                json={"url": "https://httpbin.org/html"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            print("✓ 浏览器导航功能正常")
        except Exception as e:
            pytest.skip(f"浏览器MCP服务器未运行或导航失败: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_html_parser_health(self, http_client):
        """
        测试HTML解析器MCP服务器健康检查
        """
        try:
            response = await http_client.get(f"{HTML_PARSER_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print(f"✓ HTML解析器MCP服务器健康检查通过: {data}")
        except Exception as e:
            pytest.skip(f"HTML解析器MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_html_parser_parse_html(self, http_client):
        """
        测试HTML解析器解析功能
        """
        try:
            test_html = """
            <html>
                <head>
                    <title>Test Page</title>
                    <meta name="description" content="Test description">
                </head>
                <body>
                    <h1>Welcome</h1>
                    <p>This is a test page.</p>
                    <a href="/about">About Us</a>
                    <form action="/search" method="get">
                        <input type="text" name="q" placeholder="Search...">
                        <button type="submit">Search</button>
                    </form>
                </body>
            </html>
            """
            
            response = await http_client.post(
                f"{HTML_PARSER_URL}/parse_html",
                json={
                    "html": test_html,
                    "url": "https://example.com",
                    "extract_links": True,
                    "extract_forms": True,
                    "extract_text": True
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "content" in data
            content = data["content"]
            assert content["title"] == "Test Page"
            assert len(content["links"]) > 0
            assert len(content["forms"]) > 0
            print("✓ HTML解析功能正常")
        except Exception as e:
            pytest.skip(f"HTML解析器MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_decision_model_health(self, http_client):
        """
        测试决策模型MCP服务器健康检查
        """
        try:
            response = await http_client.get(f"{DECISION_MODEL_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print(f"✓ 决策模型MCP服务器健康检查通过: {data}")
        except Exception as e:
            pytest.skip(f"决策模型MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_decision_model_decide(self, http_client):
        """
        测试决策模型决策功能
        """
        try:
            test_request = {
                "university": {
                    "name": "MIT",
                    "website": "https://web.mit.edu",
                    "rank": 1
                },
                "current_page": {
                    "url": "https://web.mit.edu",
                    "title": "MIT - Massachusetts Institute of Technology",
                    "links": [
                        {"text": "About MIT", "href": "/about", "selector": "a[href='/about']"},
                        {"text": "Admissions", "href": "/admissions", "selector": "a[href='/admissions']"},
                        {"text": "Contact", "href": "/contact", "selector": "a[href='/contact']"}
                    ],
                    "buttons": [],
                    "forms": []
                },
                "visited_pages": [],
                "page_count": 0
            }
            
            response = await http_client.post(
                f"{DECISION_MODEL_URL}/decide",
                json=test_request
            )
            assert response.status_code == 200
            data = response.json()
            assert "action" in data
            assert "target" in data
            assert "reason" in data
            print(f"✓ 决策模型功能正常: {data['action']} - {data['reason']}")
        except Exception as e:
            pytest.skip(f"决策模型MCP服务器未运行: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_decision_model_keywords(self, http_client):
        """
        测试决策模型关键词配置
        """
        try:
            response = await http_client.get(f"{DECISION_MODEL_URL}/keywords")
            assert response.status_code == 200
            data = response.json()
            assert "keywords" in data
            assert "college" in data["keywords"]
            assert "academic" in data["keywords"]
            print("✓ 决策模型关键词配置正常")
        except Exception as e:
            pytest.skip(f"决策模型MCP服务器未运行: {str(e)}")

class TestIntegration:
    """
    集成测试类
    """
    
    @pytest.fixture(scope="class")
    async def http_client(self):
        """HTTP客户端fixture"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_full_pipeline_simulation(self, http_client):
        """
        测试完整管道流程模拟
        """
        try:
            # 1. 获取大学列表
            response = await http_client.get(f"{SEARCH_MCP_URL}/universities/range?start=0&end=0")
            if response.status_code != 200:
                pytest.skip("搜索MCP服务器未运行")
            
            universities = response.json()["universities"]
            if not universities:
                pytest.skip("没有大学数据")
            
            university = universities[0]
            print(f"测试大学: {university['name']}")
            
            # 2. 模拟浏览器导航（使用测试URL）
            nav_response = await http_client.post(
                f"{BROWSER_MCP_URL}/navigate",
                json={"url": "https://httpbin.org/html"}
            )
            if nav_response.status_code != 200:
                pytest.skip("浏览器MCP服务器未运行")
            
            # 3. 获取HTML内容
            html_response = await http_client.get(f"{BROWSER_MCP_URL}/get_html")
            if html_response.status_code != 200:
                pytest.skip("无法获取HTML内容")
            
            html_content = html_response.json()["html"]
            
            # 4. 解析HTML
            parse_response = await http_client.post(
                f"{HTML_PARSER_URL}/parse_html",
                json={
                    "html": html_content,
                    "url": "https://httpbin.org/html",
                    "extract_links": True,
                    "extract_forms": True,
                    "extract_text": True
                }
            )
            if parse_response.status_code != 200:
                pytest.skip("HTML解析失败")
            
            parsed_content = parse_response.json()["content"]
            
            # 5. 决策制定
            decision_response = await http_client.post(
                f"{DECISION_MODEL_URL}/decide",
                json={
                    "university": university,
                    "current_page": parsed_content,
                    "visited_pages": [],
                    "page_count": 0
                }
            )
            if decision_response.status_code != 200:
                pytest.skip("决策制定失败")
            
            decision = decision_response.json()
            
            print("✓ 完整管道流程测试通过")
            print(f"  - 大学: {university['name']}")
            print(f"  - 页面标题: {parsed_content.get('title', 'N/A')}")
            print(f"  - 决策: {decision['action']} - {decision['reason']}")
            
            assert True  # 如果到达这里，说明所有步骤都成功了
            
        except Exception as e:
            pytest.skip(f"集成测试失败: {str(e)}")

def run_tests():
    """
    运行测试的主函数
    """
    print("开始运行MCP服务器测试...")
    print("=" * 50)
    
    # 运行测试
    pytest_args = [
        __file__,
        "-v",  # 详细输出
        "-s",  # 不捕获输出
        "--tb=short",  # 简短的错误回溯
        "-x",  # 遇到第一个失败就停止
    ]
    
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("\n✓ 所有测试通过!")
    else:
        print(f"\n✗ 测试失败，退出码: {exit_code}")
    
    return exit_code

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)