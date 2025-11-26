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
from extract import extract_teacher_button,check_next_page,check_similar_page,decide_if_teacher_list,extract_teachers_with_deepseek
import concurrent.futures
import threading
import logging
from get_html import get_html
from src.mcp_servers.extractor import parse_html
# 中间文件目录
MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file2"
MIDDLE_FILE_DIR.mkdir(exist_ok=True)

DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"
TOKEN_LIMIT = 120000
"""
使用get_html获取网页原码，使用parse_html解析网页原码
"""
browser_lock = threading.Lock()


# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)

# Ensure logs directory exists
logs_dir = PROJECT_ROOT / "logs"
logs_dir.mkdir(exist_ok=True)

# Add FileHandler for detailed logs
detailed_handler = logging.FileHandler(logs_dir / "detailed.log")
detailed_handler.setLevel(logging.INFO)
detailed_handler.setFormatter(logging.Formatter('%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(detailed_handler)

# Create separate logger for exceptions
exceptions_logger = logging.getLogger('exceptions')
exceptions_logger.setLevel(logging.INFO)
exceptions_handler = logging.FileHandler(logs_dir / "exceptions.log")
exceptions_handler.setLevel(logging.INFO)
exceptions_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
exceptions_logger.addHandler(exceptions_handler)

def process_college_teachers(university_name: str, college_name: str, college_url: str, output_dir: Path):
    sanitized_name = college_name.replace('/', '_').replace('\\', '_')
    teacher_folder = output_dir / sanitized_name
    os.makedirs(teacher_folder, exist_ok=True)
    if not college_url.endswith("/"):
        college_url = college_url + "/"
    logging.info(f"处理学院教师信息: {university_name} {college_name} ({college_url})")
    current_url = college_url
    # with browser_lock:
    #     # 导航到学院URL
    #     logging.info(f"导航到学院URL: {current_url}")
    #     navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": current_url, "wait_time": 2})
    #     if navigate_response.status_code != 200:
    #         logging.info(f"导航到学院URL失败: {college_url}")
    #         return []

    #     # 获取HTML并解析
    #     parse_response = requests.post(f"{HTML_PARSER_URL}/parse", json={"url": college_url, "output_prefix": university_name+'_'+college_name, "output_dir": str(MIDDLE_FILE_DIR)})
    #     if parse_response.status_code != 200:
    #         logging.info(f"解析学院HTML失败: {college_url}")

    # try:
    #     # 读取解析的JSON
    #     html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{university_name}_{college_name}.json")
    #     html_text = _safe_json_dumps(html_obj)
    # except FileNotFoundError:
    #     logging.info(f"学院HTML文件不存在: {MIDDLE_FILE_DIR}/{university_name}_{college_name}.json")
    #     with browser_lock:
    #         # 获取当前页面的HTML原码
    #         current_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
    #         if current_page_response.status_code == 200:
    #             html_content = current_page_response.json()['html']
    #             html_text = html_content  # 使用HTML原码作为html_text
    #             logging.info(f"获取HTML成功，HTML长度: {len(html_text)}字符")
    #             html_text = _limit_text_by_tokens(html_text, TOKEN_LIMIT)
    #             logging.info(f"限制HTML长度为 {TOKEN_LIMIT} 个token，实际长度: {len(html_text)}字符")
    #         else:
    #             logging.info(f"获取学院页面HTML失败: {college_url}")
    #             return []
    html_text = get_html(current_url)
    html_text = parse_html(html_text)
    count = 0
    button_url = ""
    is_teacher_list = "False"
    while is_teacher_list != "True" and count < 2:
        count += 1
        result_link = extract_teacher_button(DEEPSEEK_API_KEY, html_text)
        if result_link["status"] != "success":
            logging.info(f"未找到教师按钮: {result_link['message']}")
            continue
        button_text = result_link["button_text"]
        click_url = result_link["url"]
        button_url = click_url
        logging.info(f"点击按钮文本: {button_text}, URL: {click_url}")

        logging.info(f"当前URL: {current_url}")
        logging.info(f"点击URL: {click_url}")
        click_url = urljoin(current_url, click_url)
        logging.info(f"合并后的URL: {click_url}")
        logging.info('-----------------')

        html_text = get_html(click_url)
        html_text = parse_html(html_text)

        # 检查是否为教师列表
        decide_result = decide_if_teacher_list(DEEPSEEK_API_KEY, html_text)
        is_teacher_list = decide_result["message"]
        logging.info(f"是否为教师列表: {is_teacher_list}")

    logging.info("正在提取教师信息...")
    all_teachers = []
    page_count = 1
    extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
    first_html_text = html_text
    first_html_url = current_url
    current_page_teachers = extract_result["teachers"]
    # print(f"当前页面教师URL: {current_page_teachers[0]}")
    # print(current_url)
    for teacher in current_page_teachers:
        teacher["URL"] = urljoin(current_url, teacher["URL"])
    all_teachers.extend(current_page_teachers)
    # print(f"合并后的教师URL: {current_page_teachers[0]}")
    logging.info(f"第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")


    # 检查是否有下一页
    all_url_list = []
    while True:
        next_page_result = check_next_page(DEEPSEEK_API_KEY, html_text)
        if not next_page_result["has_next"] or not next_page_result["next_url"]:
            logging.info("没有更多页面，教师信息提取完成")
            break
        # 获取下一页URL
        next_url = next_page_result["next_url"]
        if not next_url.startswith("http"):
            next_url = urljoin(current_url, next_url)
        

        if next_url in all_url_list:
            logging.info(f"发现重复URL: {next_url}，停止翻页")
            break
        all_url_list.append(next_url)
        
        logging.info(f"发现下一页，导航到: {next_url}")
        page_count += 1
      
        html_text = get_html(next_url)
        html_text = parse_html(html_text)
        # 提取下一页的教师信息
        extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
        current_page_teachers = extract_result["teachers"]
        for teacher in current_page_teachers:
            teacher["URL"] = urljoin(current_url, teacher["URL"])
        all_teachers.extend(current_page_teachers)
        logging.info(f"第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师\n")
    
    logging.info(f"总共提取到 {len(all_teachers)} 位教师信息")

    # 检查是否有相似页面
    logging.info("\n开始检查相似页面...")
    logging.info(f"当前按钮或链接的URL为：{button_url}")
    similar_page_result = check_similar_page(DEEPSEEK_API_KEY, first_html_text,button_url)
    logging.info(f"检查相似页面结果: {similar_page_result}")
    
    # part to modify:
    if similar_page_result.get("status") == "success" and similar_page_result["has_next"]:
        for similar in similar_page_result["next_urls"]:
            similar_url = similar["url"]
            similar_name = similar["name"]
            original_url = similar_url  # 保存原始URL用于调试

            # 标准化URL路径
            if not similar_url.startswith("http"):
                logging.info(f"相似页面URL不是绝对路径: {similar_url}")
                logging.info(f"原始URL: {first_html_url}")
                similar_url = urljoin(first_html_url, similar_url)
                logging.info(f"标准化后的相似页面URL: {similar_url}")
            
            logging.info(f"原始相似页面URL: {original_url}")
            logging.info(f"处理后的相似页面URL: {similar_url}")
            logging.info(f"发现相似页面 '{similar_name}'，导航到: {similar_url}")
           
            html_text = get_html(similar_url)
            html_text = parse_html(html_text)
            # 提取相似页面的教师信息
            extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
            similar_teachers = extract_result["teachers"]
            for teacher in similar_teachers:
                teacher["URL"] = urljoin(similar_url, teacher["URL"])
            all_teachers.extend(similar_teachers)
            logging.info(f"相似页面 '{similar_name}' (page {page_count}): 提取到 {len(similar_teachers)} 位教师")
            
            # 对于相似页面，也检查是否有翻页
            while True:
                next_page_result = check_next_page(DEEPSEEK_API_KEY, html_text)
                if not next_page_result["has_next"] or not next_page_result["next_url"]:
                    break
                next_url = next_page_result["next_url"]
                if not next_url.startswith("http"):
                    next_url = urljoin(similar_url, next_url)
                if next_url in all_url_list:
                    logging.info(f"发现重复URL in 相似页面: {next_url}，停止翻页")
                    break
                all_url_list.append(next_url)
                
                logging.info(f"相似页面 '{similar_name}' 发现下一页，导航到: {next_url}")
                page_count += 1
                
                html_text = get_html(next_url)
                html_text = parse_html(html_text)
                extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
                current_page_teachers = extract_result["teachers"]
                for teacher in current_page_teachers:
                    teacher["URL"] = urljoin(next_url, teacher["URL"])
                all_teachers.extend(current_page_teachers)
                logging.info(f"相似页面 '{similar_name}' 第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")
    # all_teachers去重 假设用 'name' 字段作为唯一标识
    # 先strip()姓名字段，再去重
    t = []
    for teacher in all_teachers:
        teacher["name"] = teacher["name"].replace(' ','')
        temp = teacher
        t.append(temp)
    all_teachers = t
    
    seen = set()
    unique_teachers = []
    for teacher in all_teachers:
        identifier = teacher.get('name')  # 或其他唯一字段
        if identifier not in seen:
            seen.add(identifier)
            unique_teachers.append(teacher)
    all_teachers = unique_teachers
    logging.info(f"-----------共提取到 {len(all_teachers)} 位教师-----------")
    
    # Check if teachers list is empty and log to exceptions
    if len(all_teachers) == 0:
        exceptions_logger.info(f"Empty teacher folder: {teacher_folder} for university {university_name} college {college_name} URL {college_url}")
    
    teacher_folder = output_dir / college_name
    os.makedirs(teacher_folder, exist_ok=True)

    teachers_file = teacher_folder / f"{college_name}_teachers.json"
    with open(teachers_file, 'w', encoding='utf-8') as f:
        json.dump(all_teachers, f, ensure_ascii=False, indent=4)
    print(f"已保存 {college_name} 的教师列表到 {teachers_file}")
    return []



def parse_schools_data(filename):
    schools = {}
    
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
                
            # 分割学校部分和学院部分
            parts = line.split('\\')
            
            # 提取学校名称（去掉前面的编号_）
            school_part = parts[0]
            if '_' in school_part:
                school_name = school_part.split('_', 1)[1]
            else:
                school_name = school_part
                
            # 如果学校不在字典中，初始化一个空列表
            if school_name not in schools:
                schools[school_name] = []
            
            # 如果有学院信息，提取学院名称
            if len(parts) > 1:
                college_part = parts[1]
                # 去掉学院名称中的文件后缀
                if college_part.endswith('_teachers.json'):
                    college_name = college_part.rsplit('_teachers.json', 1)[0]
                else:
                    college_name = college_part
                
                # 如果学院不在该学校的列表中，则添加
                if college_name not in schools[school_name]:
                    schools[school_name].append(college_name)
    
    return schools


if __name__ == "__main__":
    filename = "empty_items2.txt"
    result = parse_schools_data(filename)

    # Load school websites
    chinese_schools_path = PROJECT_ROOT / "chinese_schools.json"
    with open(chinese_schools_path, 'r', encoding='utf-8') as f:
        schools_data = json.load(f)
    school_urls = {school['name']: school['website'] for school in schools_data}

    input_dir = PROJECT_ROOT / "data" / "output_chinese"
    output_base = PROJECT_ROOT / "data" / "schoolTeachers"

    for school in schools_data:
        university_name = school['name']
        if university_name != "北京大学":
            continue
        school_website = school['website']
        rank = school['rank']
        error_colleges = []
        err_len = 0
        if university_name in result:
            error_colleges = result[university_name]
            err_len = len(error_colleges)
            print(f"需要处理 {university_name}: {error_colleges}")
        else:
            error_colleges = []
        if err_len == 0:
            continue
        matching_files = list(input_dir.glob(f"*_{university_name}_schools_result.json"))
        if not matching_files:
            print(f"Skipping {university_name}: no JSON file found in output_chinese")
            continue
        if len(matching_files) > 1:
            print(f"Warning: Multiple JSON files found for {university_name}, using the first one")
        json_path = matching_files[0]
        print(f"Processing university: {university_name} using {json_path}\n")

        with open(json_path, 'r', encoding='utf-8') as f:
            colleges = json.load(f)

        output_dir = output_base / f"{rank}_{university_name}"
        os.makedirs(output_dir, exist_ok=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=err_len) as executor:
            futures = []
            for college in colleges:
                college_name = college["name"]
                college_url = college["URL"]
                if not college_name in error_colleges:
                    continue
                if college_url is None:
                    continue
                # if college_name != "信息与电子工程学院":
                #     continue
                # if not college_url.startswith("http"):
                #     college_url = urljoin(school_website, college_url)
                future = executor.submit(process_college_teachers, university_name, college_name, college_url, output_dir)
                futures.append((college_name, future))

            for college_name, future in futures:
                try:
                    future.result()  # 等待任务完成，但不处理返回结果，因为保存已在函数内部完成
                    print(f"已处理 {college_name}\n")
                except Exception as e:
                    print(f"处理 {college_name} 失败: {e}\n")
