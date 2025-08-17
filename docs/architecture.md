# 项目架构设计文档

## 概述

基于demand.md的需求，重新设计大学数据收集系统，采用模块化的MCP服务器架构，实现循环处理机制。

## 系统架构

### 核心组件

1. **搜索MCP服务器** (Search MCP)
2. **浏览器MCP服务器** (Browser MCP - Playwright)
3. **HTML解析MCP服务器** (HTML Parser MCP)
4. **决策模型MCP服务器** (Decision Model MCP)
5. **主控制器** (Main Controller)

### 数据流程

```
搜索MCP → 浏览器MCP → HTML解析MCP → 决策模型MCP
    ↓           ↑              ↑              ↓
大学列表    ←─── 循环处理机制 ────────────────────┘
```

## 模块详细设计

### 1. 搜索MCP服务器 (端口: 8000)

**职责:**
- 管理QS500大学名单数据
- 提供大学信息查询接口
- 支持批量和单个大学数据获取

**API接口:**
- `GET /universities` - 获取所有大学列表
- `GET /universities/{id}` - 获取单个大学信息
- `GET /universities/range/{start}/{end}` - 获取指定范围大学

**数据格式:**
```json
{
  "rank": 1,
  "school": "麻省理工学院",
  "website": "http://web.mit.edu/",
  "country": "美国",
  "processed": false
}
```

### 2. 浏览器MCP服务器 (端口: 8002)

**职责:**
- 网页导航和HTML获取
- 执行点击、填写表单等交互操作
- 管理浏览器会话状态
- 支持页面前进、后退操作

**API接口:**
- `POST /navigate` - 导航到指定URL
- `POST /click` - 点击页面元素
- `POST /fill_form` - 填写表单
- `POST /get_html` - 获取当前页面HTML
- `POST /go_back` - 返回上一页
- `POST /close` - 关闭浏览器会话

### 3. HTML解析MCP服务器 (端口: 8080)

**职责:**
- 解析HTML内容为结构化JSON
- 提取页面关键信息（链接、按钮、表单等）
- 支持重复调用和循环处理

**API接口:**
- `POST /parse_html` - 解析HTML内容

**输出格式:**
```json
{
  "title": "页面标题",
  "links": [{"text": "链接文本", "href": "链接地址", "selector": "CSS选择器"}],
  "buttons": [{"text": "按钮文本", "selector": "CSS选择器"}],
  "forms": [{"action": "表单提交地址", "fields": [...]}],
  "navigation": [...],
  "text_blocks": [...]
}
```

### 4. 决策模型MCP服务器 (端口: 8001)

**职责:**
- 基于解析的JSON数据做出决策
- 确定下一步交互操作
- 支持多种决策策略

**API接口:**
- `POST /decide` - 做出下一步操作决策

**决策输出:**
```json
{
  "action": "click_link|click_button|fill_form|stop",
  "target": {
    "selector": "CSS选择器",
    "href": "链接地址",
    "text": "目标文本"
  },
  "reason": "决策理由"
}
```

### 5. 主控制器

**职责:**
- 协调各MCP服务器的工作
- 实现循环处理机制
- 管理处理状态和错误处理
- 数据持久化

**核心流程:**
1. 从搜索MCP获取大学列表
2. 对每个大学执行处理循环:
   - 浏览器MCP打开网站
   - HTML解析MCP解析页面
   - 决策模型MCP决定下一步
   - 浏览器MCP执行操作
   - 重复步骤2-4直到完成或失败
3. 保存处理结果

## 技术规范

### 通信协议
- 所有MCP服务器使用HTTP REST API
- 数据格式统一使用JSON
- 支持异步处理和超时控制

### 错误处理
- 统一错误码和错误信息格式
- 支持重试机制
- 详细的日志记录

### 配置管理
- 集中化配置文件
- 支持环境变量覆盖
- 动态配置更新

## 部署架构

### 开发环境
- 所有服务运行在本地不同端口
- 使用本地文件系统存储数据

### 生产环境
- 支持Docker容器化部署
- 服务发现和负载均衡
- 分布式数据存储

## 扩展性设计

- 插件化决策策略
- 可配置的解析规则
- 支持多种浏览器引擎
- 水平扩展能力