# 高校内容收集系统 (University Data Collection System)

基于MCP (Model Context Protocol) 架构的智能化高校信息收集系统，能够自动化地从QS世界大学排名前500的高校官网收集结构化数据。

## 📋 需求 (Requirements)

本系统的核心需求是：
- **爬取世界500大学的二级学院信息**

通过智能化的网页解析和交互，系统能够自动识别并提取各大学官网上的二级学院结构、名称、简介等关键信息，形成结构化数据，为高校研究和分析提供基础数据支持。

## 🏗️ 系统架构

本系统采用微服务架构，由4个独立的MCP服务器组成：

```
┌───打开帝国理工学院官网，地址为：'https://www.imperial.ac.uk/'，找到并提取所有二级学院信息，包括学院名称、官网链接，将数据直接以Json格式保存在本地，文件名为帝国理工学院_colleges.json。注意：不要使用python脚本来用于抓取并生成 JSON 文件，而是直接将你从网页里看到的二级学院信息进行保存。'武汉大学_colleges.json'是一个正确的例子
──────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   搜索MCP服务器   │    │  浏览器MCP服务器  │    │ HTML解析MCP服务器 │    │ 决策模型MCP服务器 │
│   (Search MCP)  │    │ (Browser MCP)   │    │(HTML Parser MCP)│    │(Decision Model) │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • QS500大学列表  │    │ • 网页导航       │    │ • HTML内容解析   │    │ • 智能决策制定   │
│ • 大学信息检索   │    │ • 页面交互       │    │ • 结构化数据提取 │    │ • 下一步动作推荐 │
│ • 数据过滤      │    │ • 内容获取       │    │ • 链接和表单识别 │    │ • 优先级评估     │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │    主控制器         │
                        │ (Main Controller)   │
                        ├─────────────────────┤
                        │ • 流程协调          │
                        │ • 任务调度          │
                        │ • 数据收集          │
                        │ • 结果保存          │
                        └─────────────────────┘
```

## 🚀 核心功能

### 1. 搜索MCP服务器 (端口: 8001)
- **大学列表管理**: 维护QS世界大学排名前500的完整列表
- **智能搜索**: 支持按名称、排名、地区等条件搜索大学
- **数据过滤**: 提供灵活的过滤和分页功能

### 2. 浏览器MCP服务器 (端口: 8002) --- click
- **自动化浏览**: 基于Playwright的无头浏览器控制
- **页面交互**: 支持点击、填表、导航等操作
- **内容获取**: 实时获取页面HTML内容和元数据

### 3. HTML解析MCP服务器 (端口: 8003) -----MCP parser
- **智能解析**: 使用BeautifulSoup进行深度HTML解析
- **结构化提取**: 自动识别和提取链接、表单、按钮等元素
- **内容清理**: 过滤无关内容，提取有价值信息

### 4. 决策模型MCP服务器 (端口: 8004)
- **智能决策**: 基于页面内容和上下文制定下一步行动
- **优先级评估**: 对不同操作进行置信度和优先级评分
- **自适应策略**: 根据网站结构动态调整收集策略

## 📦 安装指南

### 环境要求
- Python 3.8+
- Windows/Linux/macOS
- 至少4GB可用内存

### 1. 克隆项目
```bash
git clone <repository-url>
cd browserMCP
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 安装Playwright浏览器
```bash
playwright install
```

### 4. 创建必要目录
```bash
mkdir -p data/input data/output data/test logs
```

## 🎯 使用指南

### 快速启动

1. **启动所有MCP服务器**:
```bash
python start_servers.py
```

2. **运行演示**:
```bash
python demo.py
```

3. **运行测试**:
```bash
python run_tests.py
```

### 详细使用

#### 1. 启动服务器
```bash
# 启动所有服务器
python start_servers.py start all

# 启动单个服务器
python start_servers.py start search
python start_servers.py start browser
python start_servers.py start html_parser
python start_servers.py start decision_model

# 检查服务器状态
python start_servers.py status

# 停止所有服务器
python start_servers.py stop all
```

#### 2. 运行主程序
```bash
# 使用主控制器收集数据
python -c "from src.main_controller import MainController; import asyncio; asyncio.run(MainController().run())"
```

#### 3. 测试系统
```bash
# 运行所有测试
python run_tests.py all

# 只运行单元测试
python run_tests.py unit

# 只运行集成测试
python run_tests.py integration
```

## 📊 API文档

### 搜索MCP服务器 API

#### 获取大学列表
```http
GET /universities/range?start=0&end=10
```

#### 搜索大学
```http
GET /search?name=MIT&country=US
```

#### 健康检查
```http
GET /health
```

### 浏览器MCP服务器 API

#### 导航到URL
```http
POST /navigate
Content-Type: application/json

{
  "url": "https://example.com",
  "wait_time": 3
}
```

#### 获取HTML内容
```http
GET /get_html
```

#### 点击元素
```http
POST /click
Content-Type: application/json

{
  "selector": "a[href='/about']"
}
```

### HTML解析MCP服务器 API

#### 解析HTML
```http
POST /parse_html
Content-Type: application/json

{
  "html": "<html>...</html>",
  "url": "https://example.com",
  "extract_links": true,
  "extract_forms": true,
  "extract_text": true
}
```

### 决策模型MCP服务器 API

#### 制定决策
```http
POST /decide
Content-Type: application/json

{
  "university": {
    "name": "MIT",
    "website": "https://web.mit.edu",
    "rank": 1
  },
  "current_page": {
    "url": "https://web.mit.edu",
    "title": "MIT",
    "links": [...],
    "buttons": [...],
    "forms": [...]
  },
  "visited_pages": [],
  "page_count": 0
}
```

#### 获取关键词配置
```http
GET /keywords
```

## 🔧 配置说明

主要配置文件: `src/config.py`

### 服务器配置
```python
# MCP服务器URL
SEARCH_MCP_URL = "http://localhost:8001"
BROWSER_MCP_URL = "http://localhost:8002"
HTML_PARSER_URL = "http://localhost:8003"
DECISION_MODEL_URL = "http://localhost:8004"
```

### 处理配置
```python
# 处理限制
MAX_RETRIES = 3
RETRY_INTERVAL = 5
MAX_CLICK_DEPTH = 10
REQUEST_TIMEOUT = 30
```

### 浏览器配置
```python
# 浏览器设置
BROWSER_CONFIG = {
    "headless": True,
    "timeout": 30000,
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

## 📁 项目结构

```
browserMCP/
├── src/                          # 源代码目录
│   ├── mcp_servers/             # MCP服务器实现
│   │   ├── search_mcp.py        # 搜索MCP服务器
│   │   ├── browser_mcp.py       # 浏览器MCP服务器
│   │   ├── html_parser_mcp.py   # HTML解析MCP服务器
│   │   └── decision_model_mcp.py # 决策模型MCP服务器
│   ├── main_controller.py       # 主控制器
│   └── config.py               # 配置文件
├── tests/                       # 测试用例
│   └── test_mcp_servers.py     # MCP服务器测试
├── data/                        # 数据目录
│   ├── input/                  # 输入数据
│   ├── output/                 # 输出数据
│   └── test/                   # 测试数据
├── logs/                        # 日志目录
├── start_servers.py            # 服务器启动脚本
├── run_tests.py               # 测试运行脚本
├── demo.py                    # 演示脚本
├── requirements.txt           # Python依赖
└── README.md                  # 项目文档
```

## 🧪 测试

### 测试覆盖范围
- **单元测试**: 各MCP服务器的独立功能测试
- **集成测试**: 服务器间协作和完整流程测试
- **健康检查**: 所有服务器的状态监控

### 运行测试
```bash
# 运行所有测试
python run_tests.py

# 运行特定类型测试
python run_tests.py unit        # 单元测试
python run_tests.py integration # 集成测试
```

## 📝 日志

系统会在 `logs/` 目录下生成详细的日志文件：
- `search_mcp.log` - 搜索服务器日志
- `browser_mcp.log` - 浏览器服务器日志
- `html_parser_mcp.log` - HTML解析服务器日志
- `decision_model.log` - 决策模型服务器日志
- `main_controller.log` - 主控制器日志

## 🔍 故障排除

### 常见问题

1. **服务器启动失败**
   - 检查端口是否被占用
   - 确认Python依赖已正确安装
   - 查看相应的日志文件

2. **浏览器操作失败**
   - 确认Playwright浏览器已安装: `playwright install`
   - 检查网络连接
   - 查看browser_mcp.log日志

3. **测试失败**
   - 确保所有MCP服务器正在运行
   - 检查网络连接
   - 查看测试输出和日志文件

### 调试模式

启用详细日志输出：
```python
# 在config.py中设置
LOGGING_CONFIG = {
    "level": "DEBUG",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的Web框架
- [Playwright](https://playwright.dev/) - 现代浏览器自动化
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML解析库
- [Pydantic](https://pydantic-docs.helpmanual.io/) - 数据验证库

---

**注意**: 使用本系统时请遵守目标网站的robots.txt和使用条款，合理控制请求频率，避免对目标服务器造成过大负担。