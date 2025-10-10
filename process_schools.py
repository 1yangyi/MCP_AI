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

def extract_teacher_button(api_key: str, text: str) -> dict:
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception as e:
        return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
    prompt = f"""
    你是一个数据收集助手，协助收集高校学院的教师信息。
    现在你需要根据以下页面网页结构化列表，判断哪一个最可能引导至包含所有教师信息的页面，并直接返回该按钮的文本和对应URL。
    链接列表：
    {text}
    请严格按以下格式输出一个最可能的按钮文本，不要任何额外解释：
    按钮文本@URL,例如，"师资力量@teachers.htm"
    注意：优先选择类似“教师队伍”、“师资力量”、“Faculty”、“Professors”、“按字母排序”、“按专业分类”等明确指向教师列表的链接。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    content = completion.choices[0].message.content
    parts = content.split('@', 1)
    return {"status": "success", "button_text": parts[0], "url": parts[1] if len(parts) > 1 else ""}


def check_next_page(api_key: str, text: str) -> dict:
    """检查是否存在下一页按钮及其URL"""
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    prompt = f"""
    你是一个数据分析助手，请从以下网页内容中识别是否存在"下一页"、"next page"、">"等表示翻页的按钮或链接。
    网页内容如下：
    {text}
    如果存在下一页按钮或链接，请提取其URL，并以JSON格式返回：{{"has_next": true, "next_url": "链接URL"}}
    如果不存在下一页按钮或链接，请返回：{{"has_next": false, "next_url": ""}}
    如果下一页按钮或链接存在，但URL为空，请返回：{{"has_next": true, "next_url": ""}}
    注意：仅输出JSON格式结果，不要附加解释。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    content = completion.choices[0].message.content
    # 清理 content
    content = re.sub(r'^```json\s*|\s*```$', '', content).strip()
    try:
        result = json.loads(content)
        return {"status": "success", "has_next": result.get("has_next", False), "next_url": result.get("next_url", "")}
    except json.JSONDecodeError:
        return {"status": "error", "has_next": False, "next_url": ""}


def check_similar_page(api_key: str, text: str, button_url: str) -> dict:
    """检查是否存在与当前页面相似的页面"""
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
    # 简化提示词，更明确地指出要查找的内容
    prompt = f"""
    你是一个数据分析助手，请从以下JSON格式的网页内容中找出与"师资队伍"相关的其他按钮或链接。
    特别关注这些关键词："杰出人才"、"特聘教师"、"博士后"、"教授"等。
    
    当前页面URL为：{button_url}
    
    网页内容如下：
    {text}
    
    请提取所有可能包含教师信息的按钮，并以JSON数组格式返回：
    [
      {{"name": "按钮名称1", "url": "链接URL1"}},
      {{"name": "按钮名称2", "url": "链接URL2"}}
    ]
    
    如果没有找到相关按钮，请返回空数组 []
    """
    
    try:
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5  
            # do not know why here 0.5 is optimal?
        )
        
        content = completion.choices[0].message.content
        print(f"API原始返回: {content}")  
        
        # 尝试清理内容并解析JSON
        content = re.sub(r'^```json\s*|\s*```$', '', content).strip()
        try:
            result = json.loads(content)
            return {"status": "success", "has_next": len(result) > 0, "next_urls": result}
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            # 尝试更宽松的解析方式
            pattern = r'"name"\s*:\s*"([^"]+)"\s*,\s*"url"\s*:\s*"([^"]+)"'
            matches = re.findall(pattern, content)
            if matches:
                result = [{"name": name, "url": url} for name, url in matches]
                return {"status": "success", "has_next": len(result) > 0, "next_urls": result}
            return {"status": "error", "has_next": False, "next_urls": [], "raw_content": content}
    except Exception as e:
        print(f"API调用错误: {e}")
        return {"status": "error", "has_next": False, "next_urls": [], "error": str(e)}


def decide_if_teacher_list(api_key: str, text: str) -> dict:
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception as e:
        return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
    prompt = f"""
    你是一个数据收集助手，用于识别网页内容是否包含某学院的全部教师名称及对应信息。
    请根据以下结构化内容进行判断：
    {text}
    若当前列表包含该学院教师的名称和URL，则返回：True
    若列表中没有教师信息，则返回：False
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
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception as e:
        return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
    prompt = f"""
    你是一个数据收集助手，协助收集学院的教师信息。
    请从以下网页结构化列表中识别出其中所有教师的名称和URL。注意：名称只包含教师的姓名，不能包含任何分类标签（如“院长”、“研究员”、“院士”等）。
    列表内容如下：
    {text}
    请以json格式直接返回该学院所有教师(包括教师、研究员、工程师等，如果是 医学学院则还包括 医生专家等)的信息。
    注意：仅输出结果的json格式，不要附加解释。每个教师的格式为：{{"name": "", "URL": ""}}。
    如果未识别出教师信息，则返回空列表。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
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

def process_college_teachers(college_name: str, college_url: str, output_dir: Path):
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
    button_url = ""
    is_teacher_list = "False"
    while is_teacher_list != "True" and count < 2:
        count += 1
        result_link = extract_teacher_button(DEEPSEEK_API_KEY, html_text)
        if result_link["status"] != "success":
            print(f"未找到教师按钮: {result_link['message']}")
            continue
        button_text = result_link["button_text"]
        click_url = result_link["url"]
        button_url = click_url
        print(f"点击按钮文本: {button_text}, URL: {click_url}")

        print(f"当前URL: {current_url}")
        print(f"点击URL: {click_url}")
        click_url = urljoin(current_url, click_url)
        print(f"合并后的URL: {click_url}")
        print('-----------------')

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
        print(f"是否为教师列表: {is_teacher_list}")

    print("正在提取教师信息...")
    all_teachers = []
    page_count = 1
    extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
    first_html_text = html_text
    first_html_url = current_url
    current_page_teachers = extract_result["teachers"]
    all_teachers.extend(current_page_teachers)
    for teacher in current_page_teachers:
        teacher["URL"] = urljoin(current_url, teacher["URL"])
    print(f"第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")


    # 检查是否有下一页
    all_url_list = []
    while True:
        next_page_result = check_next_page(DEEPSEEK_API_KEY, html_text)
        if not next_page_result["has_next"] or not next_page_result["next_url"]:
            print("没有更多页面，教师信息提取完成")
            break
        # 获取下一页URL
        next_url = next_page_result["next_url"]
        if not next_url.startswith("http"):
            next_url = urljoin(current_url, next_url)
        
        if next_url.startswith('http://'):
            next_url = 'https://' + next_url[7:]
        if next_url in all_url_list:
            print(f"发现重复URL: {next_url}，停止翻页")
            break
        all_url_list.append(next_url)
        
        print(f"发现下一页，导航到: {next_url}")
        page_count += 1
        
        # 导航到下一页
        navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": next_url, "wait_time": 3})
        if navigate_response.status_code != 200:
            print(f"导航到下一页失败: {next_url}")
            break
        
        current_url = next_url  # 更新当前URL
        
        # 解析下一页HTML
        next_page_parse_response = requests.post(
            f"{HTML_PARSER_URL}/parse", 
            json={"url": next_url, "output_prefix": f"{college_name}_teachers_page{page_count}", "output_dir": str(MIDDLE_FILE_DIR)}
        )
        
        if next_page_parse_response.status_code != 200:
            print(f"解析下一页HTML失败: {next_url}")
            break
            
        try:
            html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}_teachers_page{page_count}.json")
            html_text = _safe_json_dumps(html_obj)
        except FileNotFoundError:
            print(f"下一页HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}_teachers_page{page_count}.json")
            break
            
        # 提取下一页的教师信息
        extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
        current_page_teachers = extract_result["teachers"]
        for teacher in current_page_teachers:
            teacher["URL"] = urljoin(current_url, teacher["URL"])
        if len(current_page_teachers) == 0:
            print(f"第 {page_count} 页: 没有提取到教师信息，停止翻页")
            break
        all_teachers.extend(current_page_teachers)
        print(f"第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")
    
    print(f"总共提取到 {len(all_teachers)} 位教师信息")

    # 检查是否有相似页面
    print("\n开始检查相似页面...")
    print(f"当前按钮或链接的URL为：{button_url}")
    similar_page_result = check_similar_page(DEEPSEEK_API_KEY, first_html_text,button_url)
    print(f"检查相似页面结果: {similar_page_result}")
    
    # part to modify:
    if similar_page_result.get("status") == "success" and similar_page_result["has_next"]:
        for similar in similar_page_result["next_urls"]:
            similar_url = similar["url"]
            similar_name = similar["name"]
            original_url = similar_url  # 保存原始URL用于调试

            # 标准化URL路径
            if not similar_url.startswith("http"):
                similar_url = urljoin(first_html_url, similar_url)
            
            if similar_url.startswith('http://'):
                similar_url = 'https://' + similar_url[7:]
            
            print(f"原始相似页面URL: {original_url}")
            print(f"处理后的相似页面URL: {similar_url}")
            print(f"发现相似页面 '{similar_name}'，导航到: {similar_url}")
            # 导航到相似页面
            navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": similar_url, "wait_time": 3})
            if navigate_response.status_code != 200:
                print(f"导航到相似页面失败: {similar_url}")
                continue
            # 解析相似页面HTML
            page_count += 1
            parse_response = requests.post(
                f"{HTML_PARSER_URL}/parse", 
                json={"url": similar_url, "output_prefix": f"{college_name}_similar_teachers_page{page_count}", "output_dir": str(MIDDLE_FILE_DIR)}
            )
            if parse_response.status_code != 200:
                print(f"解析相似页面HTML失败: {similar_url}")
                continue
            try:
                html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
                html_text = _safe_json_dumps(html_obj)
            except FileNotFoundError:
                print(f"相似页面HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
                continue
            
            # 提取相似页面的教师信息
            extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
            similar_teachers = extract_result["teachers"]
            for teacher in similar_teachers:
                teacher["URL"] = urljoin(similar_url, teacher["URL"])
            all_teachers.extend(similar_teachers)
            print(f"相似页面 '{similar_name}' (page {page_count}): 提取到 {len(similar_teachers)} 位教师")
            
            # 对于相似页面，也检查是否有翻页
            while True:
                next_page_result = check_next_page(DEEPSEEK_API_KEY, html_text)
                if not next_page_result["has_next"] or not next_page_result["next_url"]:
                    break
                next_url = next_page_result["next_url"]
                if not next_url.startswith("http"):
                    next_url = urljoin(similar_url, next_url)
                if next_url.startswith('http://'):
                    next_url = 'https://' + next_url[7:]
                if next_url in all_url_list:
                    print(f"发现重复URL in 相似页面: {next_url}，停止翻页")
                    break
                all_url_list.append(next_url)
                
                print(f"相似页面 '{similar_name}' 发现下一页，导航到: {next_url}")
                page_count += 1
                
                navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": next_url, "wait_time": 3})
                if navigate_response.status_code != 200:
                    print(f"导航到相似页面下一页失败: {next_url}")
                    break
                
                parse_response = requests.post(
                    f"{HTML_PARSER_URL}/parse", 
                    json={"url": next_url, "output_prefix": f"{college_name}_similar_teachers_page{page_count}", "output_dir": str(MIDDLE_FILE_DIR)}
                )
                if parse_response.status_code != 200:
                    print(f"解析相似页面下一页HTML失败: {next_url}")
                    break
                
                try:
                    html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
                    html_text = _safe_json_dumps(html_obj)
                except FileNotFoundError:
                    print(f"相似页面下一页HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
                    break
                    
                extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
                current_page_teachers = extract_result["teachers"]
                for teacher in current_page_teachers:
                    teacher["URL"] = urljoin(next_url, teacher["URL"])
                if len(current_page_teachers) == 0:
                    print(f"相似页面 '{similar_name}' 第 {page_count} 页: 没有提取到教师信息，停止翻页")
                    break
                all_teachers.extend(current_page_teachers)
                print(f"相似页面 '{similar_name}' 第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")
    # all_teachers去重 假设用 'name' 字段作为唯一标识
    seen = set()
    unique_teachers = []
    for teacher in all_teachers:
        identifier = teacher.get('name')  # 或其他唯一字段
        if identifier not in seen:
            seen.add(identifier)
            unique_teachers.append(teacher)
    all_teachers = unique_teachers
    print(f"-----------共提取到 {len(all_teachers)} 位教师-----------")
    teacher_folder = output_dir / college_name
    os.makedirs(teacher_folder, exist_ok=True)

    print("\n开始加载教师页面...")
    for teacher in all_teachers:
        teacher_name = teacher["name"]
        teacher_url = teacher["URL"]
        if not teacher_url or not teacher_name:
            continue

        print(f"处理教师: {teacher_name} ({teacher_url})")
        navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": teacher_url, "wait_time": 2})
        if navigate_response.status_code != 200:
            print(f"导航到教师页面失败: {teacher_url} for {college_name}")
            continue

        current_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
        if current_page_response.status_code != 200:
            print(f"获取教师页面HTML失败: {teacher_url} in {college_name}")
            continue
        print(f"教师页面HTML获取成功: {teacher_url} in {college_name}")
        current_page_data = current_page_response.json()
        html_content = current_page_data['html']

        print(f"创建{teacher_name}老师信息json文件...")
        teacher_file = teacher_folder / f"{teacher_name}.html"
        try:
            with open(teacher_file, 'w', encoding='utf-8') as file:
                file.write(html_content)
            print(f"保存教师 {teacher_name} 的HTML到 {teacher_file}...成功")
        except Exception as e:
            print(f"保存教师 {teacher_name} 的HTML到 {teacher_file} 失败: {e}")
            continue
        print('---------------------------------------------------')
    return all_teachers


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
        # if university_name != '清华大学':
        #     continue
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

        output_dir = output_base / university_name
        os.makedirs(output_dir, exist_ok=True)

        for college in colleges:
            college_name = college["name"]
            # if college_name != '电机工程与应用电子技术系':
            #     continue
            college_url = college["URL"]
            if not college_url.startswith("http"):
                college_url = urljoin(school_website, college_url)
            teachers = process_college_teachers(college_name, college_url, output_dir)
            file_path = output_dir / f"{college_name}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(teachers, f, ensure_ascii=False, indent=4)
            print(f"Saved {college_name} teachers to {file_path}\n")


# import concurrent.futures
# from tqdm import tqdm
# import requests
# import json
# import os
# import re
# from datetime import datetime
# from pathlib import Path
# from src.mcp_servers.ai import read_json_file, _safe_json_dumps, decide_click_or_extrect
# from src.config import BROWSER_MCP_URL, HTML_PARSER_URL, PROJECT_ROOT
# from openai import OpenAI
# from urllib.parse import urljoin
# import glob

# # 中间文件目录
# MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file2"
# MIDDLE_FILE_DIR.mkdir(exist_ok=True)

# DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"

# def multi_process_exec_v0(f, args_mat, pool_size=5, desc=None):
#     if len(args_mat)==0:return []
#     results=[None for _ in range(len(args_mat))]
#     with tqdm(total=len(args_mat), desc=desc) as pbar:
#         with concurrent.futures.ProcessPoolExecutor(max_workers=pool_size) as executor:
#             futures = {executor.submit(f,*args): i for i,args in enumerate(args_mat)}
#             for future in concurrent.futures.as_completed(futures):
#                 i=futures[future]
#                 ret = future.result()
#                 results[i]=ret
#                 pbar.update(1)
#     return results

# def extract_teacher_button(api_key: str, text: str) -> dict:
#     try:
#         client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
#     except Exception as e:
#         return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
#     prompt = f"""
#     你是一个数据收集助手，协助收集高校学院的教师信息。
#     现在你需要根据以下页面网页结构化列表，判断哪一个最可能引导至包含所有教师信息的页面，并直接返回该按钮的文本和对应URL。
#     链接列表：
#     {text}
#     请严格按以下格式输出一个最可能的按钮文本，不要任何额外解释：
#     按钮文本@URL,例如，"师资力量@teachers.htm"
#     注意：优先选择类似"教师队伍"、"师资力量"、"Faculty"、"Professors"、"按字母排序"、"按专业分类"等明确指向教师列表的链接。
#     """
#     completion = client.chat.completions.create(
#         model="deepseek-chat",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.0
#     )
#     content = completion.choices[0].message.content
#     parts = content.split('@', 1)
#     return {"status": "success", "button_text": parts[0], "url": parts[1] if len(parts) > 1 else ""}

# def check_next_page(api_key: str, text: str) -> dict:
#     """检查是否存在下一页按钮及其URL"""
#     client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
#     prompt = f"""
#     你是一个数据分析助手，请从以下网页内容中识别是否存在"下一页"、"next page"、">"等表示翻页的按钮或链接。
#     网页内容如下：
#     {text}
#     如果存在下一页按钮或链接，请提取其URL，并以JSON格式返回：{{"has_next": true, "next_url": "链接URL"}}
#     如果不存在下一页按钮或链接，请返回：{{"has_next": false, "next_url": ""}}
#     如果下一页按钮或链接存在，但URL为空，请返回：{{"has_next": true, "next_url": ""}}
#     注意：仅输出JSON格式结果，不要附加解释。
#     """
#     completion = client.chat.completions.create(
#         model="deepseek-chat",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.1
#     )
#     content = completion.choices[0].message.content
#     # 清理 content
#     content = re.sub(r'^```json\s*|\s*```$', '', content).strip()
#     try:
#         result = json.loads(content)
#         return {"status": "success", "has_next": result.get("has_next", False), "next_url": result.get("next_url", "")}
#     except json.JSONDecodeError:
#         return {"status": "error", "has_next": False, "next_url": ""}

# def check_similar_page(api_key: str, text: str, button_url: str) -> dict:
#     """检查是否存在与当前页面相似的页面"""
#     client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    
#     # 简化提示词，更明确地指出要查找的内容
#     prompt = f"""
#     你是一个数据分析助手，请从以下JSON格式的网页内容中找出与"师资队伍"相关的其他按钮或链接。
#     特别关注这些关键词："杰出人才"、"特聘教师"、"博士后"、"教授"等。
    
#     当前页面URL为：{button_url}
    
#     网页内容如下：
#     {text}
    
#     请提取所有可能包含教师信息的按钮，并以JSON数组格式返回：
#     [
#       {{"name": "按钮名称1", "url": "链接URL1"}},
#       {{"name": "按钮名称2", "url": "链接URL2"}}
#     ]
    
#     如果没有找到相关按钮，请返回空数组 []
#     """
    
#     try:
#         completion = client.chat.completions.create(
#             model="deepseek-chat",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.5  
#             # do not know why here 0.5 is optimal?
#         )
        
#         content = completion.choices[0].message.content
#         print(f"API原始返回: {content}")  
        
#         # 尝试清理内容并解析JSON
#         content = re.sub(r'^```json\s*|\s*```$', '', content).strip()
#         try:
#             result = json.loads(content)
#             return {"status": "success", "has_next": len(result) > 0, "next_urls": result}
#         except json.JSONDecodeError as e:
#             print(f"JSON解析错误: {e}")
#             # 尝试更宽松的解析方式
#             pattern = r'"name"\s*:\s*"([^"]+)"\s*,\s*"url"\s*:\s*"([^"]+)"'
#             matches = re.findall(pattern, content)
#             if matches:
#                 result = [{"name": name, "url": url} for name, url in matches]
#                 return {"status": "success", "has_next": len(result) > 0, "next_urls": result}
#             return {"status": "error", "has_next": False, "next_urls": [], "raw_content": content}
#     except Exception as e:
#         print(f"API调用错误: {e}")
#         return {"status": "error", "has_next": False, "next_urls": [], "error": str(e)}

# def decide_if_teacher_list(api_key: str, text: str) -> dict:
#     try:
#         client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
#     except Exception as e:
#         return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
#     prompt = f"""
#     你是一个数据收集助手，用于识别网页内容是否包含某学院的全部教师名称及对应信息。
#     请根据以下结构化内容进行判断：
#     {text}
#     若当前列表包含该学院教师的名称和URL，则返回：True
#     若列表中没有教师信息，则返回：False
#     注意：仅输出结果文本（True 或 False），无需任何解释。
#     """
#     completion = client.chat.completions.create(
#         model="deepseek-chat",
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.0
#     )
#     content = completion.choices[0].message.content.strip()
#     return {"status": "success", "message": content}

# def extract_teachers_with_deepseek(api_key: str, text: str) -> dict:
#     try:
#         client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
#     except Exception as e:
#         return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
#     prompt = f"""
#     你是一个数据收集助手，协助收集学院的教师信息。
#     请从以下网页结构化列表中识别出其中所有教师的名称和URL。注意：名称只包含教师的姓名，不能包含任何分类标签（如"院长"、"研究员"、"院士"等）。
#     列表内容如下：
#     {text}
#     请以json格式直接返回该学院所有教师(包括教师、研究员、工程师等，如果是 医学学院则还包括 医生专家等)的信息。
#     注意：仅输出结果的json格式，不要附加解释。每个教师的格式为：{{"name": "", "URL": ""}}。
#     如果未识别出教师信息，则返回空列表。
#     """
#     completion = client.chat.completions.create(
#         model="deepseek-chat",
#         messages=[{"role": "user", "content": prompt}],
#         max_tokens=8000,
#         temperature=1.0
#     )
#     content = completion.choices[0].message.content
#     # 清理 content
#     content = re.sub(r'^```json\s*|\s*```$', '', content).strip()
#     try:
#         teachers = json.loads(content)
#     except json.JSONDecodeError:
#         teachers = []
#     return {"status": "success", "teachers": teachers}

# def process_college_teachers(college_name: str, college_url: str, output_dir: Path):
#     if not college_url.endswith("/"):
#         college_url = college_url + "/"
#     print(f"处理学院教师信息: {college_name} ({college_url})")
#     current_url = college_url.replace("http://", "https://") if college_url.startswith("http://") else college_url
#     # 导航到学院URL
#     print(f"导航到学院URL: {current_url}")
#     navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": current_url, "wait_time": 2})
#     if navigate_response.status_code != 200:
#         print(f"导航到学院URL失败: {college_url}")
#         return []

#     # 获取HTML并解析
#     parse_response = requests.post(f"{HTML_PARSER_URL}/parse", json={"url": college_url, "output_prefix": college_name, "output_dir": str(MIDDLE_FILE_DIR)})
#     if parse_response.status_code != 200:
#         print(f"解析学院HTML失败: {college_url}")
#         return []

#     try:
#         # 读取解析的JSON
#         html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}.json")
#         html_text = _safe_json_dumps(html_obj)
#     except FileNotFoundError:
#         print(f"学院HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}.json")
#         return []

#     count = 0
#     button_url = ""
#     is_teacher_list = "False"
#     while is_teacher_list != "True" and count < 2:
#         count += 1
#         result_link = extract_teacher_button(DEEPSEEK_API_KEY, html_text)
#         if result_link["status"] != "success":
#             print(f"未找到教师按钮: {result_link['message']}")
#             continue
#         button_text = result_link["button_text"]
#         click_url = result_link["url"]
#         button_url = click_url
#         print(f"点击按钮文本: {button_text}, URL: {click_url}")

#         print(f"当前URL: {current_url}")
#         print(f"点击URL: {click_url}")
#         click_url = urljoin(current_url, click_url)
#         print(f"合并后的URL: {click_url}")
#         print('-----------------')

#         if click_url.startswith('http://'):
#             click_url = 'https://' + click_url[7:]
#         # 导航到教师页面
#         print(f"导航到教师页面: {click_url}")
#         requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": click_url, "wait_time": 3})
#         current_url = click_url  # 更新当前 URL

#         # 解析新页面HTML
#         print(f"解析教师页面HTML: {click_url}")
#         new_parse_response = requests.post(f"{HTML_PARSER_URL}/parse", json={"url": click_url, "output_prefix": f"{college_name}_teachers", "output_dir": str(MIDDLE_FILE_DIR)})
#         if new_parse_response.status_code != 200:
#             print(f"解析教师页面HTML失败: {click_url}")
#             continue

#         try:
#             html_obj = read_json_file(f"{MIDDLE_FILE_DIR}\{college_name}_teachers.json")
#             html_text = _safe_json_dumps(html_obj)
#         except FileNotFoundError:
#             print(f"教师页面HTML文件不存在: {MIDDLE_FILE_DIR}\{college_name}_teachers.json")
#             continue

#         # 检查是否为教师列表
#         decide_result = decide_if_teacher_list(DEEPSEEK_API_KEY, html_text)
#         is_teacher_list = decide_result["message"]
#         print(f"是否为教师列表: {is_teacher_list}")

#     print("正在提取教师信息...")
#     all_teachers = []
#     page_count = 1
#     extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
#     first_html_text = html_text
#     first_html_url = current_url
#     current_page_teachers = extract_result["teachers"]
#     all_teachers.extend(current_page_teachers)
#     for teacher in current_page_teachers:
#         teacher["URL"] = urljoin(current_url, teacher["URL"])
#     print(f"第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")


#     # 检查是否有下一页
#     all_url_list = []
#     while True:
#         next_page_result = check_next_page(DEEPSEEK_API_KEY, html_text)
#         if not next_page_result["has_next"] or not next_page_result["next_url"]:
#             print("没有更多页面，教师信息提取完成")
#             break
#         # 获取下一页URL
#         next_url = next_page_result["next_url"]
#         if not next_url.startswith("http"):
#             next_url = urljoin(current_url, next_url)
        
#         if next_url.startswith('http://'):
#             next_url = 'https://' + next_url[7:]
#         if next_url in all_url_list:
#             print(f"发现重复URL: {next_url}，停止翻页")
#             break
#         all_url_list.append(next_url)
        
#         print(f"发现下一页，导航到: {next_url}")
#         page_count += 1
        
#         # 导航到下一页
#         navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": next_url, "wait_time": 3})
#         if navigate_response.status_code != 200:
#             print(f"导航到下一页失败: {next_url}")
#             break
        
#         current_url = next_url  # 更新当前URL
        
#         # 解析下一页HTML
#         next_page_parse_response = requests.post(
#             f"{HTML_PARSER_URL}/parse", 
#             json={"url": next_url, "output_prefix": f"{college_name}_teachers_page{page_count}", "output_dir": str(MIDDLE_FILE_DIR)}
#         )
        
#         if next_page_parse_response.status_code != 200:
#             print(f"解析下一页HTML失败: {next_url}")
#             break
            
#         try:
#             html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}_teachers_page{page_count}.json")
#             html_text = _safe_json_dumps(html_obj)
#         except FileNotFoundError:
#             print(f"下一页HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}_teachers_page{page_count}.json")
#             break
            
#         # 提取下一页的教师信息
#         extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
#         current_page_teachers = extract_result["teachers"]
#         for teacher in current_page_teachers:
#             teacher["URL"] = urljoin(current_url, teacher["URL"])
#         if len(current_page_teachers) == 0:
#             print(f"第 {page_count} 页: 没有提取到教师信息，停止翻页")
#             break
#         all_teachers.extend(current_page_teachers)
#         print(f"第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")
    
#     print(f"总共提取到 {len(all_teachers)} 位教师信息")

#     # 检查是否有相似页面
#     print("\n开始检查相似页面...")
#     print(f"当前按钮或链接的URL为：{button_url}")
#     similar_page_result = check_similar_page(DEEPSEEK_API_KEY, first_html_text,button_url)
#     print(f"检查相似页面结果: {similar_page_result}")
    
#     # part to modify:
#     if similar_page_result.get("status") == "success" and similar_page_result["has_next"]:
#         for similar in similar_page_result["next_urls"]:
#             similar_url = similar["url"]
#             similar_name = similar["name"]
#             original_url = similar_url  # 保存原始URL用于调试

#             # 标准化URL路径
#             if not similar_url.startswith("http"):
#                 similar_url = urljoin(first_html_url, similar_url)
            
#             if similar_url.startswith('http://'):
#                 similar_url = 'https://' + similar_url[7:]
            
#             print(f"原始相似页面URL: {original_url}")
#             print(f"处理后的相似页面URL: {similar_url}")
#             print(f"发现相似页面 '{similar_name}'，导航到: {similar_url}")
#             # 导航到相似页面
#             navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": similar_url, "wait_time": 3})
#             if navigate_response.status_code != 200:
#                 print(f"导航到相似页面失败: {similar_url}")
#                 continue
#             # 解析相似页面HTML
#             page_count += 1
#             parse_response = requests.post(
#                 f"{HTML_PARSER_URL}/parse", 
#                 json={"url": similar_url, "output_prefix": f"{college_name}_similar_teachers_page{page_count}", "output_dir": str(MIDDLE_FILE_DIR)}
#             )
#             if parse_response.status_code != 200:
#                 print(f"解析相似页面HTML失败: {similar_url}")
#                 continue
#             try:
#                 html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
#                 html_text = _safe_json_dumps(html_obj)
#             except FileNotFoundError:
#                 print(f"相似页面HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
#                 continue
            
#             # 提取相似页面的教师信息
#             extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
#             similar_teachers = extract_result["teachers"]
#             for teacher in similar_teachers:
#                 teacher["URL"] = urljoin(similar_url, teacher["URL"])
#             all_teachers.extend(similar_teachers)
#             print(f"相似页面 '{similar_name}' (page {page_count}): 提取到 {len(similar_teachers)} 位教师")
            
#             # 对于相似页面，也检查是否有翻页
#             while True:
#                 next_page_result = check_next_page(DEEPSEEK_API_KEY, html_text)
#                 if not next_page_result["has_next"] or not next_page_result["next_url"]:
#                     break
#                 next_url = next_page_result["next_url"]
#                 if not next_url.startswith("http"):
#                     next_url = urljoin(similar_url, next_url)
#                 if next_url.startswith('http://'):
#                     next_url = 'https://' + next_url[7:]
#                 if next_url in all_url_list:
#                     print(f"发现重复URL in 相似页面: {next_url}，停止翻页")
#                     break
#                 all_url_list.append(next_url)
                
#                 print(f"相似页面 '{similar_name}' 发现下一页，导航到: {next_url}")
#                 page_count += 1
                
#                 navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": next_url, "wait_time": 3})
#                 if navigate_response.status_code != 200:
#                     print(f"导航到相似页面下一页失败: {next_url}")
#                     break
                
#                 parse_response = requests.post(
#                     f"{HTML_PARSER_URL}/parse", 
#                     json={"url": next_url, "output_prefix": f"{college_name}_similar_teachers_page{page_count}", "output_dir": str(MIDDLE_FILE_DIR)}
#                 )
#                 if parse_response.status_code != 200:
#                     print(f"解析相似页面下一页HTML失败: {next_url}")
#                     break
                
#                 try:
#                     html_obj = read_json_file(f"{MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
#                     html_text = _safe_json_dumps(html_obj)
#                 except FileNotFoundError:
#                     print(f"相似页面下一页HTML文件不存在: {MIDDLE_FILE_DIR}/{college_name}_similar_teachers_page{page_count}.json")
#                     break
                    
#                 extract_result = extract_teachers_with_deepseek(DEEPSEEK_API_KEY, html_text)
#                 current_page_teachers = extract_result["teachers"]
#                 for teacher in current_page_teachers:
#                     teacher["URL"] = urljoin(next_url, teacher["URL"])
#                 if len(current_page_teachers) == 0:
#                     print(f"相似页面 '{similar_name}' 第 {page_count} 页: 没有提取到教师信息，停止翻页")
#                     break
#                 all_teachers.extend(current_page_teachers)
#                 print(f"相似页面 '{similar_name}' 第 {page_count} 页: 提取到 {len(current_page_teachers)} 位教师")
#     # all_teachers去重 假设用 'name' 字段作为唯一标识
#     seen = set()
#     unique_teachers = []
#     for teacher in all_teachers:
#         identifier = teacher.get('name')  # 或其他唯一字段
#         if identifier not in seen:
#             seen.add(identifier)
#             unique_teachers.append(teacher)
#     all_teachers = unique_teachers
#     print(f"-----------共提取到 {len(all_teachers)} 位教师-----------")
#     teacher_folder = output_dir / college_name
#     os.makedirs(teacher_folder, exist_ok=True)

#     print("\n开始加载教师页面...")
#     for teacher in all_teachers:
#         teacher_name = teacher["name"]
#         teacher_url = teacher["URL"]
#         if not teacher_url or not teacher_name:
#             continue

#         print(f"处理教师: {teacher_name} ({teacher_url})")
#         navigate_response = requests.post(f"{BROWSER_MCP_URL}/navigate", json={"url": teacher_url, "wait_time": 2})
#         if navigate_response.status_code != 200:
#             print(f"导航到教师页面失败: {teacher_url} for {college_name}")
#             continue

#         current_page_response = requests.get(f"{BROWSER_MCP_URL}/current_page")
#         if current_page_response.status_code != 200:
#             print(f"获取教师页面HTML失败: {teacher_url} in {college_name}")
#             continue
#         print(f"教师页面HTML获取成功: {teacher_url} in {college_name}")
#         current_page_data = current_page_response.json()
#         html_content = current_page_data['html']

#         print(f"创建{teacher_name}老师信息json文件...")
#         teacher_file = teacher_folder / f"{teacher_name}.html"
#         try:
#             with open(teacher_file, 'w', encoding='utf-8') as file:
#                 file.write(html_content)
#             print(f"保存教师 {teacher_name} 的HTML到 {teacher_file}...成功")
#         except Exception as e:
#             print(f"保存教师 {teacher_name} 的HTML到 {teacher_file} 失败: {e}")
#             continue
#         print('---------------------------------------------------')
#     return all_teachers

# def process_single_school_batch(schools_batch):
#     """
#     处理单个学校批次的函数
#     """
#     results = []
#     for school in schools_batch:
#         university_name = school['name']
#         school_website = school['website']
        
#         input_dir = PROJECT_ROOT / "data" / "output_chinese"
#         matching_files = list(input_dir.glob(f"*_{university_name}_schools_result.json"))
#         if not matching_files:
#             print(f"Skipping {university_name}: no JSON file found in output_chinese")
#             results.append({"university": university_name, "status": "skipped", "reason": "no JSON file"})
#             continue
            
#         if len(matching_files) > 1:
#             print(f"Warning: Multiple JSON files found for {university_name}, using the first one")
#         json_path = matching_files[0]
#         print(f"Processing university: {university_name} using {json_path}\n")

#         try:
#             with open(json_path, 'r', encoding='utf-8') as f:
#                 colleges = json.load(f)
#         except Exception as e:
#             print(f"Error loading JSON for {university_name}: {e}")
#             results.append({"university": university_name, "status": "error", "reason": f"JSON load error: {e}"})
#             continue

#         output_dir = PROJECT_ROOT / "data" / "schools" / university_name
#         os.makedirs(output_dir, exist_ok=True)

#         college_results = []
#         for college in colleges:
#             college_name = college["name"]
#             college_url = college["URL"]
#             if not college_url.startswith("http"):
#                 college_url = urljoin(school_website, college_url)
                
#             try:
#                 teachers = process_college_teachers(college_name, college_url, output_dir)
#                 file_path = output_dir / f"{college_name}.json"
#                 with open(file_path, 'w', encoding='utf-8') as f:
#                     json.dump(teachers, f, ensure_ascii=False, indent=4)
#                 print(f"Saved {college_name} teachers to {file_path}\n")
#                 college_results.append({"college": college_name, "teachers_count": len(teachers), "status": "success"})
#             except Exception as e:
#                 print(f"Error processing college {college_name} in {university_name}: {e}")
#                 college_results.append({"college": college_name, "status": "error", "reason": str(e)})

#         results.append({
#             "university": university_name, 
#             "status": "completed", 
#             "college_results": college_results
#         })
    
#     return results

# if __name__ == "__main__":
#     # Load school websites
#     chinese_schools_path = PROJECT_ROOT / "chinese_schools.json"
#     with open(chinese_schools_path, 'r', encoding='utf-8') as f:
#         schools_data = json.load(f)
    
#     # 将学校数据分成50批
#     batch_size = max(1, len(schools_data) // 50)
#     school_batches = []
#     for i in range(0, len(schools_data), batch_size):
#         batch = schools_data[i:i + batch_size]
#         school_batches.append(batch)
    
#     print(f"总共有 {len(schools_data)} 所学校，分成 {len(school_batches)} 个批次执行")
    
#     # 准备多进程参数
#     args_mat = [(batch,) for batch in school_batches]
    
#     # 使用多进程并行执行，设置合适的进程池大小
#     # 注意：根据你的系统资源和API限制调整pool_size
#     pool_size = min(10, len(school_batches))  # 限制最大进程数
    
#     results = multi_process_exec_v0(
#         process_single_school_batch, 
#         args_mat, 
#         pool_size=pool_size,
#         desc="处理学校数据"
#     )
    
#     # 汇总结果
#     all_results = []
#     for batch_result in results:
#         all_results.extend(batch_result)
    
#     # 保存最终结果
#     summary_path = PROJECT_ROOT / "data" / "processing_summary.json"
#     with open(summary_path, 'w', encoding='utf-8') as f:
#         json.dump(all_results, f, ensure_ascii=False, indent=2)
    
#     print(f"所有批次处理完成！结果已保存到 {summary_path}")