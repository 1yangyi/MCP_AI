import requests
import json
import os
import time
from datetime import datetime
from pathlib import Path

# 从配置文件导入服务器URL
from src.config import BROWSER_MCP_URL, HTML_PARSER_URL

# 确保输出目录存在
RESULTS_DIR = Path("output")
RESULTS_DIR.mkdir(exist_ok=True)

def process_whu_website():
    print("开始处理武汉大学网站(whu.edu.cn)")
    
    result = {
        "university": {
            "name": "武汉大学",
            "website": "https://www.whu.edu.cn/"
        },
        "pages_visited": [],
        "collected_data": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 步骤1: 使用browser.py导航到whu.edu.cn
        print("\n1. 使用browser.py导航到whu.edu.cn...")
        navigate_response = requests.post(
            f"{BROWSER_MCP_URL}/navigate",
            json={"url": "https://www.whu.edu.cn", "wait_time": 2}  # 减少等待时间
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
        
        # 步骤3: 使用html_extractor.py解析HTML内容
        print("\n3. 使用html_extractor.py解析HTML内容...")
        parse_response = requests.post(
            f"{HTML_PARSER_URL}/parse",
            json={
                "url": current_url,
                "output_prefix": "whu_edu_cn"
            }
        )
        
        if parse_response.status_code != 200:
            print(f"解析失败: {parse_response.text}")
            return
        
        parse_data = parse_response.json()
        print(f"解析状态: {parse_data['status']}")
        
        # 从生成的JSON文件中读取链接信息
        try:
            with open("whu_edu_cn.json", "r", encoding="utf-8") as f:
                tree_data = json.load(f)
            
            # 提取所有链接
            links = []
            def extract_links(nodes):
                for node in nodes:
                    if "text" in node and "url" in node:
                        links.append({
                            "text": node["text"],
                            "url": node["url"],
                            "selector": f"a[href='{node['url']}']" if "url" in node else ""
                        })
                    if "children" in node:
                        extract_links(node["children"])
            
            extract_links(tree_data)
            
            # 更新解析数据
            parse_data["links"] = links
        except Exception as e:
            print(f"提取链接时出错: {str(e)}")
        
        # 步骤4: 查找包含"院系"的链接
        print("\n4. 查找包含'院系'的链接...")
        found_link = False
        
        if "links" in parse_data:
            for link in parse_data["links"]:
                link_text = link.get("text", "")
                # 检查链接文本是否包含"院系"或URL是否包含"yxsz"
                if "院系" in link_text or "yxsz" in link.get("url", ""):
                    print(f"找到院系相关链接: {link_text} ({link.get('url', '')})")
                    # 构建完整URL
                    click_url = link.get("url")
                    if not click_url.startswith("http"):
                        base_url = "https://www.whu.edu.cn/"
                        click_url = base_url + click_url
                    
                    print(f"导航到URL: {click_url}")
                    # 直接导航到URL
                    click_response = requests.post(
                        f"{BROWSER_MCP_URL}/navigate",
                        json={"url": click_url, "wait_time": 3}
                    )
                    
                    if click_response.status_code != 200:
                        print(f"点击链接失败: {click_response.text}")
                        continue
                    
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
                            "output_prefix": "whu_yxsz"
                        }
                    )
                    
                    if new_parse_response.status_code == 200:
                        new_parse_data = new_parse_response.json()
                        print(f"院系页面解析成功")
                        
                        # 从生成的JSON文件中读取院系设置页面的数据
                        try:
                            with open("whu_yxsz.json", "r", encoding="utf-8") as f:
                                yxsz_data = json.load(f)
                            
                            # 提取院系设置页面的链接和内容
                            yxsz_links = []
                            yxsz_content = []
                            
                            def extract_data(nodes):
                                for node in nodes:
                                    if "text" in node and node["text"].strip():
                                        yxsz_content.append(node["text"].strip())
                                    if "text" in node and "url" in node:
                                        yxsz_links.append({
                                            "text": node["text"],
                                            "url": node["url"],
                                            "selector": f"a[href='{node['url']}']" if "url" in node else ""
                                        })
                                    if "children" in node:
                                        extract_data(node["children"])
                            
                            extract_data(yxsz_data)
                            
                            # 添加院系页面数据
                            result["collected_data"]["secondary_page"] = {
                                "title": click_data["title"],
                                "url": click_data["url"],
                                "links": yxsz_links,
                                "content": "\n".join(yxsz_content)
                            }
                            
                            found_link = True
                        except Exception as e:
                            print(f"提取院系设置页面数据时出错: {str(e)}")
                            result["collected_data"]["secondary_page"] = {
                                "title": click_data["title"],
                                "url": click_data["url"],
                                "error": str(e)
                            }
                    else:
                        print(f"院系页面解析失败: {new_parse_response.text}")
                    
                    break
        
        if not found_link:
            print("未找到院系相关链接")
            result["error"] = "未找到院系相关链接"
        
        # 保存结果
        result_file = RESULTS_DIR / f"whu_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n结果已保存到: {result_file}")
        print("\n处理完成!")
        
    except Exception as e:
        print(f"处理过程中出错: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    process_whu_website()