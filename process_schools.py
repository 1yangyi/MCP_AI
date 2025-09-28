import requests
import json
import os
import re
from datetime import datetime
from pathlib import Path
from src.mcp_servers.ai import read_json_file, _safe_json_dumps, decide_click_or_extrect
from src.config import BROWSER_MCP_URL, HTML_PARSER_URL, PROJECT_ROOT
from openai import OpenAI
from urllib.parse import urljoin
import glob

# 中间文件目录
MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file2"
MIDDLE_FILE_DIR.mkdir(exist_ok=True)

DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"

def extract_entities_with_deepseek(api_key: str, text: str) -> dict:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    prompt = f"""
    你是一个数据收集助手，协助收集高校学院的教师信息。
    现在你需要根据以下页面网页结构化列表，判断哪一个最可能引导至包含所有教师信息的页面，并直接返回该按钮的文本和对应URL。
    链接列表：
    {text}
    请严格按以下格式输出一个最可能的按钮文本，不要任何额外解释：
    按钮文本@URL,例如，"师资力量@teachers.htm"
    注意：优先选择类似“教师队伍”、“师资力量”、“Faculty”、“Professors”等明确指向教师列表的链接。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    content = completion.choices[0].message.content
    parts = content.split('@', 1)
    return {"status": "success", "button_text": parts[0], "url": parts[1] if len(parts) > 1 else ""}

def decide_if_teacher_list(api_key: str, text: str) -> dict:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    prompt = f"""
    你是一个数据收集助手，用于识别网页内容是否包含某学院的全部教师名称及对应信息。
    请根据以下结构化内容进行判断：
    {text}
    若当前列表已完整包含该学院所有教师的名称和URL，则返回：True
    若列表仅包含分类而未列出具体教师，则返回：False
    注意：仅输出结果文本（True 或 False），无需任何解释。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    content = completion.choices[0].message.content.strip()
    return {"status": "success", "message": content}

def extract_teachers_with_deepseek(api_key: str, text: str) -> dict:
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    prompt = f"""
    你是一个数据收集助手，协助收集学院所有教师信息。
    请从以下网页结构化列表中识别出该学院所有教师的名称和URL。
    列表内容如下：
    {text}
    请以json格式直接返回该学院所有教师的信息。
    注意：仅输出结果的json格式，不要附加解释。每个教师的格式为：{{"name": "", "URL": ""}}。
    如果未识别出教师信息，则返回空列表。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0
    )
    content = completion.choices[0].message.content
    # 清理 content
    content = re.sub(r'^```json\s*|\s*```$', '', content).strip()
    try:
        teachers = json.loads(content)
    except json.JSONDecodeError:
        teachers = []
    return {"status": "success", "teachers": teachers}

def process_college_teachers(college_name: str, college_url: str):
    if not college_url.endswith("/"):
        college_url = college_url + "/"
    print(f"处理学院教师信息: {college_name} ({college_url})")
    current_url = college_url.replace("http://", "https://") if college_url.startswith("http://") else college_url
    # 导航到学院URL
    print(f"导航到学院URL: {current_url}")
    navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": current_url, "wait_time": 2})
    if navigate_response.status_code != 200:
        print(f"导航到学院URL失败: {college_url}")
        return []

    # 获取HTML并解析
    parse_response = requests.post(f"{HTML_PARSER_URL}/parse", json={"url": college_url, "output_prefix": college_name, "output_dir": str(MIDDLE_FILE_DIR)})
    if parse_response.status_code != 200:
        print(f"解析学院HTML失败: {college_url}")
        return []

    try:
        # 读取解析的JSON
        html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}.json")
        html_text = _safe_json_dumps(html_obj)
    except FileNotFoundError:
        print(f"学院HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}.json")
        return []

    count = 0
    is_teacher_list = "False"
    while is_teacher_list != "True" and count < 2:
        count += 1
        result_link = extract_entities_with_deepseek(DEEPSEEK_API_KEY, html_text)
        if result_link["status"] != "success":
            continue
        button_text = result_link["button_text"]
        click_url = result_link["url"]
        print(f"点击按钮文本: {button_text}, URL: {click_url}")

        print(f"当前URL: {current_url}")
        print(f"点击URL: {click_url}")
        click_url = urljoin(current_url, click_url)
        print(f"合并后的URL: {click_url}")
        

        if click_url.startswith('http://'):
            click_url = 'https://' + click_url[7:]

        # 导航到教师页面
        print(f"导航到教师页面: {click_url}")
        requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": click_url, "wait_time": 3})
        current_url = click_url  # 更新当前 URL

        # 解析新页面HTML
        print(f"解析教师页面HTML: {click_url}")
        new_parse_response = requests.post(f"{HTML_PARSER_URL}/parse", json={"url": click_url, "output_prefix": f"{college_name}_teachers", "output_dir": str(MIDDLE_FILE_DIR)})
        if new_parse_response.status_code != 200:
            print(f"解析教师页面HTML失败: {click_url}")
            continue

        try:
            html_obj = read_json_file(f"{MIDDLE_FILE_DIR}\{college_name}_teachers.json")
            html_text = _safe_json_dumps(html_obj)
        except FileNotFoundError:
            print(f"教师页面HTML文件不存在: {MIDDLE_FILE_DIR}\{college_name}_teachers.json")
            continue

        # 检查是否为教师列表
        decide_result = decide_if_teacher_list(DEEPSEEK_API_KEY, html_text)
        is_teacher_list = decide_result["message"]

    
    print("正在提取教师信息...")
    extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
    return extract_result["teachers"]


if __name__ == "__main__":
    # Load school websites
    chinese_schools_path = PROJECT_ROOT / "chinese_schools.json"
    with open(chinese_schools_path, 'r', encoding='utf-8') as f:
        schools_data = json.load(f)
    school_urls = {school['name']: school['website'] for school in schools_data}

    input_dir = PROJECT_ROOT / "data" / "output_chinese"
    output_base = PROJECT_ROOT / "data" / "schools"

    for school in schools_data:
        university_name = school['name']
        school_website = school['website']
        matching_files = list(input_dir.glob(f"*_{university_name}_schools_result.json"))
        if not matching_files:
            print(f"Skipping {university_name}: no JSON file found in output_chinese")
            continue
        if len(matching_files) > 1:
            print(f"Warning: Multiple JSON files found for {university_name}, using the first one")
        json_path = matching_files[0]
        print(f"Processing university: {university_name} using {json_path}")

        with open(json_path, 'r', encoding='utf-8') as f:
            colleges = json.load(f)

        output_dir = output_base / university_name
        os.makedirs(output_dir, exist_ok=True)

        for college in colleges:
            college_name = college["name"]
            college_url = college["URL"]
            if not college_url.startswith("http"):
                college_url = urljoin(school_website, college_url)
            teachers = process_college_teachers(college_name, college_url)
            file_path = output_dir / f"{college_name}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(teachers, f, ensure_ascii=False, indent=4)
            print(f"Saved {college_name} teachers to {file_path}")