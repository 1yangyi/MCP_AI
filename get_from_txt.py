import json
import re
import ast
from urllib.parse import urljoin
DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"
from openai import OpenAI



def extract_teachers_with_deepseek(api_key: str, text: str) -> dict:
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception as e:
        return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
    prompt = f"""
    你是一个数据收集助手。
    请从以下信息中提取出所有人名和对应的URL：
    {text}
    注意：仅输出结果的json格式，不要附加解释。每个人的信息的格式为：{{"name": "", "URL": ""}}。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
        temperature=0.1
    )
    content = completion.choices[0].message.content
    # 清理 content
    content = re.sub(r'^```json\s*|\s*```$', '', content).strip()
    try:
        teachers = json.loads(content)
    except json.JSONDecodeError:
        teachers = []
    return {"status": "success", "teachers": teachers}

def extract_schools_with_deepseek(api_key: str, text: str) -> dict:
    """
    使用DeepSeek API从网页结构化列表中识别出该学校所有科研机构所在的位置（按钮）。

    参数:
        api_key (str): DeepSeek API密钥（不应硬编码，建议使用环境变量 DEEPSEEK_API_KEY）
        text (str): 网页结构化列表（建议提供JSON字符串）

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

    # # 构造提示词
    
    prompt = f"""
    你是一个数据收集助手，协助收集高校所有科研机构信息。
    请从以下网页html原码中识别出该学校所有科研机构的名称和URL（如果有）。html原码内容如下：
    {text}
    注意：只需要提取科研机构，不包含学院（如文学院、计算机学院等）和行政机构（如行政办公室、科学技术处、图书馆等）。
    注意：仅输出结果的json格式，不要附加解释。每个科研机构的格式为：{{"name": "", "URL": ""}}。
    如果某些研究机构只找到了名字而没有URL，也需要保留该机构，URL项置空。
    如果未识别出科研机构信息，则返回空字典。"""

    prompt = f"""
    你是一个数据收集助手，协助收集高校所有学院信息。
    请从以下网页结构化列表中识别出该学校所有学院或学术部门的名称和URL。列表内容如下：
    {text}
    注意：如果某些学院属于更上层的学部（例如“School of Engineering”下属多个子学院或学系），应提取具体的子学院信息（如“Aeronautics and Astronautics”、“Biological Engineering”等），而非仅提取上级学部。
    请以json格式直接返回该学校所有学院或学术部门的名称和URL。
    注意：仅输出结果的json格式，不要附加解释。每个学院或学术部门的格式为：{{"name": "", "URL": ""}}。
    如果未识别出学院或学术部门信息，则返回空字典。"""
    
    # prompt = f"""
    # 你是一个数据收集助手，协助收集高校所有学院信息。
    # 请从以下网页结构化列表中识别出该学校所有学院或学术部门的名称和URL。列表内容如下：
    # {text}
    # 注意：如果某些学院属于更上层的学部（例如“School of Engineering”下属多个子学院或学系），应提取具体的子学院信息（如“Aeronautics and Astronautics”、“Biological Engineering”等），而非仅提取上级学部。
    # 请以json格式直接返回该学校所有学院或学术部门的名称和URL。
    # 注意：仅输出结果的json格式，不要附加解释。每个学院或学术部门的格式为：{{"name": "", "URL": ""}}。
    # 如果未识别出学院或学术部门信息，则返回空字典。"""
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
            max_tokens=8000,
            temperature=0.05,
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

def extract_and_normalize(text: str) -> list:
    schools_result = extract_schools_with_deepseek(
        api_key=DEEPSEEK_API_KEY,
        text=text.replace("\n", "")
    )
    
    if schools_result.get("status") != "success":
        print(f"提取失败: {schools_result.get('message')}")
        return []
    
    schools_list = schools_result.get("schools")

    
    try:
        if isinstance(schools_list, (list, dict)):
            data = schools_list if isinstance(schools_list, list) else [schools_list]
        else:
            raw_text = (schools_list or "").lstrip('\ufeff').strip()
            fence_match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", raw_text)
            if fence_match:
                raw_text = fence_match.group(1).strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            raw_text = raw_text.replace("`", "")
            if '[' in raw_text and ']' in raw_text:
                raw_text = raw_text[raw_text.find('['): raw_text.rfind(']') + 1]
            try:
                data = json.loads(raw_text)
            except Exception:
                try:
                    data = ast.literal_eval(raw_text)
                except Exception:
                    data = []
        
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
        return norm
    
    except Exception as e:
        print(f"处理数据时出错: {e}")
        return []

# 从txt文件中读取内容
# 如果知道文件编码，最好明确指定
with open('html.txt', 'r', encoding='utf-8') as file:
    text_content = file.read()

# all_norm = extract_and_normalize(text_content)
extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, text_content)
print(extract_result)
current_page_teachers = extract_result["teachers"]
for item in current_page_teachers:
    if item["URL"] is None:
        item["URL"] = ""
    if item["URL"] is not None:
        if not item["URL"].startswith("http"):
            item["URL"] = urljoin("https://ngce.sustech.edu.cn/#/tutor?alias=f0a303ea-9f2a-4cee-8454-f966c9ba6896", item["URL"])
print(json.dumps(current_page_teachers, ensure_ascii=False, indent=2))
