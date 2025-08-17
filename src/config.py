#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件 - 大学数据收集系统
定义各个MCP服务器的URL和系统参数
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
BASE_DIR = str(PROJECT_ROOT)  # 保持向后兼容

# 数据文件路径
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
TEST_DATA_DIR = DATA_DIR / "test"
UNIVERSITY_DATA_FILE = DATA_DIR / "top500_school_websites.json"

# 日志路径
LOG_DIR = PROJECT_ROOT / "logs"
LOGS_DIR = LOG_DIR  # 别名

# MCP服务器URL配置
SEARCH_MCP_URL = os.getenv("SEARCH_MCP_URL", "http://localhost:8001")
BROWSER_MCP_URL = os.getenv("BROWSER_MCP_URL", "http://localhost:8000")
HTML_PARSER_URL = os.getenv("HTML_PARSER_URL", "http://localhost:8002")
DECISION_MODEL_URL = os.getenv("DECISION_MODEL_URL", "http://localhost:8003")

# 处理配置
MAX_RETRIES = 3
RETRY_INTERVAL = 2  # 秒
MAX_CLICK_DEPTH = 10  # 每个大学最多访问的页面数
REQUEST_TIMEOUT = 30  # HTTP请求超时时间（秒）
PAGE_LOAD_TIMEOUT = 10  # 页面加载超时时间（秒）

# 浏览器配置
BROWSER_HEADLESS = True
BROWSER_WIDTH = 1920
BROWSER_HEIGHT = 1080
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 决策模型配置
DEFAULT_PRIORITY_KEYWORDS = {
    "college": ["college", "university", "school", "education", "academic"],
    "academic": ["academic", "research", "faculty", "department", "program", "course"],
    "about": ["about", "overview", "history", "mission", "vision"],
    "admission": ["admission", "apply", "application", "enroll", "student"],
    "contact": ["contact", "address", "phone", "email", "location"]
}

# HTML解析配置
HTML_PARSER_CONFIG = {
    "extract_links": True,
    "extract_forms": True,
    "extract_images": True,
    "extract_text": True,
    "extract_navigation": True,
    "extract_contact_info": True,
    "extract_social_links": True,
    "extract_meta": True,
    "extract_structured_data": True
}

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 环境变量配置
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# API配置
API_RATE_LIMIT = 100  # 每分钟请求数限制
API_TIMEOUT = 30  # API超时时间

# 错误处理配置
MAX_ERROR_RETRIES = 3
ERROR_RETRY_DELAY = 5  # 秒

# 数据收集配置
COLLECT_EMAILS = True
COLLECT_PHONES = True
COLLECT_ADDRESSES = True
COLLECT_SOCIAL_LINKS = True
COLLECT_IMPORTANT_LINKS = True

# 过滤配置
SKIP_EXTERNAL_LINKS = True
SKIP_SOCIAL_MEDIA_LINKS = True
SKIP_LOGIN_LINKS = True
SKIP_FILE_DOWNLOADS = True

# 社交媒体域名列表
SOCIAL_MEDIA_DOMAINS = [
    "facebook.com", "twitter.com", "instagram.com", "linkedin.com",
    "youtube.com", "tiktok.com", "snapchat.com", "pinterest.com",
    "reddit.com", "tumblr.com", "flickr.com", "vimeo.com"
]

# 文件下载扩展名列表
FILE_EXTENSIONS = [
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".tar", ".gz", ".jpg", ".jpeg", ".png", ".gif",
    ".mp4", ".avi", ".mov", ".mp3", ".wav"
]

# 登录/注册关键词
LOGIN_KEYWORDS = [
    "login", "signin", "sign in", "log in", "register", "signup", "sign up",
    "create account", "join", "member", "portal", "dashboard"
]

# 重要页面关键词
IMPORTANT_PAGE_KEYWORDS = {
    "about": ["about", "about us", "overview", "history", "mission", "vision", "values"],
    "contact": ["contact", "contact us", "get in touch", "reach us", "location", "address"],
    "admission": ["admission", "admissions", "apply", "application", "how to apply", "requirements"],
    "academic": ["academics", "programs", "courses", "departments", "schools", "colleges"],
    "research": ["research", "innovation", "discovery", "labs", "centers"],
    "faculty": ["faculty", "staff", "professors", "teachers", "directory"],
    "student": ["students", "student life", "campus", "activities", "services"]
}

# 表单识别配置
SEARCH_FORM_INDICATORS = [
    "search", "find", "query", "lookup", "explore"
]

# 联系信息正则表达式
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_PATTERN = r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'
ADDRESS_KEYWORDS = [
    "address", "location", "street", "avenue", "road", "boulevard", "drive",
    "suite", "building", "floor", "room", "office", "campus"
]

# 性能配置
CONCURRENT_REQUESTS = 5  # 并发请求数
REQUEST_DELAY = 1  # 请求间隔（秒）
PAGE_PROCESSING_TIMEOUT = 60  # 页面处理超时（秒）

# 输出格式配置
OUTPUT_FORMAT = "json"  # json, csv, xlsx
INCLUDE_TIMESTAMPS = True
INCLUDE_METADATA = True

# 创建必要的目录
for directory in [DATA_DIR, INPUT_DIR, OUTPUT_DIR, TEST_DATA_DIR, LOG_DIR]:
    directory.mkdir(exist_ok=True)

# 验证配置
def validate_config():
    """
    验证配置的有效性
    """
    errors = []
    
    # 检查必要的目录
    if not UNIVERSITY_DATA_FILE.exists():
        errors.append(f"大学数据文件不存在: {UNIVERSITY_DATA_FILE}")
    
    # 检查URL格式
    urls = [SEARCH_MCP_URL, BROWSER_MCP_URL, HTML_PARSER_URL, DECISION_MODEL_URL]
    for url in urls:
        if not url.startswith(('http://', 'https://')):
            errors.append(f"无效的URL格式: {url}")
    
    # 检查数值配置
    if MAX_CLICK_DEPTH <= 0:
        errors.append("MAX_CLICK_DEPTH 必须大于0")
    
    if REQUEST_TIMEOUT <= 0:
        errors.append("REQUEST_TIMEOUT 必须大于0")
    
    if errors:
        raise ValueError("配置验证失败:\n" + "\n".join(errors))
    
    return True

# 获取配置摘要
def get_config_summary():
    """
    获取配置摘要信息
    """
    return {
        "environment": ENVIRONMENT,
        "debug": DEBUG,
        "mcp_servers": {
            "search": SEARCH_MCP_URL,
            "browser": BROWSER_MCP_URL,
            "html_parser": HTML_PARSER_URL,
            "decision_model": DECISION_MODEL_URL
        },
        "processing": {
            "max_click_depth": MAX_CLICK_DEPTH,
            "max_retries": MAX_RETRIES,
            "request_timeout": REQUEST_TIMEOUT
        },
        "data_paths": {
            "university_data": str(UNIVERSITY_DATA_FILE),
            "output_dir": str(OUTPUT_DIR),
            "logs_dir": str(LOG_DIR)
        }
    }

if __name__ == "__main__":
    # 验证配置
    try:
        validate_config()
        print("配置验证通过")
        
        # 打印配置摘要
        import json
        summary = get_config_summary()
        print("配置摘要:")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        
    except ValueError as e:
        print(f"配置验证失败: {e}")