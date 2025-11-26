import requests
import json
import os
import time
import re
from datetime import datetime
from pathlib import Path
# 从配置文件导入服务器URL和目录配置
from src.config import BROWSER_MCP_URL, PROJECT_ROOT,DATA_DIR

# 确保输出目录存在
OUTPUT_DIR = DATA_DIR / "output_chinese2"
RESULTS_DIR = OUTPUT_DIR
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

# 创建中间文件目录
MIDDLE_FILE_DIR = PROJECT_ROOT / "middle_file"
MIDDLE_FILE_DIR.mkdir(exist_ok=True)

DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"

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

    # 构造提示词
    prompt = f"""
    你是一个数据收集助手，协助收集高校所有科研机构信息。
    请从以下网页html原码中识别出该学校所有科研机构的名称和URL（如果有）。html原码内容如下：
    {text}
    注意：只需要提取科研机构，不包含学院（如文学院、计算机学院等）和行政机构（如行政办公室、科学技术处、图书馆等）。
    注意：仅输出结果的json格式，不要附加解释。每个科研机构的格式为：{{"name": "", "URL": ""}}。
    如果某些研究机构只找到了名字而没有URL，也需要保留该机构，URL项置空。
    如果未识别出科研机构信息，则返回空字典。"""
    
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

def process_university_website(university_name: str, university_url: str, rank: int):
    print(f"\n开始处理第 {rank} 所学校 {university_name} 网站({university_url})")
    
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
        print(f"获取HTML成功，HTML长度: {len(html_content)}字符")

        print("\n3. 提取科研机构信息...")
        schools_result = extract_schools_with_deepseek(
            api_key=DEEPSEEK_API_KEY,
            text=html_content.replace("\n", "")
        )
        print(f"deepseek提取科研机构结果: {schools_result}")
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
            
            for item in norm:
                if item['URL'] is None:
                    item['URL'] = ''
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
    # process_university_website("国立欧亚大学 (ENU)", "https://enu.kz/", 321)
    # from get_null import get_null_list
    # null_list = get_null_list()
    # i = 0
    # for item in null_list:
    #     if item[0]<495:
    #         continue
    #     print(f"正在处理第{i+1}/{len(null_list)}个学校: Rank: {item[0]}, School: {item[1]}, Website: {item[2]}")
    #     process_university_website(item[1], item[2], item[0])
    #     i += 1
    #     print(f"第{i}/{len(null_list)}个学校: {item[0]}_{item[1]} 已处理完成")


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


    # 批量处理代码
    # 指定文件路径
    json_file_path = r"D:/project08/MCP_AI/data/input/chinese_schoolsURL.json"
    
    # 读取JSON文件
    school_data = read_school_json(json_file_path)
    # 假设 school_data 是一个包含学校信息的列表
    i = 0
    for index, item in enumerate(school_data):
        i += 1
        # if i<50:
        #     continue
        school = item["name"]
        website = item["website"]

        file = RESULTS_DIR / f"{i}_{school}_schools_result.json"
        if website == '':
            # 确保目录存在
            print(f"第 {i} 所学校: {school} 没有网站，跳过\n")
            directory = os.path.dirname(file)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            # 写入JSON文件
            with open(file, 'w', encoding='utf-8') as file:
                json.dump([], file, ensure_ascii=False, indent=2)
            continue
        process_university_website(school, website, i)
        
        # 可选：打印进度
        print(f"第 {i} 所学校: {school} 已处理完成\n")

