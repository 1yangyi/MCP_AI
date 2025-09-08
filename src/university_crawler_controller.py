#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主控制器 - 大学数据收集系统
实现循环处理机制和模块协调
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import httpx
import json
from pathlib import Path

from src.config import (
    SEARCH_MCP_URL, BROWSER_MCP_URL, HTML_PARSER_URL, DECISION_MODEL_URL,
    MAX_RETRIES, RETRY_INTERVAL, MAX_CLICK_DEPTH, OUTPUT_DIR
)

class MainController:
    """
    主控制器类 - 协调各个MCP服务器完成大学数据收集任务
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.session = httpx.AsyncClient(timeout=30.0)
        self.results = []
        
        # MCP服务器URL配置
        self.search_url = SEARCH_MCP_URL
        self.browser_url = BROWSER_MCP_URL
        self.html_parser_url = HTML_PARSER_URL
        self.decision_url = DECISION_MODEL_URL
        
        # 处理配置
        self.max_retries = MAX_RETRIES
        self.retry_interval = RETRY_INTERVAL
        self.max_pages_per_university = MAX_CLICK_DEPTH
        
        self.logger.info("主控制器初始化完成")
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志配置"""
        logger = logging.getLogger("main_controller")
        logger.setLevel(logging.INFO)
        
        # 创建日志目录
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 文件处理器
        file_handler = logging.FileHandler(log_dir / "main_controller.log")
        file_handler.setLevel(logging.INFO)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    async def run_pipeline(self, start_index: int = 0, end_index: Optional[int] = None, 
                          single_university: Optional[str] = None) -> Dict[str, Any]:
        """
        运行完整的数据收集管道
        
        Args:
            start_index: 开始索引
            end_index: 结束索引
            single_university: 单个大学名称
        
        Returns:
            处理结果统计
        """
        start_time = time.time()
        self.logger.info(f"开始运行数据收集管道 - 开始索引: {start_index}, 结束索引: {end_index}")
        
        try:
            # 1. 获取大学列表
            universities = await self._get_universities(start_index, end_index, single_university)
            if not universities:
                self.logger.warning("没有找到需要处理的大学")
                return {"status": "no_universities", "processed": 0}
            
            self.logger.info(f"获取到 {len(universities)} 所大学待处理")
            
            # 2. 处理每所大学
            processed_count = 0
            failed_count = 0
            
            for university in universities:
                try:
                    result = await self._process_university(university)
                    if result["status"] == "success":
                        processed_count += 1
                        # 标记大学为已处理
                        await self._mark_university_processed(university["rank"])
                    else:
                        failed_count += 1
                    
                    self.results.append(result)
                    
                except Exception as e:
                    self.logger.error(f"处理大学 {university['name']} 时出错: {str(e)}")
                    failed_count += 1
                    self.results.append({
                        "university": university,
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
            
            # 3. 保存结果
            await self._save_results()
            
            end_time = time.time()
            duration = end_time - start_time
            
            summary = {
                "status": "completed",
                "total_universities": len(universities),
                "processed_successfully": processed_count,
                "failed": failed_count,
                "duration_seconds": duration,
                "results_file": str(Path(OUTPUT_DIR) / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            }
            
            self.logger.info(f"管道执行完成 - {summary}")
            return summary
            
        except Exception as e:
            self.logger.error(f"管道执行失败: {str(e)}")
            return {"status": "error", "error": str(e)}
        
        finally:
            await self.session.aclose()
    
    async def _get_universities(self, start_index: int, end_index: Optional[int], 
                               single_university: Optional[str]) -> List[Dict[str, Any]]:
        """
        从搜索MCP获取大学列表
        """
        try:
            if single_university:
                # 搜索单个大学
                response = await self.session.get(
                    f"{self.search_url}/search",
                    params={"name": single_university}
                )
            else:
                # 获取范围内的大学
                params = {"start": start_index}
                if end_index is not None:
                    params["end"] = end_index
                
                response = await self.session.get(
                    f"{self.search_url}/universities/range",
                    params=params
                )
            
            response.raise_for_status()
            data = response.json()
            
            if single_university:
                return data.get("universities", [])
            else:
                return data.get("universities", [])
                
        except Exception as e:
            self.logger.error(f"获取大学列表失败: {str(e)}")
            return []
    
    async def _process_university(self, university: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个大学的数据收集
        
        实现循环处理机制：
        1. 浏览器导航到大学网站
        2. HTML解析器解析页面内容
        3. 决策模型判断下一步操作
        4. 根据决策执行操作（点击链接、填写表单等）
        5. 重复步骤2-4，直到达到停止条件
        """
        self.logger.info(f"开始处理大学: {university['name']} ({university['website']})")
        
        university_result = {
            "university": university,
            "status": "processing",
            "pages_visited": [],
            "collected_data": {},
            "timestamp": datetime.now().isoformat()
        }
        
        visited_pages = []
        page_count = 0
        
        try:
            # 1. 初始化浏览器并导航到大学网站
            await self._navigate_to_website(university["website"])
            
            # 开始循环处理
            while page_count < self.max_pages_per_university:
                # 2. 获取当前页面HTML
                current_url = await self._get_current_url()
                if current_url in visited_pages:
                    self.logger.info(f"页面已访问过，跳过: {current_url}")
                    break
                
                html_content = await self._get_page_html()
                if not html_content:
                    self.logger.warning("无法获取页面HTML内容")
                    break
                
                # 3. 解析HTML内容
                parsed_content = await self._parse_html(html_content, current_url)
                if not parsed_content:
                    self.logger.warning("HTML解析失败")
                    break
                
                # 记录访问的页面
                visited_pages.append(current_url)
                university_result["pages_visited"].append({
                    "url": current_url,
                    "title": parsed_content.get("title"),
                    "timestamp": datetime.now().isoformat()
                })
                
                # 收集有用的数据
                self._collect_useful_data(university_result, parsed_content)
                
                # 4. 决策下一步操作
                decision = await self._make_decision(
                    university=university,
                    current_page=parsed_content,
                    visited_pages=visited_pages,
                    page_count=page_count
                )
                
                if not decision or decision.get("action") == "stop":
                    self.logger.info(f"决策停止，原因: {decision.get('reason', '未知')}")
                    break
                
                # 5. 执行决策操作
                action_result = await self._execute_action(decision)
                if not action_result:
                    self.logger.warning("操作执行失败")
                    break
                
                page_count += 1
                
                # 短暂等待，避免过快请求
                await asyncio.sleep(1)
            
            university_result["status"] = "success"
            university_result["pages_processed"] = page_count
            self.logger.info(f"大学 {university['name']} 处理完成，访问了 {page_count} 个页面")
            
        except Exception as e:
            self.logger.error(f"处理大学 {university['name']} 时出错: {str(e)}")
            university_result["status"] = "error"
            university_result["error"] = str(e)
        
        finally:
            # 重启浏览器，为下一个大学做准备
            await self._restart_browser()
        
        return university_result
    
    async def _navigate_to_website(self, url: str) -> bool:
        """
        导航到指定网站
        """
        try:
            response = await self.session.post(
                f"{self.browser_url}/navigate",
                json={"url": url}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"导航到网站失败 {url}: {str(e)}")
            return False
    
    async def _get_current_url(self) -> str:
        """
        获取当前页面URL
        """
        try:
            response = await self.session.get(f"{self.browser_url}/current_page")
            response.raise_for_status()
            data = response.json()
            return data.get("url", "")
        except Exception as e:
            self.logger.error(f"获取当前URL失败: {str(e)}")
            return ""
    
    async def _get_page_html(self) -> str:
        """
        获取当前页面HTML
        """
        try:
            response = await self.session.get(f"{self.browser_url}/get_html")
            response.raise_for_status()
            data = response.json()
            return data.get("html", "")
        except Exception as e:
            self.logger.error(f"获取页面HTML失败: {str(e)}")
            return ""
    
    async def _parse_html(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """
        解析HTML内容
        """
        try:
            response = await self.session.post(
                f"{self.html_parser_url}/parse_html",
                json={
                    "html": html,
                    "url": url,
                    "extract_links": True,
                    "extract_forms": True,
                    "extract_images": True,
                    "extract_text": True,
                    "extract_navigation": True,
                    "extract_contact_info": True,
                    "extract_social_links": True
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("content")
        except Exception as e:
            self.logger.error(f"HTML解析失败: {str(e)}")
            return None
    
    async def _make_decision(self, university: Dict[str, Any], current_page: Dict[str, Any],
                           visited_pages: List[str], page_count: int) -> Optional[Dict[str, Any]]:
        """
        调用决策模型做出下一步决策
        """
        try:
            response = await self.session.post(
                f"{self.decision_url}/decide",
                json={
                    "university": university,
                    "current_page": current_page,
                    "visited_pages": visited_pages,
                    "page_count": page_count,
                    "max_pages": self.max_pages_per_university
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"决策制定失败: {str(e)}")
            return None
    
    async def _execute_action(self, decision: Dict[str, Any]) -> bool:
        """
        执行决策操作
        """
        action = decision.get("action")
        target = decision.get("target", {})
        
        try:
            if action == "click_link":
                response = await self.session.post(
                    f"{self.browser_url}/click",
                    json={"selector": target.get("selector")}
                )
            elif action == "click_button":
                response = await self.session.post(
                    f"{self.browser_url}/click",
                    json={"selector": target.get("selector")}
                )
            elif action == "fill_form":
                response = await self.session.post(
                    f"{self.browser_url}/fill_form",
                    json={
                        "form_selector": target.get("form_selector"),
                        "form_data": target.get("form_data")
                    }
                )
            elif action == "scroll":
                response = await self.session.post(
                    f"{self.browser_url}/scroll",
                    json={"direction": "down", "pixels": 500}
                )
            elif action == "wait":
                await asyncio.sleep(2)
                return True
            else:
                self.logger.warning(f"未知操作类型: {action}")
                return False
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            self.logger.error(f"执行操作失败 {action}: {str(e)}")
            return False
    
    def _collect_useful_data(self, university_result: Dict[str, Any], parsed_content: Dict[str, Any]):
        """
        从解析的内容中收集有用的数据
        """
        collected = university_result["collected_data"]
        
        # 收集联系信息
        if "contact_info" in parsed_content:
            contact_info = parsed_content["contact_info"]
            if contact_info.get("emails"):
                collected.setdefault("emails", set()).update(contact_info["emails"])
            if contact_info.get("phones"):
                collected.setdefault("phones", set()).update(contact_info["phones"])
            if contact_info.get("addresses"):
                collected.setdefault("addresses", set()).update(contact_info["addresses"])
        
        # 收集社交媒体链接
        if "social_links" in parsed_content:
            social_links = parsed_content["social_links"]
            collected.setdefault("social_links", []).extend(social_links)
        
        # 收集重要链接
        if "links" in parsed_content:
            important_links = []
            for link in parsed_content["links"]:
                link_text = link.get("text", "").lower()
                # 收集包含重要关键词的链接
                important_keywords = ["about", "contact", "admission", "academic", "research", "faculty"]
                if any(keyword in link_text for keyword in important_keywords):
                    important_links.append(link)
            
            if important_links:
                collected.setdefault("important_links", []).extend(important_links)
        
        # 转换set为list以便JSON序列化
        for key, value in collected.items():
            if isinstance(value, set):
                collected[key] = list(value)
    
    async def _restart_browser(self):
        """
        重启浏览器
        """
        try:
            await self.session.post(f"{self.browser_url}/restart")
        except Exception as e:
            self.logger.error(f"重启浏览器失败: {str(e)}")
    
    async def _mark_university_processed(self, rank: int):
        """
        标记大学为已处理
        """
        try:
            await self.session.post(
                f"{self.search_url}/mark_processed",
                json={"rank": rank}
            )
        except Exception as e:
            self.logger.error(f"标记大学已处理失败: {str(e)}")
    
    async def _save_results(self):
        """
        保存处理结果
        """
        try:
            output_dir = Path(OUTPUT_DIR)
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_file = output_dir / f"results_{timestamp}.json"
            
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"结果已保存到: {results_file}")
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {str(e)}")


async def main():
    """
    主函数 - 用于测试
    """
    controller = MainController()
    result = await controller.run_pipeline(start_index=0, end_index=2)
    print(f"处理结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())