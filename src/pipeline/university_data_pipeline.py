import json
import requests
import time
import logging
from typing import Dict, List, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("university_pipeline")

# MCP服务器配置
HTML_PARSER_URL = "http://localhost:8080/parse_html"

# 最大重试次数
MAX_RETRIES = 3
# 重试间隔（秒）
RETRY_INTERVAL = 2
# 最大点击深度
MAX_CLICK_DEPTH = 5

class UniversityDataPipeline:
    def __init__(self, universities_file: str):
        """
        初始化数据管道
        
        Args:
            universities_file: QS500大学列表的JSON文件路径
        """
        self.universities = self._load_universities(universities_file)
        self.results = []
        
    def _load_universities(self, file_path: str) -> List[Dict[str, Any]]:
        """
        加载大学列表
        """
        try:
            # 尝试多种编码格式
            encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return json.load(f)
                except UnicodeDecodeError:
                    continue
            
            # 如果所有编码都失败，抛出错误
            raise Exception(f"无法使用任何编码格式读取文件: {file_path}")
            
        except Exception as e:
            logger.error(f"加载大学列表失败: {str(e)}")
            return []
    
    def run(self, start_index: int = 0, end_index: Optional[int] = None):
        """
        运行完整的数据收集管道
        
        Args:
            start_index: 开始处理的大学索引
            end_index: 结束处理的大学索引（不包含）
        """
        if not self.universities:
            logger.error("没有大学数据可处理")
            return
        
        if end_index is None:
            end_index = len(self.universities)
        
        for i, university in enumerate(self.universities[start_index:end_index]):
            current_index = start_index + i
            logger.info(f"处理大学 {current_index+1}/{end_index}: {university['school']} ({university['rank']})")
            
            try:
                university_data = self._process_university(university)
                if university_data:
                    self.results.append(university_data)
                    # 每处理10所大学保存一次结果
                    if (current_index + 1) % 10 == 0:
                        self._save_results(f"university_data_partial_{current_index+1}.json")
            except Exception as e:
                logger.error(f"处理大学 {university['school']} 时出错: {str(e)}")
        
        # 保存最终结果
        self._save_results("university_data_final.json")
        logger.info(f"数据收集完成，共处理 {len(self.results)}/{end_index-start_index} 所大学")
    
    def _process_university(self, university: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理单个大学的数据收集流程
        """
        university_data = {
            "rank": university["rank"],
            "name": university["school"],
            "website": university["website"],
            "pages": []
        }
        
        # 使用Playwright MCP打开大学网站
        try:
            # 这里调用Playwright MCP，获取初始HTML
            initial_html, current_url = self._call_playwright_navigate(university["website"])
            if not initial_html:
                logger.warning(f"无法获取 {university['school']} 的网页内容")
                return university_data
            
            # 解析初始HTML
            parsed_data = self._call_html_parser(initial_html, current_url)
            if not parsed_data:
                logger.warning(f"无法解析 {university['school']} 的网页内容")
                return university_data
            
            # 添加初始页面数据
            university_data["pages"].append({
                "url": current_url,
                "title": parsed_data.get("title", ""),
                "parsed_data": parsed_data
            })
            
            # 开始交互循环
            self._interactive_loop(university_data, parsed_data, current_url, depth=0)
            
            return university_data
            
        except Exception as e:
            logger.error(f"处理大学 {university['school']} 时出错: {str(e)}")
            return university_data
    
    def _interactive_loop(self, university_data: Dict[str, Any], parsed_data: Dict[str, Any], 
                          current_url: str, depth: int):
        """
        交互式循环：决策模型决定下一步点击，然后获取新页面并解析
        """
        if depth >= MAX_CLICK_DEPTH:
            logger.info(f"已达到最大点击深度 {MAX_CLICK_DEPTH}，停止交互")
            return
        
        # 调用决策模型决定下一步点击
        next_action = self._call_decision_model(parsed_data, university_data)
        
        if not next_action or not next_action.get("action"):
            logger.info("决策模型未返回下一步操作，停止交互")
            return
        
        action_type = next_action["action"]
        target = next_action.get("target", {})
        
        if action_type == "click_link" and target.get("href"):
            # 点击链接
            new_html, new_url = self._call_playwright_click(target.get("selector"), current_url)
            
        elif action_type == "click_button" and target.get("selector"):
            # 点击按钮
            new_html, new_url = self._call_playwright_click(target.get("selector"), current_url)
            
        elif action_type == "fill_form" and target.get("form_data"):
            # 填写表单
            new_html, new_url = self._call_playwright_fill_form(
                target.get("form_selector"), 
                target.get("form_data"), 
                current_url
            )
            
        elif action_type == "stop":
            # 停止交互
            logger.info("决策模型决定停止交互")
            return
            
        else:
            logger.warning(f"未知的操作类型: {action_type}")
            return
        
        # 检查是否成功获取新页面
        if not new_html:
            logger.warning("交互后未能获取新页面内容")
            return
        
        # 解析新页面
        new_parsed_data = self._call_html_parser(new_html, new_url)
        if not new_parsed_data:
            logger.warning("无法解析交互后的页面内容")
            return
        
        # 添加新页面数据
        university_data["pages"].append({
            "url": new_url,
            "title": new_parsed_data.get("title", ""),
            "parsed_data": new_parsed_data,
            "from_action": {
                "type": action_type,
                "target": target
            }
        })
        
        # 递归继续交互
        self._interactive_loop(university_data, new_parsed_data, new_url, depth + 1)
    
    def _call_playwright_navigate(self, url: str) -> tuple:
        """
        调用Playwright MCP导航到URL并获取HTML
        
        返回: (html_content, current_url)
        """
        # 这里应该调用实际的Playwright MCP
        # 以下是示例代码，需要替换为实际的MCP调用
        try:
            response = self._call_mcp_playwright("playwright_navigate", {"url": url})
            if response and "html" in response and "url" in response:
                return response["html"], response["url"]
            return None, url
        except Exception as e:
            logger.error(f"调用Playwright导航失败: {str(e)}")
            return None, url
    
    def _call_playwright_click(self, selector: str, current_url: str) -> tuple:
        """
        调用Playwright MCP点击元素并获取新HTML
        
        返回: (html_content, current_url)
        """
        # 这里应该调用实际的Playwright MCP
        # 以下是示例代码，需要替换为实际的MCP调用
        try:
            response = self._call_mcp_playwright("playwright_click", {"selector": selector})
            if response and "html" in response:
                return response["html"], response.get("url", current_url)
            return None, current_url
        except Exception as e:
            logger.error(f"调用Playwright点击失败: {str(e)}")
            return None, current_url
    
    def _call_playwright_fill_form(self, form_selector: str, form_data: Dict[str, str], current_url: str) -> tuple:
        """
        调用Playwright MCP填写表单并提交
        
        返回: (html_content, current_url)
        """
        # 这里应该调用实际的Playwright MCP
        # 以下是示例代码，需要替换为实际的MCP调用
        try:
            # 填写表单中的每个字段
            for field_selector, value in form_data.items():
                self._call_mcp_playwright("playwright_fill", {
                    "selector": field_selector,
                    "value": value
                })
            
            # 提交表单
            submit_selector = form_selector + " [type=submit]"  # 假设表单有一个提交按钮
            response = self._call_mcp_playwright("playwright_click", {"selector": submit_selector})
            
            if response and "html" in response:
                return response["html"], response.get("url", current_url)
            return None, current_url
        except Exception as e:
            logger.error(f"调用Playwright填写表单失败: {str(e)}")
            return None, current_url
    
    def _call_html_parser(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """
        调用HTML解析MCP服务器解析HTML
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    HTML_PARSER_URL,
                    json={"html": html, "url": url},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("parsed_data")
                else:
                    logger.warning(f"HTML解析服务返回错误: {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"调用HTML解析服务失败 (尝试 {attempt+1}/{MAX_RETRIES}): {str(e)}")
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_INTERVAL)
        
        return None
    
    def _call_decision_model(self, parsed_data: Dict[str, Any], university_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        调用决策模型决定下一步操作
        """
        # 这里应该调用实际的决策模型MCP
        # 以下是示例代码，需要替换为实际的MCP调用
        try:
            # 构建决策模型的输入
            decision_input = {
                "university": {
                    "name": university_data["name"],
                    "rank": university_data["rank"],
                    "website": university_data["website"]
                },
                "current_page": parsed_data,
                "visited_pages": [page["url"] for page in university_data["pages"]],
                "page_count": len(university_data["pages"])
            }
            
            # 调用决策模型
            response = self._call_mcp_decision(decision_input)
            
            if response and "action" in response:
                return response
            return {"action": "stop"}
        except Exception as e:
            logger.error(f"调用决策模型失败: {str(e)}")
            return {"action": "stop"}
    
    def _call_mcp_playwright(self, tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        调用Playwright MCP服务器
        """
        # 这里应该实现实际的MCP调用
        # 在实际实现中，这将使用MCP协议调用Playwright服务器
        # 以下是示例代码，需要替换为实际的MCP调用
        try:
            # 使用run_mcp工具调用Playwright MCP
            return {"status": "success", "message": "MCP调用成功"}
        except Exception as e:
            logger.error(f"调用Playwright MCP失败: {str(e)}")
            return None
    
    def _call_mcp_decision(self, input_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        调用决策模型MCP服务器
        """
        # 这里应该实现实际的MCP调用
        # 在实际实现中，这将使用MCP协议调用决策模型服务器
        # 以下是示例代码，需要替换为实际的MCP调用
        try:
            # 使用run_mcp工具调用决策模型MCP
            return {"action": "stop"}
        except Exception as e:
            logger.error(f"调用决策模型MCP失败: {str(e)}")
            return None
    
    def _save_results(self, filename: str):
        """
        保存收集的数据到JSON文件
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            logger.info(f"结果已保存到 {filename}")
        except Exception as e:
            logger.error(f"保存结果失败: {str(e)}")

# Update file paths in the main section
if __name__ == "__main__":
    pipeline = UniversityDataPipeline("../../data/input/top500_school_websites.json")
    pipeline.run(start_index=0, end_index=10)
    # 处理前10所大学作为示例
    pipeline.run(start_index=0, end_index=10)