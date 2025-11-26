import json
import re
from openai import OpenAI


def extract_teacher_button(api_key: str, text: str) -> dict:
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception as e:
        return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
    # prompt = f"""
    # # 你是一个数据收集助手，协助收集高校学院的教师信息。
    # # 现在你需要根据以下页面网页结构化列表，判断哪一个最可能引导至包含教师信息的页面，并直接返回该按钮的文本和对应URL。
    # # 链接列表：
    # # {text}
    # # 请严格按以下格式输出一个最可能的按钮文本，不要任何额外解释：
    # # 按钮文本@URL,例如，"师资力量@teachers.htm"
    # # 注意：优先选择类似"教师队伍"、"师资力量"、"Faculty"、"Professors"、"按字母排序"、"按专业分类"等明确指向教师列表的具体链接。
    # """
    prompt = f"""
    你是一个数据收集助手，协助收集高校学院的教师信息。
    请分析以下页面网页html原码，找出最可能引导至教师信息页面的链接。

    html原码：
    {text}
    判断标准（按优先级排序）：
    1. 明确包含"教师队伍"、"师资力量"、"Faculty"、"Professors"、"教学团队"等关键词
    2. 包含"教师"、"老师"、"导师"等教师相关词汇
    3. URL路径中包含teacher、faculty、szdw等关键词

    请严格按照以下JSON格式返回，不要任何额外内容：
    {{
        "button_text": "按钮文本",
        "url": "对应的URL"
    }}

    如果找不到合适的链接，返回：
    {{
        "button_text": null,
        "url": null
    }}
    """
    try:
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        content = completion.choices[0].message.content.strip()
        
        # 解析JSON响应
        import json
        result_data = json.loads(content)
        
        # 构建规范化的返回格式
        if result_data.get("button_text") and result_data.get("url"):
            return {
                "status": "success", 
                "button_text": result_data["button_text"],
                "url": result_data["url"]
            }
        else:
            return {
                "status": "success",
                "button_text": None,
                "url": None,
                "message": "未找到合适的教师信息链接"
            }
    except Exception as e:
        return {"status": "error", "message": f"Deepseek API 调用失败: {str(e)}"}
    # completion = client.chat.completions.create(
    #     model="deepseek-chat",
    #     messages=[{"role": "user", "content": prompt}],
    #     temperature=0.1
    # )
    # content = completion.choices[0].message.content
    # parts = content.split('@', 1)
    # return {"status": "success", "button_text": parts[0], "url": parts[1] if len(parts) > 1 else ""}


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
    你是一个数据分析助手，请从以下的网页内容中找出与当前页面相似的其它可能引导至包含教师信息页面的按钮或链接。
    特别关注这些关键词："杰出人才"、"特聘教师"、"博士后"、"教授"、"副教授"等；避免指向具体教师个人页面的链接。
    
    当前页面URL为：{button_url}
    
    网页内容如下：
    {text}
    
    请提取所有可能包含教师信息的按钮，并以JSON数组格式返回：
    [
      {{"name": "按钮名称1", "url": "链接URL1"}},
      {{"name": "按钮名称2", "url": "链接URL2"}}
    ]
    
    如果没有找到相关按钮，请返回空数组 []
    注意：仅输出列表格式结果，不要附加解释。
    """
    
    try:
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5  
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
    请从以下网页结构化列表中识别出其中所有教师的名称和URL。注意：名称只包含教师的姓名，不能包含任何分类标签（如"院长"、"研究员"、"院士"等）。
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

def extract_intro_button(api_key: str, text: str) -> dict:
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception as e:
        return {"status": "error", "message": f"Deepseek API 初始化失败: {str(e)}"}
    prompt = f"""
    你是一个数据收集助手，协助收集高校学院的简介信息。
    现在你需要根据以下页面网页结构化列表，判断哪一个最可能引导至包含学院简介的页面，并直接返回该按钮的文本和对应URL。
    链接列表：
    {text}
    请严格按以下格式输出一个最可能的按钮文本，不要任何额外解释：
    按钮文本@URL,例如，"学院简介@introduction.htm"
    注意：优先选择类似"学院简介"、"Introduction"、"About Us"、"学院概况"等明确指向学院简介的链接。
    """
    completion = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    content = completion.choices[0].message.content
    parts = content.split('@', 1)
    return {"status": "success", "button_text": parts[0], "url": parts[1] if len(parts) > 1 else ""}