import json
import os
from pathlib import Path
from typing import Any, Dict, List


def read_json_file(filename: str) -> Any:
    """读取与本文件同目录下的 JSON 文件并返回其 Python 对象"""
    base = Path(__file__).parent
    file_path = (base / filename).resolve()
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_json_dumps(data: Any) -> str:
    """将对象转为较紧凑的 JSON 字符串，便于放入提示词中"""
    try:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(data)


def _parse_model_content_to_json(content: str) -> Dict:
    """尝试从模型返回的内容中解析JSON对象"""
    try:
        return json.loads(content)
    except Exception:
        # 尝试提取可能被引号包裹的JSON字符串
        try:
            import re
            m = re.search(r'```json\s*(.+?)\s*```', content, re.DOTALL)
            if m:
                return json.loads(m.group(1))
        except Exception:
            pass
        
        # 返回空字典作为回退
        return {}


# def make_decision_with_ai(api_key: str, page_content: Dict, university_info: Dict, 
#                          visited_pages: List[str], page_count: int, max_pages: int = 10) -> Dict:
#     """使用AI模型决定下一步操作
    
#     参数:
#         api_key (str): DeepSeek API密钥
#         page_content (Dict): 当前页面内容
#         university_info (Dict): 大学信息
#         visited_pages (List[str]): 已访问页面URL列表
#         page_count (int): 已访问页面数量
#         max_pages (int): 最大页面访问数量
        
#     返回:
#         Dict: 决策结果，包含action、target、reason等字段
#     """
#     # 延迟导入，避免无 openai 依赖时导致整个模块无法导入
#     try:
#         from openai import OpenAI  # type: ignore
#     except Exception as e:
#         return {
#             "action": "stop",
#             "reason": f"缺少openai依赖或导入失败: {e}",
#             "confidence": 0.0
#         }
    
#     # 如果已经访问了足够多的页面，停止
#     if page_count >= max_pages:
#         return {
#             "action": "stop",
#             "reason": f"已达到最大页面访问数量({max_pages})",
#             "confidence": 1.0
#         }
    
#     # 构造提示词
#     prompt = f"""
# 你是一个智能网页导航助手，帮助从大学网站收集信息。

# # 当前状态
# - 大学名称: {university_info.get('name')}
# - 当前页面URL: {page_content.get('url')}
# - 已访问页面数: {page_count}/{max_pages}
# - 已访问的URL: {', '.join(visited_pages[:5])}{'...' if len(visited_pages) > 5 else ''}

# # 当前页面内容
# {_safe_json_dumps(page_content)}

# # 你的任务
# 分析当前页面内容，决定下一步操作。你需要找到包含以下信息的页面（按优先级排序）：
# 1. 二级学院/院系设置/学院列表
# 2. 学术信息/专业设置/课程
# 3. 关于学校/学校概况
# 4. 招生信息
# 5. 联系方式

# # 返回格式
# 请以JSON格式返回你的决策，包含以下字段：
# - action: 操作类型，可选值为 click_link（点击链接）, click_button（点击按钮）, fill_form（填写表单）, scroll（滚动页面）, wait（等待加载）, stop（停止操作）
# - target: 操作目标，包含selector（CSS选择器）, href（链接地址）, text（文本内容）等字段
# - reason: 决策原因
# - confidence: 决策置信度（0-1之间的浮点数）

# 只返回JSON格式，不要有其他解释。
# """

#     # 初始化客户端（DeepSeek 兼容 OpenAI SDK）
#     try:
#         client = OpenAI(
#             api_key=api_key,
#             base_url="https://api.deepseek.com/v1",
#         )
#     except Exception as e:
#         return {
#             "action": "stop",
#             "reason": f"初始化客户端失败: {e}",
#             "confidence": 0.0
#         }

#     try:
#         completion = client.chat.completions.create(
#             model="deepseek-chat",
#             messages=[
#                 {"role": "system", "content": "你是一个专业的网页导航助手，严格按要求输出JSON格式的决策。"},
#                 {"role": "user", "content": prompt},
#             ],
#             temperature=0.2,
#             max_tokens=1024,
#         )

#         # 获取模型返回的内容
#         content = completion.choices[0].message.content if completion.choices else ""
#         if not content:
#             return {
#                 "action": "stop",
#                 "reason": "模型未返回内容",
#                 "confidence": 0.0
#             }

#         # 解析为决策对象
#         decision = _parse_model_content_to_json(content)
        
#         # 确保返回的决策包含必要的字段
#         if "action" not in decision:
#             decision["action"] = "stop"
#         if "reason" not in decision:
#             decision["reason"] = "AI未能提供有效决策"
#         if "confidence" not in decision:
#             decision["confidence"] = 0.5
            
#         return decision

#     except Exception as e:
#         return {
#             "action": "stop",
#             "reason": f"API请求失败: {str(e)}",
#             "confidence": 0.0
#         }


def extract_entities_with_deepseek(api_key: str, text: str, example: str) -> dict:
    """
    使用DeepSeek API从网页结构化列表中识别出该学校所有二级学院所在的位置（按钮）。

    参数:
        api_key (str): DeepSeek API密钥（不应硬编码，建议使用环境变量 DEEPSEEK_API_KEY）
        text (str): 网页结构化列表（建议提供JSON字符串）
        example (str): 示例文本（建议提供JSON字符串）

    返回:
        dict: {status, entities(str|Any), raw_response(str|Any) 或 message}
    """
    # 延迟导入，避免无 openai 依赖时导致整个模块无法导入
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        return {
            "status": "error",
            "message": f"缺少openai依赖或导入失败: {e}"
        }

    # 构造提示词
    prompt = f"""
    你是一个数据收集助手，协助收集高校所有二级学院信息。
    请从以下网页结构化列表中识别出该学校所有二级学院所在的位置（按钮）。列表内容如下：
    {text}
    请以字符串格式直接返回该学校所有二级学院所在的位置（按钮）的文本和URL。格式为"文本@URL"。
    注意：仅输出一个最可能的按钮文本，不要附加解释。
    例如，给定示例：{example}，输出应为："院系设置@yxsz.htm"。
    """
    # 初始化客户端（DeepSeek 兼容 OpenAI SDK）
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
    except Exception as e:
        return {"status": "error", "message": f"初始化客户端失败: {e}"}

    try:
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的助手，严格按要求输出按钮文本。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=512,
        )

        # 获取模型返回的内容
        content = completion.choices[0].message.content if completion.choices else ""
        if not content:
            return {"status": "error", "message": "模型未返回内容"}

        # 解析为按钮文本
        button_text = _parse_model_content_to_text(content)
        return {
            "status": "success",
            "button_text": button_text,
            "raw_response": content,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"API请求失败: {str(e)}",
        }



def extract_schools_with_deepseek(api_key: str, text: str) -> dict:
    """
    使用DeepSeek API从网页结构化列表中识别出该学校所有二级学院所在的位置（按钮）。

    参数:
        api_key (str): DeepSeek API密钥（不应硬编码，建议使用环境变量 DEEPSEEK_API_KEY）
        text (str): 网页结构化列表（建议提供JSON字符串）
        example (str): 示例文本（建议提供JSON字符串）

    返回:
        dict: {status, entities(str|Any), raw_response(str|Any) 或 message}
    """
    # 延迟导入，避免无 openai 依赖时导致整个模块无法导入
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        return {
            "status": "error",
            "message": f"缺少openai依赖或导入失败: {e}"
        }

    # 构造提示词
    prompt = f"""
    你是一个数据收集助手，协助收集高校所有二级学院信息。
    请从以下网页结构化列表中识别出该学校所有二级学院的名称和URL。列表内容如下：
    {text}
    请以json格式直接返回该学校所有二级学院的名称和URL。
    注意：仅输出结果的json格式，不要附加解释。输出格式：{"名称":"院系名称","URL":"院系URL"}。
    """
    # 初始化客户端（DeepSeek 兼容 OpenAI SDK）
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
    except Exception as e:
        return {"status": "error", "message": f"初始化客户端失败: {e}"}

    try:
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的助手，严格按要求输出按钮文本。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=512,
        )

        # 获取模型返回的内容
        content = completion.choices[0].message.content if completion.choices else ""
        if not content:
            return {"status": "error", "message": "模型未返回内容"}

        # 解析为按钮文本
        schools = _parse_model_content_to_text(content)
        return {
            "status": "success",
            "schools": schools,
            "raw_response": content,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"API请求失败: {str(e)}",
        }


# 在decision.py中实现以下函数

# def identify_department_links(api_key: str, page_content: Dict) -> List[Dict]:
#     """使用AI识别与院系/学院/系部相关的链接
    
#     参数:
#         api_key (str): DeepSeek API密钥
#         page_content (Dict): 当前页面内容，包含links列表
        
#     返回:
#         List[Dict]: 可能与院系相关的链接列表，按相关性排序
#     """
#     # 延迟导入，避免无 openai 依赖时导致整个模块无法导入
#     try:
#         from openai import OpenAI
#     except Exception as e:
#         logger.error(f"缺少openai依赖或导入失败: {e}")
#         return []
    
#     # 提取页面中的所有链接
#     links = page_content.get("links", [])
#     if not links:
#         return []
    
#     # 构造提示词
#     prompt = f"""
#     你是一个专业的大学网站分析助手。请分析以下大学网站中的链接列表，识别出哪些链接最可能指向"院系设置"、"学院列表"或"系部设置"等页面。

#     链接列表：
#     {json.dumps(links, ensure_ascii=False, indent=2)}

#     请返回一个JSON数组，包含你认为与院系/学院/系部相关的链接对象，按相关性从高到低排序。每个对象应包含原始链接的所有字段，并添加一个confidence字段（0-1之间的浮点数）表示你的置信度。

#     只返回JSON格式，不要有其他解释。
#     """

#     # 初始化客户端
#     try:
#         client = OpenAI(
#             api_key=api_key,
#             base_url="https://api.deepseek.com/v1",
#         )
        
#         completion = client.chat.completions.create(
#             model="deepseek-chat",
#             messages=[
#                 {"role": "system", "content": "你是一个专业的大学网站分析助手，严格按要求输出JSON格式的结果。"},
#                 {"role": "user", "content": prompt},
#             ],
#             temperature=0.2,
#             max_tokens=1024,
#         )
        
#         # 获取模型返回的内容
#         content = completion.choices[0].message.content if completion.choices else ""
#         if not content:
#             return []
            
#         # 解析为链接列表
#         department_links = _parse_model_content_to_json(content)
#         if not isinstance(department_links, list):
#             return []
            
#         return department_links
        
#     except Exception as e:
#         logger.error(f"API请求失败: {str(e)}")
#         return []


# 在FastAPI应用中添加以下端点

# class DepartmentLinksRequest(BaseModel):
#     page_content: Dict
#     api_key: Optional[str] = None

# class DepartmentLinksResponse(BaseModel):
#     links: List[Dict]
#     status: str

# @app.post("/identify_department_links", response_model=DepartmentLinksResponse)
# async def api_identify_department_links(request: DepartmentLinksRequest):
#     """识别页面中与院系相关的链接"""
#     # 获取API密钥
#     api_key = request.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
#     if not api_key:
#         raise HTTPException(status_code=400, detail="缺少API密钥")
    
#     # 调用AI识别函数
#     department_links = identify_department_links(api_key, request.page_content)
    
#     return {
#         "links": department_links,
#         "status": "success"
#     }


# if __name__ == "__main__":
#     # 测试代码
#     DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    
#     if not DEEPSEEK_API_KEY:
#         print("未检测到环境变量 DEEPSEEK_API_KEY，跳过调用示例。请先设置后再运行本文件。")
#     else:
#         # 测试决策功能
#         try:
#             # 模拟页面内容和大学信息
#             page_content = {
#                 "url": "https://example.edu",
#                 "title": "示例大学",
#                 "links": [
#                     {"text": "院系设置", "href": "/colleges"},
#                     {"text": "招生信息", "href": "/admission"}
#                 ]
#             }
#             university_info = {"name": "示例大学", "rank": 100}
            
#             result = make_decision_with_ai(
#                 api_key=DEEPSEEK_API_KEY,
#                 page_content=page_content,
#                 university_info=university_info,
#                 visited_pages=[],
#                 page_count=0
#             )
            
#             print("AI决策结果:", json.dumps(result, ensure_ascii=False, indent=2))
#         except Exception as e:
#             print("测试决策功能失败:", e)