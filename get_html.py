import random
import time
import requests
import urllib3
import chardet  # 需要安装：pip install chardet
import logging

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_html(url, max_retries=1, base_delay=1, timeout=5):
    """
    获取给定URL的HTML源码，支持HTTP/HTTPS，提高鲁棒性处理反爬和错误。
    
    :param url: 要获取的URL
    :param max_retries: 最大重试次数
    :param base_delay: 基础延迟秒数
    :param timeout: 请求超时秒数
    :return: HTML字符串
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    ]
    
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    for attempt in range(max_retries):
        try:
            # 添加 verify=False 来跳过SSL证书验证
            if url.startswith('https://'):
                response = session.get(url, timeout=timeout, allow_redirects=True, verify=False)
            else:
                response = session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()  # 引发HTTP错误的异常
            
            # 检查是否是HTML内容
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                raise ValueError("响应不是HTML内容")
            
            # 编码处理
            if response.encoding.lower() == 'iso-8859-1':
                # 如果响应编码是ISO-8859-1，尝试自动检测
                detected_encoding = chardet.detect(response.content)['encoding']
                if detected_encoding:
                    response.encoding = detected_encoding
                else:
                    # 如果自动检测失败，尝试常见的中文编码
                    for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
                        try:
                            response.content.decode(encoding)
                            response.encoding = encoding
                            break
                        except UnicodeDecodeError:
                            continue
            
            return response.text
        
        except requests.RequestException as e:
            print(f"尝试 {attempt + 1}/{max_retries} 失败: {str(e)}")
            if attempt < max_retries - 1:
                # 指数退避延迟
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
    
    return ''


import os
import json


def read_json_files_from_folder(root_folder):
    """
    遍历根文件夹下的所有二级文件夹，读取其中的JSON文件并打印内容
    
    Args:
        root_folder (str): 根文件夹路径
    """
     # 获取根文件夹下所有二级文件夹
    secondary_folders = [f.path for f in os.scandir(root_folder) if f.is_dir()]
    
    # 自定义排序函数：按文件夹名称以'_'分割后前半部分转为int类型排序

    def folder_sort_key(folder_path):
        folder_name = os.path.basename(folder_path)
        try:
            # 按'_'分割并取第一部分转为int
            prefix = folder_name.split('_', 1)[0]
            return int(prefix)
        except (ValueError, IndexError):
            # 如果转换失败或没有'_'，返回一个很大的值，让这些文件夹排在后面
            return float('inf')
    # 按自定义规则排序遍历二级文件夹
    for secondary_folder in sorted(secondary_folders, key=folder_sort_key):
        # print(os.path.basename(secondary_folder))
        if not os.path.basename(secondary_folder).endswith("武汉大学"):
            continue
        # 获取二级文件夹下的所有三级文件夹
        tertiary_folders = [f.path for f in os.scandir(secondary_folder) if f.is_dir()]
        
        # 按自定义规则排序遍历三级文件夹
        for tertiary_folder in tertiary_folders:
            json_files = []
            
            # 查找三级文件夹中的JSON文件
            for entry in os.scandir(tertiary_folder):
                if entry.is_file() and entry.name.lower().endswith('.json'):
                    json_files.append(entry.path)
            
            # 处理找到的JSON文件（每个三级文件夹最多一个）
            if json_files:
                # 如果有多个JSON文件，只取第一个
                json_file = sorted(json_files)[0]
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for teacher in data:
                            name = teacher["name"]
                            url = teacher["URL"]
                            htmlTXT = get_html(url)
                            output_path = os.path.join(tertiary_folder, f"{name}.html")
                            with open(output_path, "w", encoding="utf-8") as html_file:
                                html_file.write(htmlTXT)
                            if not htmlTXT:
                                logging.warning(f"Empty HTML for {url}: {output_path}")
                except Exception as e:
                    print(f"错误：读取文件 {json_file} 时发生异常 - {str(e)}")
            else:
                print(f"注意：三级文件夹 {tertiary_folder} 中没有找到JSON文件")


if __name__ == "__main__":
    # logging.basicConfig(level=logging.WARNING, filename='logs/exceptions.log', filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')
    # folder_path = "data/schoolTeachers"
    
    # if not os.path.exists(folder_path):
    #     print("错误：指定的路径不存在")
    # else:
    #     read_json_files_from_folder(folder_path)
    url = "http://www.ynusky.ynu.edu.cn/"
    htmlTXT = get_html(url)
    with open("test.html", "w", encoding="utf-8") as f:
        f.write(htmlTXT)