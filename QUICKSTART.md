# 快速开始指南 (Quick Start Guide)

本指南将帮助您在5分钟内启动并运行高校内容收集系统。

## 🚀 一键启动

### 步骤1: 环境准备

确保您的系统已安装:
- Python 3.8 或更高版本
- pip 包管理器

### 步骤2: 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装Playwright浏览器
playwright install
```

### 步骤3: 启动系统

```bash
# 启动所有MCP服务器
python start_servers.py
```

等待所有服务器启动完成（约30秒），您将看到类似输出：
```
✅ 搜索MCP服务器启动成功 (PID: 1234, 端口: 8001)
✅ 浏览器MCP服务器启动成功 (PID: 1235, 端口: 8002)
✅ HTML解析MCP服务器启动成功 (PID: 1236, 端口: 8003)
✅ 决策模型MCP服务器启动成功 (PID: 1237, 端口: 8004)

🎉 所有MCP服务器启动完成!
```

### 步骤4: 运行演示

```bash
# 运行系统演示
python demo.py
```

演示将展示:
- 🔍 搜索QS500大学列表
- 🌐 自动浏览器导航
- 📄 HTML内容解析
- 🤖 智能决策制定
- 💾 数据收集和保存

## 🧪 验证安装

运行测试确保一切正常:

```bash
# 运行所有测试
python run_tests.py
```

如果看到 `✓ 所有测试通过!`，说明系统安装成功！

## 🎯 开始收集数据

### 方法1: 使用主控制器

```bash
# 启动完整的数据收集流程
python -c "from src.main_controller import MainController; import asyncio; asyncio.run(MainController().run())"
```

### 方法2: 自定义收集

```python
# 创建自定义脚本 my_collection.py
import asyncio
from src.main_controller import MainController

async def collect_specific_universities():
    controller = MainController()
    
    # 收集前10所大学的数据
    universities = await controller.get_university_list(0, 9)
    
    for university in universities:
        print(f"正在收集: {university['name']}")
        success = await controller.process_university(university)
        if success:
            print(f"✅ {university['name']} 收集完成")
        else:
            print(f"❌ {university['name']} 收集失败")
    
    await controller.cleanup()

if __name__ == "__main__":
    asyncio.run(collect_specific_universities())
```

然后运行:
```bash
python my_collection.py
```

## 📊 查看结果

收集的数据将保存在:
- `data/output/` - 结构化数据文件
- `logs/` - 详细日志文件

## 🔧 常用命令

### 服务器管理
```bash
# 检查服务器状态
python start_servers.py status

# 停止所有服务器
python start_servers.py stop all

# 重启所有服务器
python start_servers.py restart all

# 启动单个服务器
python start_servers.py start search
python start_servers.py start browser
python start_servers.py start html_parser
python start_servers.py start decision_model
```

### 测试命令
```bash
# 运行单元测试
python run_tests.py unit

# 运行集成测试
python run_tests.py integration

# 运行所有测试
python run_tests.py all
```

## 🌐 Web界面访问

启动服务器后，您可以通过浏览器访问各个服务的API文档:

- 搜索MCP服务器: http://localhost:8001/docs
- 浏览器MCP服务器: http://localhost:8002/docs
- HTML解析MCP服务器: http://localhost:8003/docs
- 决策模型MCP服务器: http://localhost:8004/docs

## ⚠️ 故障排除

### 问题1: 端口被占用
```bash
# 检查端口占用
netstat -ano | findstr :8001
netstat -ano | findstr :8002
netstat -ano | findstr :8003
netstat -ano | findstr :8004

# 杀死占用进程 (Windows)
taskkill /PID <PID> /F

# 杀死占用进程 (Linux/Mac)
kill -9 <PID>
```

### 问题2: 依赖安装失败
```bash
# 升级pip
python -m pip install --upgrade pip

# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### 问题3: Playwright浏览器安装失败
```bash
# 手动安装浏览器
playwright install chromium

# 如果网络问题，设置环境变量
set PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net
playwright install
```

### 问题4: 权限问题
```bash
# Windows: 以管理员身份运行命令提示符
# Linux/Mac: 使用sudo
sudo python start_servers.py
```

## 📞 获取帮助

如果遇到问题:

1. 查看 `logs/` 目录下的日志文件
2. 运行 `python run_tests.py` 检查系统状态
3. 查看完整文档: [README.md](README.md)
4. 检查配置文件: `src/config.py`

## 🎉 下一步

现在您已经成功启动了系统！接下来可以:

1. 📖 阅读完整的 [README.md](README.md) 了解更多功能
2. 🔧 修改 `src/config.py` 自定义配置
3. 🧪 编写自己的测试用例
4. 🚀 开始收集您感兴趣的大学数据

---

**提示**: 首次运行可能需要下载浏览器文件，请耐心等待。建议在稳定的网络环境下进行。