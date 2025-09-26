import requests
import json
import os
import time
import re
import ast
from datetime import datetime
from pathlib import Path
from src.mcp_servers.ai import extract_entities_with_deepseek,extract_schools_with_deepseek,decide_click_or_extrect
# 从配置文件导入服务器URL和目录配置
from src.config import BROWSER_MCP_URL, OUTPUT_DIR, PROJECT_ROOT
try:
    from deepseek_v3_tokenizer.deepseek_tokenizer import get_tokenizer as _ds_get_tokenizer
except Exception:
    _ds_get_tokenizer = None

# 确保输出目录存在
RESULTS_DIR = OUTPUT_DIR
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# 创建中间文件目录
MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file"
MIDDLE_FILE_DIR.mkdir(exist_ok=True)

from deepseek_v3_tokenizer.deepseek_tokenizer import get_tokenizer
DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"

# 基于token数量限制文本长度
TOKEN_LIMIT = 120000

def _token_len(s: str) -> int:
    try:
        if _ds_get_tokenizer is None:
            raise RuntimeError("tokenizer not available")
        toks = _ds_get_tokenizer(s)
        return len(toks)
    except Exception:
        # 保守估计：按 1 token / 1 字符，保证永不超限
        return len(s)


def _limit_text_by_tokens(text: str, max_tokens: int = TOKEN_LIMIT) -> str:
    try:
        # 1) 快速路径
        if _token_len(text) <= max_tokens:
            return text

        # 2) 采样估计 tokens/char 比率（<= 4096 字符），取安全系数 0.85
        sample_chars = min(len(text), 4096)
        if sample_chars <= 0:
            return ""
        sample = text[:sample_chars]
        ratio = _token_len(sample) / max(sample_chars, 1)
        if ratio <= 0:
            ratio = 1.0  # 极端兜底，保证安全

        # 3) 保守初截：根据估计比率留安全余量
        target_chars = int(max_tokens / ratio * 0.85)
        target_chars = max(1, min(target_chars, len(text)))
        truncated = text[:target_chars]

        # 4) 校验与快速收缩（最多 4 轮）
        for _ in range(4):
            tlen = _token_len(truncated)
            if tlen < max_tokens:
                return truncated
            overflow = tlen - max_tokens
            # 将超出 token 数折算为字符，并加额外冗余 1024 字符
            drop_chars = int(overflow / max(ratio, 1e-6)) + 1024
            # 每次至少删 1024 字符，避免小步振荡；同时限制最大步长
            drop_chars = max(1024, min(drop_chars, len(truncated) // 3 if len(truncated) > 3000 else len(truncated)))
            new_len = len(truncated) - drop_chars
            if new_len <= 0:
                return ""
            truncated = truncated[:new_len]

        # 5) 兜底回退：指数级收缩直至满足
        while len(truncated) > 0 and _token_len(truncated) >= max_tokens:
            truncated = truncated[: max(1, len(truncated) // 2)]
        return truncated
    except Exception:
        # 6) 出错时保守兜底：按字符直接截，确保最终 < 上限
        approx = text[: min(len(text), max_tokens)]
        while len(approx) > 0 and _token_len(approx) >= max_tokens:
            approx = approx[: max(1, len(approx) // 2)]
        return approx


def process_lost_university_website(university_name: str, university_url: str, rank: int):
    print(f"开始处理{university_name}网站({university_url}) [raw-HTML模式]")

    result = {
        "university": {
            "name": university_name,
            "website": university_url
        },
        "pages_visited": [],
        "collected_data": {},
        "timestamp": datetime.now().isoformat()
    }

    try:
        # 步骤1: 使用browser.py导航到指定学校
        print(f"\n1. 使用browser.py导航到{university_url}...")
        navigate_response = requests.post(
            f"{BROWSER_MCP_URL}/navigate",
            json={"url": university_url, "wait_time": 2}  # 减少等待时间
        )
        if navigate_response.status_code != 200:
            print(f"导航失败: {navigate_response.text}")
            return

        navigate_data = navigate_response.json()
        print(f"导航成功: {navigate_data['message']}")
        print(f"页面标题: {navigate_data['title']}")
        print(f"当前URL: {navigate_data['url']}")

        # 记录访问的页面
        result["pages_visited"].append({
            "url": navigate_data["url"],
            "title": navigate_data["title"],
            "timestamp": datetime.now().isoformat()
        })

        # 步骤2: 获取当前页面的HTML内容
        print("\n2. 获取当前页面的HTML内容...")
        current_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
        if current_page_response.status_code != 200:
            print(f"获取页面内容失败: {current_page_response.text}")
            return

        current_page_data = current_page_response.json()
        html_content = current_page_data['html']
        current_url = current_page_data['url']
        print(f"获取HTML成功，HTML长度: {len(html_content)}字符")

        # 直接使用原始HTML（不使用html_extractor）
        print("\n3. 直接使用HTML原码进行识别(不使用html_extractor)...")
        # token截断
        _text0 = html_content.replace("\n", "")
        _text0 = _limit_text_by_tokens(_text0, TOKEN_LIMIT)
        result_link = extract_entities_with_deepseek(
            api_key=DEEPSEEK_API_KEY,
            text=_text0,
            example='',
        )
        print(f"result_link:{result_link}")
        parts = result_link.get("button_text", "@").split('@', 1)
        button_text = parts[0]
        click_url = parts[1] if len(parts) > 1 else ""
        click_url = click_url.lstrip('/')

        if result_link.get("status") == "success":
            print("识别结果(按钮文本):", button_text)
        else:
            print("抽取失败:", result_link.get("message", "未知错误"))
            if "raw_response" in result_link:
                print("模型原始返回:", result_link.get("raw_response"))

        # 规范化URL为绝对路径
        if not click_url.startswith("http") and not click_url.startswith("www."):
            base_url = university_url if university_url.endswith("/") else f"{university_url}/"
            click_url = base_url + click_url
        if click_url.startswith("www."):
            click_url = "https://" + click_url

        print(f"导航到URL: {click_url}")
        # 直接导航到URL
        click_response = requests.post(
            f"{BROWSER_MCP_URL}/navigate",
            json={"url": click_url, "wait_time": 3}
        )
        if click_response.status_code != 200:
            print(f"点击链接失败: {click_response.text}")

        click_data = click_response.json()
        print(f"点击成功，新页面标题: {click_data['title']}")
        print(f"新页面URL: {click_data['url']}")

        # 记录访问的页面
        result["pages_visited"].append({
            "url": click_data["url"],
            "title": click_data["title"],
            "timestamp": datetime.now().isoformat()
        })

        # 获取新页面的HTML（不解析，直接传给模型）
        print("\n5. 获取院系页面HTML(不使用html_extractor解析)...")
        new_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
        if new_page_response.status_code != 200:
            print(f"获取新页面内容失败: {new_page_response.text}")
            return
        new_page_data = new_page_response.json()
        html_text = new_page_data['html']

        # token截断
        _text1 = html_text.replace("\n", "")
        _text1 = _limit_text_by_tokens(_text1, TOKEN_LIMIT)
        result1 = decide_click_or_extrect(
            api_key=DEEPSEEK_API_KEY,
            text=_text1
        )
        Identity_result = result1.get("message")
        print("Identity_result: ", Identity_result)

        # 循环：如果还不是最终包含所有学院信息的页面，则继续点击
        count = 0
        while Identity_result != 'True':
            count += 1
            if count > 2:
                break

            # token截断
            _text_loop = html_text.replace("\n", "")
            _text_loop = _limit_text_by_tokens(_text_loop, TOKEN_LIMIT)
            result_link = extract_entities_with_deepseek(
                api_key=DEEPSEEK_API_KEY,
                text=_text_loop,
                example='',
            )
            print(f"result_link:{result_link}")
            parts = result_link.get("button_text", "@").split('@', 1)
            button_text = parts[0]
            click_url = parts[1] if len(parts) > 1 else ""
            click_url = click_url.lstrip('/')

            if result_link.get("status") == "success":
                print("下一个点击的按钮:", button_text)
            else:
                print("抽取失败:", result_link.get("message", "未知错误"))
                if "raw_response" in result_link:
                    print("模型原始返回:", result_link.get("raw_response"))

            # 将click_url转换为绝对URL
            if not click_url.startswith("http") and not click_url.startswith("www."):
                base_url = university_url if university_url.endswith("/") else f"{university_url}/"
                click_url = base_url + click_url
            if click_url.startswith("www."):
                click_url = "https://" + click_url

            print("正在前往页面:", click_url)
            click_response = requests.post(
                f"{BROWSER_MCP_URL}/navigate",
                json={"url": click_url, "wait_time": 3}
            )
            if click_response.status_code != 200:
                print(f"点击链接失败: {click_response.text}")
                break

            # 获取当前页面HTML
            new_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
            if new_page_response.status_code != 200:
                print(f"获取页面内容失败: {new_page_response.text}")
                break
            new_page_data = new_page_response.json()
            html_text = new_page_data['html']
            print('新页面已获取HTML...')

            # token截断
            _text2 = html_text.replace("\n", "")
            _text2 = _limit_text_by_tokens(_text2, TOKEN_LIMIT)
            result1 = decide_click_or_extrect(
                api_key=DEEPSEEK_API_KEY,
                text=_text2
            )
            Identity_result = result1.get("message")
            print("新的Identity_result: ", Identity_result)

        # 到此，html_text 为最终页面HTML，直接抽取学院列表
        _text3 = html_text.replace("\n", "")
        _text3 = _limit_text_by_tokens(_text3, TOKEN_LIMIT)
        schools_result = extract_schools_with_deepseek(
            api_key=DEEPSEEK_API_KEY,
            text=_text3
        )
        schools_list = schools_result.get("schools")

        # 指定保存路径到输出目录
        file_path = RESULTS_DIR / f"{rank}_{university_name}_schools_result.json"

        # 将字符串数据保存为JSON文件
        try:
            # 如果已经是列表/字典，直接使用
            if isinstance(schools_list, (list, dict)):
                data = schools_list if isinstance(schools_list, list) else [schools_list]
            else:
                raw_text = (schools_list or "").lstrip('\ufeff').strip()
                # 去除代码块包裹 ```json ... ``` 或 ``` ... ```
                fence_match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", raw_text)
                if fence_match:
                    raw_text = fence_match.group(1).strip()
                # 如果仍包含围栏，清理所有反引号
                if raw_text.startswith("```"):
                    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                # 去掉所有孤立反引号（例如 URL 中的 `...`）
                raw_text = raw_text.replace("`", "")
                # 裁剪到首个 [ 与最后一个 ] 之间，去除模型多余描述
                if '[' in raw_text and ']' in raw_text:
                    raw_text = raw_text[raw_text.find('['): raw_text.rfind(']') + 1]
                # 首选严格 JSON 解析
                try:
                    data = json.loads(raw_text)
                except Exception:
                    # 兼容单引号/尾逗号等 Python 风格
                    try:
                        data = ast.literal_eval(raw_text)
                    except Exception:
                        # 解析失败则使用空列表
                        data = []
            # 归一化清洗字段
            norm = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get('name')
                        url = item.get('URL') or item.get('url') or item.get('link')
                        if isinstance(url, str):
                            u = url.strip().strip('`').strip().strip('"').strip("'")
                            norm.append({"name": name, "URL": u})
                        else:
                            norm.append({"name": name, "URL": url})
            else:
                norm = []

            # 确保目录存在
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # 写入JSON文件
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(norm, file, ensure_ascii=False, indent=2)

            print(f"JSON数据已成功写入文件: {file_path}")
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            # 写入空列表作为回退值
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump([], file, ensure_ascii=False, indent=2)
            print(f"已写入空列表作为回退值到: {file_path}")
        except IOError as e:
            print(f"写入文件时出错: {e}")
        except Exception as e:
            print(f"处理数据时出错: {e}")

    except Exception as e:
        print(f"处理过程中出错: {str(e)}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    from check import get_missing_list
    missing_list = get_missing_list()
    i = 0
    for item in missing_list:
        print(f"Rank: {item[0]}, School: {item[1]}, Website: {item[2]}")
        process_lost_university_website(item[1], item[2], item[0])
        i += 1
        print(f"{i}/{len(missing_list)}:{item[0]}_{item[1]} 已处理完成")