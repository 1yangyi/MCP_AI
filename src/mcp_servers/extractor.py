import re
from bs4 import BeautifulSoup

def check_buttons_pairs(s):
    """检查字符串中是否包含至少两个连续的text和url对"""
    pattern = r'buttons(.*?text.*?url.*?){2}'
    if re.search(pattern, s, re.DOTALL):
        return True
    else:
        return False

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
    if element.name == 'input':
        text = element.get('value', '')
    else:
        text = element.get_text(strip=True)

    relative_url = ""
    if element.name == 'a':
        relative_url = element.get('href', '')
    elif element.name in ['input', 'button']:
        form = element.find_parent('form')
        if form:
            relative_url = form.get('action', '')
    else:
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
    node_info = {
        "tag": element.name,
        "class": ' '.join(element.get('class', [])),
        "buttons": [],
        "children": []
    }

    for child in element.children:
        if child.name is None:
            continue
        child_tree = build_tree_structure(child, parent_node=node_info)
        if child_tree["buttons"] or child_tree["children"]:
            node_info["children"].append(child_tree)

    if is_clickable(element):
        button_info = extract_button_info(element)
        if parent_node is not None:
            parent_node["buttons"].append(button_info)
        else:
            node_info["buttons"].append(button_info)

    return node_info

def filter_empty_nodes(node):
    """递归过滤无按钮的空节点，返回处理后的节点字典"""
    filtered_node = {
        "tag": node["tag"],
        "class": node["class"],
        "buttons": node["buttons"].copy(),
        "children": []
    }

    for child in node["children"]:
        filtered_child = filter_empty_nodes(child)
        if filtered_child.get("buttons") or filtered_child.get("children"):
            filtered_node["children"].append(filtered_child)

    if not filtered_node["buttons"] and not filtered_node["children"]:
        return {}

    return filtered_node

def print_tree_to_string(node, indent=0):
    lines = []
    tag = node.get("tag", "")
    class_attr = node.get("class", "")
    buttons = node.get("buttons", [])

    should_print = len(buttons) > 0

    if should_print:
        indent_str = "  " * indent
        attrs = []
        if tag:
            attrs.append(f"tag='{tag}'")
        if class_attr:
            attrs.append(f"class='{class_attr}'")
        button_strs = []
        for btn in buttons:
            btn_text = btn.get("text", "").strip()
            btn_url = btn.get("relative_url", "").strip()
            if btn_text or btn_url:
                btn_info = f"text='{btn_text}', url='{btn_url}'"
                button_strs.append(btn_info)
        if button_strs:
            attrs.append(f"buttons=[{', '.join(button_strs)}]")
        lines.append(f"{indent_str}{{ {', '.join(attrs)} }}\n")

    for child in node.get("children", []):
        child_lines = print_tree_to_string(child, indent + 1)
        lines.extend(child_lines)

    return lines

def process_lines(lines):
    """处理行列表，调整缩进"""
    processed_lines = []
    stack = []

    for idx, line in enumerate(lines):
        indent = 0
        while indent < len(line) and line[indent] == ' ':
            indent += 1
        content = line.strip()
        current_value = content

        while stack and stack[-1][1] >= indent:
            stack.pop()

        adjust = 0
        if stack:
            parent_idx, parent_indent, parent_value = stack[-1]
            if check_buttons_pairs(parent_value):
                adjust = indent - parent_indent

        new_indent = max(0, indent - adjust)
        new_line = ' ' * new_indent + content + '\n'
        processed_lines.append(new_line)

        stack.append((idx, indent, current_value))

    return processed_lines

def parse_html(html_str: str) -> str:
    """解析HTML字符串并返回处理后的字符串"""
    try:
        soup = BeautifulSoup(html_str, 'html.parser')
    except Exception:
        return ""

    root = soup.find('html')
    if not root:
        return ""

    tree = build_tree_structure(root)
    filtered_tree = filter_empty_nodes(tree)

    if not filtered_tree.get("buttons") and not filtered_tree.get("children"):
        return ""

    lines = print_tree_to_string(filtered_tree)
    processed = process_lines(lines)

    not_repeated = []
    datas = []
    for l in processed:
        stripped = l.strip()
        if stripped not in not_repeated:
            not_repeated.append(stripped)
            datas.append(l)

    return ''.join(datas)