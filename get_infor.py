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
from process_lost import _limit_text_by_tokens
import glob
import logging

# 中间文件目录
MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file2"
MIDDLE_FILE_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    filename=str(PROJECT_ROOT / "logs" / "college_processing.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"
TOKEN_LIMIT = 120000


def extract_intro_button(api_key: str, text: str) -> dict:
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception as e:
        error_msg = f"Deepseek API 初始化失败: {str(e)}"
        logger.exception(error_msg)
        return {"status": "error", "message": error_msg}
    prompt = f"""
    你是一个数据收集助手，协助收集高校学院的简介信息。
    现在你需要根据以下页面网页结构化列表，判断哪一个最可能引导至包含学院简介的页面，并直接返回该按钮的文本和对应URL。
    链接列表：
    {text}
    请严格按以下格式输出一个最可能的按钮文本，不要任何额外解释：
    按钮文本@URL,例如，"学院简介@introduction.htm"
    注意：优先选择类似“学院简介”、“Introduction”、“About Us”、“学院概况”等明确指向学院简介的链接。
    """
    try:
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        content = completion.choices[0].message.content
        parts = content.split('@', 1)
        return {"status": "success", "button_text": parts[0], "url": parts[1] if len(parts) > 1 else ""}
    except Exception as e:
        error_msg = f"Deepseek API 调用失败: {str(e)}"
        logger.exception(error_msg)
        return {"status": "error", "message": error_msg}


def process_college_teachers(university_name: str, college_name: str, college_url: str, output_dir: Path):
    try:
        teacher_folder = output_dir / college_name
        safe_path = (college_name.replace('\\', '_')
                          .replace('/', '_')
                          .replace(':', '_')
                          .replace('*', '_')
                          .replace('?', '_')
                          .replace('"', '_')
                          .replace('<', '_')
                          .replace('>', '_')
                          .replace('|', '_')
                          .strip())
        teacher_folder = output_dir / safe_path
        os.makedirs(teacher_folder, exist_ok=True)
    except Exception as e:
        logger.exception(f"创建教师文件夹失败 for {college_name}: {str(e)}")
        return []
    if college_url == '':
        return []
    if not college_url.endswith("/"):
        college_url = college_url + "/"
    print(f"处理学院教师信息: {university_name} {college_name} ({college_url})")
    logger.info(f"处理学院教师信息: {university_name} {college_name} ({college_url})")
    current_url = college_url.replace("http://", "https://") if college_url.startswith("http://") else college_url
    # 导航到学院URL
    print(f"导航到学院URL: {current_url}")
    logger.info(f"导航到学院URL: {current_url}")
    try:
        navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": current_url, "wait_time": 2})
        if navigate_response.status_code != 200:
            error_msg = f"导航到学院URL失败: {college_url} (状态码: {navigate_response.status_code})"
            print(error_msg)
            logger.error(error_msg)
            return []
    except Exception as e:
        logger.exception(f"导航到学院URL时发生异常: {college_url}")
        return []

    # 获取HTML并解析
    try:
        parse_response = requests.post(f"{HTML_PARSER_URL}/parse", json={"url": college_url, "output_prefix": university_name+'_'+college_name, "output_dir": str(MIDDLE_FILE_DIR)})
        if parse_response.status_code != 200:
            error_msg = f"解析学院HTML失败: {college_url} (状态码: {parse_response.status_code})"
            print(error_msg)
            logger.error(error_msg)
    except Exception as e:
        logger.exception(f"解析学院HTML时发生异常: {college_url}")

    try:
        # 读取解析的JSON
        html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{university_name}_{college_name}.json")
        html_text = _safe_json_dumps(html_obj)
    except FileNotFoundError:
        error_msg = f"学院HTML文件不存在: {MIDDLE_FILE_DIR}/{university_name}_{college_name}.json"
        print(error_msg)
        logger.error(error_msg)
        # 获取当前页面的HTML原码
        try:
            current_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
            if current_page_response.status_code == 200:
                html_content = current_page_response.json()['html']
                html_text = html_content  # 使用HTML原码作为html_text
                print('html_text:', html_text)
                print(f"获取HTML成功，HTML长度: {len(html_text)}字符")
                logger.info(f"获取HTML成功，HTML长度: {len(html_text)}字符")
                html_text = _limit_text_by_tokens(html_text, TOKEN_LIMIT)
                print(f"限制HTML长度为 {TOKEN_LIMIT} 个token，实际长度: {len(html_text)}字符")
                logger.info(f"限制HTML长度为 {TOKEN_LIMIT} 个token，实际长度: {len(html_text)}字符")
            else:
                error_msg = f"获取学院页面HTML失败: {college_url} (状态码: {current_page_response.status_code})"
                print(error_msg)
                logger.error(error_msg)
                return []
        except Exception as e:
            logger.exception(f"获取学院页面HTML时发生异常: {college_url}")
            return []
    except Exception as e:
        logger.exception(f"读取或处理HTML文件时发生异常: {college_url}")
        return []

    # 新增：寻找并保存学院简介
    print("开始寻找学院简介...")
    logger.info("开始寻找学院简介...")
    intro_result = extract_intro_button(DEEPSEEK_API_KEY, html_text)
    if intro_result["status"] == "success" and intro_result["url"]:
        intro_url = urljoin(current_url, intro_result["url"])
        if intro_url.startswith('http://'):
            intro_url = 'https://' + intro_url[7:]
        print(f"导航到学院简介页面: {intro_url}")
        logger.info(f"导航到学院简介页面: {intro_url}")
        try:
            navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": intro_url, "wait_time": 2})
            if navigate_response.status_code == 200:
                current_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
                if current_page_response.status_code == 200:
                    html_content = current_page_response.json()['html']
                    if not html_content.strip():
                        warning_msg = f"学院简介页面为空: {intro_url}"
                        print(warning_msg)
                        logger.warning(warning_msg)
                    else:
                        intro_file = teacher_folder / f"{college_name}_intro.html"
                        with open(intro_file, 'w', encoding='utf-8') as file:
                            file.write(html_content)
                        print(f"保存学院简介 HTML 到 {intro_file}")
                        logger.info(f"保存学院简介 HTML 到 {intro_file}")
                else:
                    error_msg = f"获取学院简介页面HTML失败: {intro_url} (状态码: {current_page_response.status_code})"
                    print(error_msg)
                    logger.error(error_msg)
            else:
                error_msg = f"导航到学院简介页面失败: {intro_url} (状态码: {navigate_response.status_code})"
                print(error_msg)
                logger.error(error_msg)
        except Exception as e:
            logger.exception(f"处理学院简介页面时发生异常: {intro_url}")
        # 导航回学院主页面
        print(f"导航回学院主页面: {current_url}")
        logger.info(f"导航回学院主页面: {current_url}")
        try:
            requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": current_url, "wait_time": 2})
        except Exception as e:
            logger.exception(f"导航回学院主页面时发生异常: {current_url}")
    else:
        warning_msg = f"未找到学院简介按钮 for {college_name}"
        print(warning_msg)
        logger.warning(warning_msg)
    return []


# if __name__ == "__main__":
#     try:
#         # Load school websites
#         chinese_schools_path = PROJECT_ROOT / "data" / "input" / "chinese_schoolsURL.json"
#         with open(chinese_schools_path, 'r', encoding='utf-8') as f:
#             schools_data = json.load(f)
#     except Exception as e:
#         logger.exception(f"加载学校数据失败: {str(e)}")
#         exit(1)
#     rank = 0
#     input_dir = PROJECT_ROOT / "data" / "output_chinese2"
#     output_base = PROJECT_ROOT / "data" / "schools2"
#     for school in schools_data:
#         university_name = school['name']
#         school_website = school['website']
#         rank += 1
#         # if int(rank) <= 60:
#         #     continue
#         # chinese_list = ['清华大学', '哈尔滨工业大学', '北京大学', '浙江大学', '南京大学', '上海交通大学','复旦大学','中国科学技术大学','同济大学','武汉大学','天津大学','北京师范大学','南方科技大学','西安交通大学','华中科技大学']
#         # if university_name in chinese_list:
#         #     continue
#         try:
#             matching_files = list(input_dir.glob(f"*_{university_name}_schools_result.json"))
#             if not matching_files:
#                 print(f"Skipping {university_name}: no JSON file found in output_chinese")
#                 logger.info(f"Skipping {university_name}: no JSON file found in output_chinese")
#                 continue
#             if len(matching_files) > 1:
#                 print(f"Warning: Multiple JSON files found for {university_name}, using the first one")
#                 logger.warning(f"Multiple JSON files found for {university_name}, using the first one")
#             json_path = matching_files[0]
#             print(f"Processing university: {university_name} using {json_path}\n")
#             with open(json_path, 'r', encoding='utf-8') as f:
#                 colleges = json.load(f)
#         except Exception as e:
#             logger.exception(f"处理大学 {university_name} 时发生异常: {str(e)}")
#             continue

#         try:
#             output_dir = output_base / f"{rank}_{university_name}"
#             os.makedirs(output_dir, exist_ok=True)
#         except Exception as e:
#             logger.exception(f"创建输出目录失败 for {university_name}: {str(e)}")
#             continue

#         for college in colleges:
#             try:
#                 college_name = college["name"]
#                 college_url = college["URL"]
#                 if college_url == '':

#                     continue
#                 if not college_url.startswith("http"):
#                     college_url = urljoin(school_website, college_url)
#                 process_college_teachers(university_name,college_name, college_url, output_dir)
#             except Exception as e:
#                 logger.exception(f"处理学院 {college_name} 时发生异常: {str(e)}")
#                 continue




if __name__ == "__main__":
    output_base = PROJECT_ROOT / "data" / "schools"
    university_name = '东北大学'

    json_path = 'D:/project08/MCP_AI/data/output_chinese/37_东北大学_schools_result.json'
    print("处理东北大学")
    with open(json_path, 'r', encoding='utf-8') as f:
        colleges = json.load(f)
        print(colleges)

    try:
        output_dir = output_base / university_name
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        logger.exception(f"创建输出目录失败 for {university_name}: {str(e)}")

    for college in colleges:
        if not college["URL"].startswith('http'):
            continue
        try:
            college_name = college["name"]
            college_url = college["URL"]
            if not college_url.startswith("http"):
                college_url = urljoin(school_website, college_url)
            process_college_teachers(university_name,college_name, college_url, output_dir)
        except Exception as e:
            logger.exception(f"处理学院 {college_name} 时发生异常: {str(e)}")
            continue
