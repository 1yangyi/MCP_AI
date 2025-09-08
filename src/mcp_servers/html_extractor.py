import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

import requests
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="HTML Parser Updated MCP Server (original_htmlParser based)")


# python -m src.mcp_servers.html_extractor --server



# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据模型
class ParseRequest(BaseModel):
    url: str
    output_prefix: Optional[str] = None
    output_dir: Optional[str] = None

class ParseResponse(BaseModel):
    status: str
    url: str
    tree_depth: int
    unique_urls_count: int
    text_entries_count: int
    output_files: Dict[str, str]
    processing_time: float
    message: Optional[str] = None

def check_buttons_pairs(s):
    """检查字符串中是否包含至少两个连续的text和url对"""
    pattern = r'buttons(.*?text.*?url.*?){2}'
    if re.search(pattern, s, re.DOTALL):
        return True
    else:
        return False

def process_file(filename):
    """处理文件，调整缩进"""
    # 读取文件所有行
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 存储处理后的行和节点栈
    processed_lines = []
    stack = []  # 栈中元素为 (当前行索引, 原始缩进, 节点值)

    for idx, line in enumerate(lines):
        # 计算当前行的原始缩进（空格数）
        indent = 0
        while indent < len(line) and line[indent] == ' ':
            indent += 1

        content = line.strip()
        current_value = content

        # 移除栈中所有缩进大于等于当前行的节点（找到父节点）
        while stack and stack[-1][1] >= indent:
            stack.pop()

        # 检查父节点是否满足条件
        adjust = 0
        if stack:
            parent_idx, parent_indent, parent_value = stack[-1]
            # 如果父节点满足条件，则计算需要删除的缩进量
            if check_buttons_pairs(parent_value):
                adjust = indent - parent_indent  # n = 当前缩进 - 父缩进

        # 应用缩进调整
        new_indent = max(0, indent - adjust)
        new_line = ' ' * new_indent + content + '\n'
        processed_lines.append(new_line)

        # 将当前节点压入栈
        stack.append((idx, indent, current_value))

    # 将处理后的内容写回文件
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(processed_lines)

def fetch_html(url):
    """获取网页HTML内容"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 检查HTTP状态码（如404/500）
        response.encoding = response.apparent_encoding  # 自动检测编码
        return response.text  # 返回字符串类型的HTML
    except requests.exceptions.RequestException as e:
        # 网络请求失败时返回字典标记
        return {"tree": False}

def is_clickable(element):
    """判断元素是否为可点击按钮（返回True/False）"""
    tag = element.name
    if tag == 'button':
        return True
    if tag == 'input':
        input_type = element.get('type', '').lower()
        return input_type in {'button', 'submit', 'reset'}
    if tag == 'a':
        href = element.get('href', '')
        return href and not href.startswith(('javascript:', '#'))
    if element.has_attr('onclick'):
        return True
    if tag == 'h3' or tag == 'h2':
        return True
    return False

def extract_button_info(element):
    """提取单个按钮的详细信息（text、relative_url等）"""
    # 提取text（针对input标签特殊处理value属性）
    if element.name == 'input':
        text = element.get('value', '')  # input的text是value属性
    else:
        text = element.get_text(strip=True)  # 其他标签提取子节点文本

    # 提取relative_url（根据元素类型）
    relative_url = ""
    if element.name == 'a':
        # 超链接：直接取href的原始值
        relative_url = element.get('href', '')
    elif element.name in ['input', 'button']:
        # 表单提交按钮：查找父<form>的action属性
        form = element.find_parent('form')
        if form:
            relative_url = form.get('action', '')
    else:
        # 其他元素（如带onclick的div）：尝试从onclick中解析
        onclick = element.get('onclick', '')
        match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]" ,onclick)
        if match:
            relative_url = match.group(1)

    return {
        "tag": element.name,
        "text": text,
        "relative_url": relative_url
    }

def build_tree_structure(element, parent_node=None):
    """递归构建树状结构（包含按钮的text和relative_url）"""
    # 当前节点的基础信息（标签、class、id）
    node_info = {
        "tag": element.name,
        "class": ' '.join(element.get('class', [])),  # class转为字符串
        "buttons": [] , # 当前节点直接包含的按钮列表（含text和relative_url）
        "children": []  # 子节点列表（节点或按钮）
    }

    # 递归处理子节点（仅处理元素节点，跳过文本节点）
    for child in element.children:
        if child.name is None:  # 跳过文本节点（如换行符）
            continue

        # 递归构建子节点的树结构
        child_tree = build_tree_structure(child, parent_node=node_info)

        # 将子节点添加到当前节点的children中（仅当子节点非空）
        if child_tree["buttons"] or child_tree["children"]:
            node_info["children"].append(child_tree)

    # 将当前可点击元素添加到父节点的buttons列表中
    if is_clickable(element):
        button_info = extract_button_info(element)
        if parent_node is not None:
            parent_node["buttons"].append(button_info)  # 添加到父节点的buttons
        else:
            node_info["buttons"].append(button_info)  # 根节点自身是按钮（罕见）

    return node_info

def filter_empty_nodes(node):
    """递归过滤无按钮的空节点，返回处理后的节点字典"""
    # 复制当前节点，避免修改原节点
    filtered_node = {
        "tag": node["tag"],
        "class": node["class"],
        "buttons": [],
        "children": []
    }

    # 保留当前节点的按钮
    filtered_node["buttons"] = node["buttons"].copy()

    # 递归过滤子节点
    for child in node["children"]:
        filtered_child = filter_empty_nodes(child)
        # 仅保留非空的子节点（即过滤后仍有按钮或子节点的子节点）
        if filtered_child.get("buttons") or filtered_child.get("children"):
            filtered_node["children"].append(filtered_child)

    # 如果当前节点没有按钮，且没有保留的子节点，则返回空字典（表示移除该节点）
    if not filtered_node["buttons"] and not filtered_node["children"]:
        return {}

    return filtered_node

def extract_clickable_buttons_tree(url, output_path):
    """主函数：提取网页中所有可点击按钮并按树状结构输出（含text和relative_url）"""
    html = fetch_html(url)
    # 处理网络请求失败的情况
    if isinstance(html, dict):
        return html
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        return {"tree": False}  # HTML解析失败时返回

    # 从根节点<html>开始构建树状结构
    root = soup.find('html')
    if not root:
        return {"tree": False}  # 未找到HTML根节点

    # 构建完整的树状结构
    tree = build_tree_structure(root)

    filtered_tree = filter_empty_nodes(tree)

    with open(output_path, "w", encoding="utf-8") as f:
        print_tree(filtered_tree, indent=0, file=f)  # 传递文件对象给函数

    # 若过滤后无有效节点，返回tree:false
    if not filtered_tree.get("buttons") and not filtered_tree.get("children"):
        return {"tree": False}

    return {"tree": filtered_tree}

def print_tree(node, indent=0, file=None):
    # 提取当前节点的基础信息
    tag = node.get("tag", "")
    class_attr = node.get("class", "")
    buttions = node.get("buttons", [])  # 获取buttions列表（可能为空）

    # 判断是否需要打印当前节点（buttions非空）
    should_print = len(buttions) > 0

    # 打印当前节点（若需要）
    if should_print:
        # 构建缩进字符串（每层2空格）
        indent_str = "  " * indent
        # 整理节点属性（仅非空属性）
        attrs = []
        if tag:
            attrs.append(f"tag='{tag}'")
        if class_attr:
            attrs.append(f"class='{class_attr}'")
        # 整理buttions内容（每个按钮的text和relative_url）
        buttion_strs = []
        for btn in buttions:
            btn_text = btn.get("text", "").strip()
            btn_url = btn.get("relative_url", "").strip()
            if btn_text or btn_url:  # 按钮有有效内容才显示
                btn_info = f"text='{btn_text}', url='{btn_url}'"
                buttion_strs.append(btn_info)
        if buttion_strs:
            attrs.append(f"buttons=[{', '.join(buttion_strs)}]")
        # 打印节点信息
        if file:
            file.write(f"{indent_str}{{ {', '.join(attrs)} }}\n")

    # 递归处理子节点（无论当前节点是否打印）
    for child in node.get("children", []):
        print_tree(child, indent + 1, file)

def parse_buttons(line):
    """解析一行中的buttons属性，返回按钮列表"""
    # 匹配buttons=[...]部分
    buttons_match = re.search(r"buttons=\[(.*?)\]", line)
    if not buttons_match:
        return []

    buttons_str = buttons_match.group(1)
    # 匹配text和url对
    pattern = r"text='(.*?)', url='(.*?)'"
    buttons = re.findall(pattern, buttons_str)
    return [{"text": text, "url": url} for text, url in buttons]

def parse_line(line):
    """解析单行数据，返回节点信息"""
    # 计算缩进层级（每2个空格为一级）
    indent = len(line) - len(line.lstrip())
    level = indent // 2

    # 解析按钮数据
    buttons = parse_buttons(line)

    return {
        "level": level,
        "buttons": buttons
    }

def build_tree(lines):
    """构建树形结构"""
    # 初始化根节点和栈
    root = []
    stack = [{"node": None, "level": -1, "children": root}]

    for line in lines:
        if not line.strip():
            continue

        data = parse_line(line)
        level = data["level"]
        buttons = data["buttons"]

        # 如果没有按钮数据，跳过该行
        if not buttons:
            continue

        # 弹出栈中层级大于等于当前层级的节点
        while stack and stack[-1]["level"] >= level:
            stack.pop()

        # 获取父节点
        parent = stack[-1]

        # 处理多个按钮的情况
        for i, button in enumerate(buttons):
            # 创建新节点
            new_node = {"text": button["text"], "url": button["url"]}

            # 如果是最后一个按钮且可能有子节点
            if i == len(buttons) - 1:
                new_node["children"] = []
                # 压入栈以便后续子节点挂载
                stack.append({
                    "node": new_node,
                    "level": level,
                    "children": new_node["children"]
                })

            # 添加到父节点的children
            parent["children"].append(new_node)

    # 递归删除空children列表
    def remove_empty_children(node):
        if isinstance(node, dict):
            if "children" in node and len(node["children"]) == 0:
                del node["children"]
            else:
                # 递归处理子节点
                if "children" in node:
                    for child in node["children"]:
                        remove_empty_children(child)
        elif isinstance(node, list):
            for item in node:
                remove_empty_children(item)

    remove_empty_children(root)

    return root

def main(url=None, output_prefix=None, output_dir="."):
    """主函数，支持命令行参数和交互式输入"""
    start_time = time.time()
    
    # 如果没有提供参数，使用命令行参数或交互式输入
    if url is None:
        if len(sys.argv) > 1:
            url = sys.argv[1]
        else:
            # 交互式输入URL
            url = input("请输入要解析的网站URL: ").strip()
            if not url:
                print("错误: 必须提供有效的URL")
                return {
                    'success': False,
                    'message': '错误: 必须提供有效的URL',
                    'output_files': {}
                }
            # 确保URL格式正确
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
    
    if output_prefix is None:
        if len(sys.argv) > 2:
            output_prefix = sys.argv[2]
        else:
            # 根据URL自动生成输出前缀
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '').replace('.', '_')
            output_prefix = domain if domain else "result"
    
    # 处理输出目录
    output_dir = Path(output_dir)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # 构建输出文件路径
    txt_file = output_dir / f"{output_prefix}.txt"
    json_file = output_dir / f"{output_prefix}.json"
    middle_file = output_dir / f"{output_prefix}_middle_file.txt"
    # txt_file = f"D:\project08\MCP_AI\data\output\{output_prefix}.txt"
    # json_file = f"D:\project08\MCP_AI\data\output\{output_prefix}.json"
    # middle_file = f"D:\project08\MCP_AI\data\output\{output_prefix}_middle_file.txt"
    
    try:
        output = extract_clickable_buttons_tree(url, str(txt_file))
        if output.get("tree") is False:
            return {
                'success': False,
                'message': '解析失败：无法获取网页内容或解析HTML',
                'output_files': {}
            }
        
        with open(middle_file, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(output, indent=2, ensure_ascii=False))

        # 解决父节点不确定的问题，思路：把爷爷节点作为父节点
        process_file(str(txt_file))

        with open(txt_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            not_repeated = []
            datas = []
            for l in lines:
                if l.strip() not in not_repeated:
                    not_repeated.append(l.strip())
                    datas.append(l)

        # 构建树形结构
        result = build_tree(datas)
        
        # 保存为JSON文件
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 统计信息
        def count_nodes(tree):
            if isinstance(tree, list):
                count = 0
                for node in tree:
                    count += count_nodes(node)
                return count
            elif isinstance(tree, dict):
                count = 1
                if "children" in tree:
                    for child in tree["children"]:
                        count += count_nodes(child)
                return count
            return 0
        
        def count_unique_urls(tree, urls=None):
            if urls is None:
                urls = set()
            
            if isinstance(tree, list):
                for node in tree:
                    count_unique_urls(node, urls)
            elif isinstance(tree, dict):
                if "url" in tree and tree["url"]:
                    urls.add(tree["url"])
                if "children" in tree:
                    for child in tree["children"]:
                        count_unique_urls(child, urls)
            
            return len(urls)
        
        tree_depth = 3  # 简化的深度计算
        text_entries_count = count_nodes(result)
        unique_urls_count = count_unique_urls(result)
        
        processing_time = time.time() - start_time
        
        return {
            'success': True,
            'message': '解析完成',
            'tree_depth': tree_depth,
            'unique_urls_count': unique_urls_count,
            'text_entries_count': text_entries_count,
            'output_files': {
                'txt': str(txt_file),
                'json': str(json_file),
                'middle': str(middle_file)
            },
            'processing_time': processing_time
        }
    except Exception as e:
        processing_time = time.time() - start_time
        return {
            'success': False,
            'message': f'执行失败: {str(e)}',
            'output_files': {},
            'processing_time': processing_time
        }

def parse_website(url, output_prefix=None, output_dir="."):
    """简化的网站解析接口"""
    return main(url, output_prefix, output_dir)

@app.post("/parse", response_model=ParseResponse)
async def parse_html(request: ParseRequest):
    """解析HTML并提取可点击元素的树状结构"""
    start_time = time.time()
    
    try:
        # 设置默认值
        output_dir = request.output_dir or "."
        # 调用main函数进行解析
        result = main(request.url, request.output_prefix, output_dir)
        processing_time = time.time() - start_time
        
        if result['success']:
            return ParseResponse(
                status="success",
                url=request.url,
                tree_depth=result['tree_depth'],
                unique_urls_count=result['unique_urls_count'],
                text_entries_count=result['text_entries_count'],
                output_files=result['output_files'],
                processing_time=processing_time,
                message=result['message']
            )
        else:
            return ParseResponse(
                status="error",
                url=request.url,
                tree_depth=0,
                unique_urls_count=0,
                text_entries_count=0,
                output_files={},
                processing_time=processing_time,
                message=result['message']
            )
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"解析失败: {str(e)}")
        return ParseResponse(
            status="error",
            url=request.url,
            tree_depth=0,
            unique_urls_count=0,
            text_entries_count=0,
            output_files={},
            processing_time=processing_time,
            message=str(e)
        )

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "HTML Parser Updated MCP Server (original_htmlParser based)"}

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 检查是否是服务器模式
        if sys.argv[1] == "--server":
            print("启动MCP服务器...")
            uvicorn.run(app, host="0.0.0.0", port=8080)
        elif len(sys.argv) == 2:
            # 只提供URL
            url = sys.argv[1]
            result = main(url)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif len(sys.argv) == 3:
            # 提供URL和输出前缀
            url = sys.argv[1]
            output_prefix = sys.argv[2]
            result = main(url, output_prefix)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif len(sys.argv) == 4:
            # 提供URL、输出前缀和输出目录
            url = sys.argv[1]
            output_prefix = sys.argv[2]
            output_dir = sys.argv[3]
            result = main(url, output_prefix, output_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("用法: python HTML_parser_updated_mcp.py <URL> [输出前缀] [输出目录]")
            print("或者: python HTML_parser_updated_mcp.py --server  # 启动MCP服务器")
    else:
        # 交互模式
        try:
            # 尝试交互式输入
            url = input("请输入要解析的网站URL: ").strip()
            if url:
                result = main(url)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("启动MCP服务器...")
                uvicorn.run(app, host="0.0.0.0", port=8080)
        except (KeyboardInterrupt, EOFError):
            print("\n启动MCP服务器...")
            uvicorn.run(app, host="0.0.0.0", port=8080)


            