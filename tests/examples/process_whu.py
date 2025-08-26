#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import httpx
import json
import traceback
from datetime import datetime
from pathlib import Path

# 设置结果输出路径
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# MCP 服务器 URL
BROWSER_URL = "http://localhost:8002"
HTML_EXTRACTOR_URL = "http://localhost:8080"

async def process_whu():
    """处理武汉大学网站"""
    print("开始处理武汉大学网站...")
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
        async with httpx.AsyncClient(timeout=60.0) as client:  # 将超时增加到60秒
            # 1. 导航到武汉大学网站
            print("导航到武汉大学网站...")
            response = await client.post(
                f"{BROWSER_URL}/navigate",
                json={"url": "https://www.whu.edu.cn/"}
            )
            response.raise_for_status()
            
            # 2. 获取当前页面信息
            print("获取当前页面信息...")
            response = await client.get(f"{BROWSER_URL}/current_page")
            response.raise_for_status()
            page_data = response.json()
            
            # 3. 解析 HTML
            print("解析 HTML 内容...")
            # 使用当前页面的 URL 而不是传递 HTML 内容
            response = await client.post(
                f"{HTML_EXTRACTOR_URL}/parse",
                json={
                    "url": page_data["url"],
                    "output_prefix": "whu_edu_cn"
                }
            )
            response.raise_for_status()
            parsed_data = response.json()
            
            # 从 whu_edu_cn.json 文件中读取链接信息
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
                            "selector": f"a[href='{node['url']}']"
                        })
                    if "children" in node:
                        extract_links(node["children"])
            
            extract_links(tree_data)
            
            # 更新解析数据
            parsed_data["links"] = links
            # 只保留这一行，确保响应状态正常
            response.raise_for_status()
            # 删除 parsed_data = response.json() 这一行，防止覆盖之前提取的链接
            parsed_data = response.json()
            
            # 4. 记录访问的页面
            result["pages_visited"].append({
                "url": page_data["url"],
                "title": page_data["title"],
                "timestamp": datetime.now().isoformat()
            })
            
            # 5. 收集数据
            result["collected_data"] = {
                "title": parsed_data.get("title", ""),
                "meta_description": parsed_data.get("meta_description", ""),
                "links": parsed_data.get("links", []),
                "buttons": parsed_data.get("buttons", [])
            }
            
            # 6. 如果有链接，点击包含"院系"的链接
            found_link = False
            if "links" in parsed_data:
                for link in parsed_data["links"]:
                    link_text = link.get("text", "")
                    # 扩大匹配范围，检查链接文本是否包含"院系"或URL是否包含"yxsz"
                    if "院系" in link_text or "yxsz" in link.get("url", ""):
                        print(f"找到院系相关链接: {link_text} ({link.get('url', '')})")
                        # 构建完整 URL
                        click_url = link.get("url")
                        if not click_url.startswith("http"):
                            base_url = "https://www.whu.edu.cn/"
                            click_url = base_url + click_url
                        
                        print(f"导航到URL: {click_url}")
                        # 直接导航到 URL
                        response = await client.post(
                            f"{BROWSER_URL}/navigate",
                            json={"url": click_url}
                        )
                        response.raise_for_status()
                        
                        # 获取新页面信息
                        response = await client.get(f"{BROWSER_URL}/current_page")
                        response.raise_for_status()
                        new_page_data = response.json()
                        
                        # 解析新页面
                        print(f"解析新页面: {new_page_data['url']}")
                        response = await client.post(
                            f"{HTML_EXTRACTOR_URL}/parse",
                            json={
                                "url": new_page_data["url"],
                                "output_prefix": "whu_yxsz"
                            }
                        )
                        response.raise_for_status()
                        new_parsed_data = response.json()
                        
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
                                "title": new_page_data["title"],
                                "url": new_page_data["url"],
                                "links": yxsz_links,
                                "content": "\n".join(yxsz_content)
                            }
                            
                            # 记录访问的页面
                            result["pages_visited"].append({
                                "url": new_page_data["url"],
                                "title": new_page_data["title"],
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            found_link = True
                            break
                        except Exception as e:
                            print(f"提取院系设置页面数据时出错: {str(e)}")
                            result["collected_data"]["secondary_page"] = {
                                "title": new_page_data["title"],
                                "url": new_page_data["url"],
                                "error": str(e)
                            }
                            found_link = True
                            break
                    
                    if not found_link:
                        print("未找到院系相关链接")
                        result["error"] = "未找到院系相关链接"
            
            result["status"] = "success"
            print("处理完成!")
            
    except Exception as e:
        print(f"处理过程中出错: {str(e)}")
        result["status"] = "error"
        result["error"] = str(e)
        # 添加详细的错误跟踪信息
        result["error_traceback"] = traceback.format_exc()
    
    # 保存结果
    result_file = RESULTS_DIR / f"whu_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"结果已保存到: {result_file}")
    return result

async def main():
    await process_whu()

if __name__ == "__main__":
    asyncio.run(main())