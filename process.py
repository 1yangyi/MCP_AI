import requests
import json
import os
import time
from datetime import datetime
from pathlib import Path
from src.mcp_servers.ai import extract_entities_with_deepseek,read_json_file,_safe_json_dumps,extract_schools_with_deepseek
# 从配置文件导入服务器URL和目录配置
from src.config import BROWSER_MCP_URL, HTML_PARSER_URL, OUTPUT_DIR, PROJECT_ROOT

# 确保输出目录存在
RESULTS_DIR = OUTPUT_DIR
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# 创建中间文件目录
MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file"
MIDDLE_FILE_DIR.mkdir(exist_ok=True)

DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"

def process_university_website(university_name: str, university_url: str):
    print(f"开始处理{university_name}网站({university_url})")
    
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
        # print(f"navigate_data:{navigate_data['message']}")
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
        
        # 步骤3: 使用html_extractor.py解析HTML内容
        print("\n3. 使用html_extractor.py解析HTML内容...")
        parse_response = requests.post(
            f"{HTML_PARSER_URL}/parse",
            json={
                "url": current_url,
                "output_prefix": university_name,
                "output_dir": str(MIDDLE_FILE_DIR)  # 明确指定输出到中间文件目录
            }
        )
        
        if parse_response.status_code != 200:
            print(f"解析失败: {parse_response.text}")
            return
        
        parse_data = parse_response.json()
        print(f"parse_data:{parse_data}")
        print(f"解析状态: {parse_data['status']}")
        
        # 步骤4: 查找包含"院系"的链接
        print("\n4. 查找包含院系的链接...")

        # 从中间文件目录读取文件
        example_obj = read_json_file("example.json")
        text_obj = read_json_file(str(MIDDLE_FILE_DIR / f"{university_name}.json"))
        example_text = _safe_json_dumps(example_obj)
        text = _safe_json_dumps(text_obj)

        result_link = extract_entities_with_deepseek(
            api_key=DEEPSEEK_API_KEY,
            text=text.replace("\n", ""),
            example=example_text,
        )
        print(f"result_link:{result_link}")
        parts = result_link.get("button_text").split('@', 1)
        button_text = parts[0]
        click_url = parts[1]
        
        if result_link.get("status") == "success":
            print("识别结果(按钮文本):", button_text)
        else:
            print("抽取失败:", result_link.get("message", "未知错误"))
            if "raw_response" in result_link:
                print("模型原始返回:", result_link.get("raw_response"))


        if not click_url.startswith("http"):
            base_url = university_url if university_url.endswith("/") else f"{university_url}/"
            click_url = base_url + click_url
        
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
        
        # 解析新页面
        print("\n5. 解析院系页面...")
        new_parse_response = requests.post(
            f"{HTML_PARSER_URL}/parse",
            json={
                "url": click_data['url'],
                "output_prefix": f"{university_name}_schools",
                "output_dir": str(MIDDLE_FILE_DIR)  # 明确指定输出到中间文件目录
            }
        )
        
        # if new_parse_response.status_code == 200:
        new_parse_data = new_parse_response.json()
        print(f"院系页面解析成功")
        

        schools_obj = read_json_file(str(MIDDLE_FILE_DIR / f"{university_name}_schools.json"))
        schools_text = _safe_json_dumps(schools_obj)
        schools_result = extract_schools_with_deepseek(
            api_key=DEEPSEEK_API_KEY,
            text=schools_text.replace("\n", "")
        )
        # print(f"schools_result:{schools_result}")
        schools_list = schools_result.get("schools")

        # 指定保存路径到输出目录
        file_path = RESULTS_DIR / f"{university_name}_schools_result.json"

        # 将字符串数据保存为JSON文件
        try:
            # 检查 schools_list 是否为空或只包含空白字符
            if not schools_list or schools_list.strip() == "":
                print("警告: schools_list 为空，使用空列表作为默认值")
                data = []
            else:
                # 解析JSON字符串
                data = json.loads(schools_list)
            
            # 确保目录存在
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            
            # 写入JSON文件
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            
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
    # 处理武汉大学网站
    process_university_website("华中科技大学", "https://www.hust.edu.cn/")

    def read_school_json(file_path):
        """
        读取指定的school.json文件
        
        参数:
        file_path (str): JSON文件的完整路径
        
        返回:
        dict: 解析后的JSON数据，如果出错则返回None
        """
        try:
            # 将路径转换为Path对象
            json_file = Path(file_path)
            
            # 检查文件是否存在
            if not json_file.exists():
                print(f"错误: 文件 '{file_path}' 不存在")
                return None
            
            # 检查是否为JSON文件
            if json_file.suffix.lower() != '.json':
                print(f"错误: 文件 '{file_path}' 不是JSON文件")
                return None
            
            # 读取JSON文件
            with open(json_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                print(f"成功读取文件: {json_file.name}")
                return data
                
        except json.JSONDecodeError as e:
            print(f"错误: 文件 '{json_file.name}' 不是有效的JSON格式 - {str(e)}")
            return None
        except Exception as e:
            print(f"读取文件 '{json_file.name}' 时出错: {str(e)}")
            return None


    # 批量处理代码 - 已注释
    '''
    # 指定文件路径
    json_file_path = r"D:\project08\MCP_AI\data\input\top500_school_websites.json"
    
    # 读取JSON文件
    school_data = read_school_json(json_file_path)
    # 假设 school_data 是一个包含学校信息的列表
    for index, item in enumerate(school_data):
        # 只处理前100个项目
        if index >= 100:
            break
            
        school = item["school"]
        website = item["website"]
        process_university_website(school, website)
        
        # 可选：打印进度
        print(f"已处理 {index + 1}/100 所学校: {school}")
    '''
