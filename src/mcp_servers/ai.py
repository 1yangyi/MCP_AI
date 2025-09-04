import json
import os
from pathlib import Path
from typing import Any


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


def _parse_model_content_to_text(content: str) -> str:
    """尽量从模型返回的 content 中提取一个清晰的按钮文本字符串。
    优先解析 JSON（如 "\"院系设置\"" 这种），回退到提取首个引号内字符串，最终再回退到原文。
    """
    # 1) 先尝试按 JSON 解析（可能是一个被引号包裹的字符串）
    try:
        parsed = json.loads(content)
        # 直接是字符串
        if isinstance(parsed, str):
            return parsed.strip()
        # 字典或列表的容错提取
        if isinstance(parsed, dict):
            for key in ("button", "text", "label", "name", "answer", "output"):
                val = parsed.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        if isinstance(parsed, list) and parsed:
            # 取第一个字符串或字典中的 text
            first = parsed[0]
            if isinstance(first, str):
                return first.strip()
            if isinstance(first, dict):
                for key in ("button", "text", "label", "name"):
                    val = first.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
    except Exception:
        pass

    # 2) 尝试从引号中抓第一个片段
    try:
        import re
        m = re.search(r'["“](.+?)["”]', content)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    # 3) 最后回退到原文整体
    return content.strip()


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
    注意：仅输出结果的json格式，不要附加解释。每个学院的格式为：{{"name": "", "URL": ""}}。
    如果未识别出学院信息，则返回空字典。"""
    
    # 初始化客户端（DeepSeek 兼容 OpenAI SDK）
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
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
            temperature=1.0,
            max_tokens=4096,
        )

        # 获取模型返回的内容
        content = completion.choices[0].message.content if completion.choices else ""
        if not content:
            return {"status": "error", "message": "模型未返回内容"}

        return {
            "status": "success",
            "schools": content,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"API请求失败: {str(e)}",
        }
# if __name__ == "__main__":
#     # 建议使用环境变量提供API密钥，避免在代码中硬编码
#     DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"

#     if not DEEPSEEK_API_KEY:
#         print("未检测到环境变量 DEEPSEEK_API_KEY，跳过调用示例。请先设置后再运行本文件。")
#     else:
#         try:
#             # 读取示例与目标页面结构化列表（JSON转为字符串，减少不可读字符）
#             example_obj = read_json_file("example.json")
#             text_obj = read_json_file("北京大学.json")
#             example_text = _safe_json_dumps(example_obj)
#             text = _safe_json_dumps(text_obj)

#             result = extract_entities_with_deepseek(
#                 api_key=DEEPSEEK_API_KEY,
#                 text=text.replace("\n", ""),
#                 example=example_text,
#             )

#             if result.get("status") == "success":
#                 print("识别结果(按钮文本):", result.get("button_text"))
#             else:
#                 print("抽取失败:", result.get("message", "未知错误"))
#                 if "raw_response" in result:
#                     print("模型原始返回:", result.get("raw_response"))
#         except Exception as e:
#             print("运行示例失败:", e)
