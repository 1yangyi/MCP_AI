import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

app = FastAPI(title="Browser MCP Server")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据模型
class NavigateRequest(BaseModel):
    url: str
    wait_time: Optional[int] = 3
    viewport_width: Optional[int] = 1280
    viewport_height: Optional[int] = 720
    ignore_https_errors: Optional[bool] = True
    wait_until: Optional[str] = "domcontentloaded"  # 新增：页面加载等待条件

class ClickRequest(BaseModel):
    selector: str
    wait_time: Optional[int] = 2

class FillRequest(BaseModel):
    selector: str
    value: str
    wait_time: Optional[int] = 1

class ScrollRequest(BaseModel):
    direction: str = "down"  # up, down, top, bottom
    pixels: Optional[int] = 500

class BrowserResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    html: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None

# 全局浏览器实例
browser: Optional[Browser] = None
context: Optional[BrowserContext] = None
page: Optional[Page] = None
playwright_instance = None

async def init_browser(ignore_https_errors: bool = True):
    """初始化浏览器"""
    global browser, context, page, playwright_instance
    
    try:
        if playwright_instance:
            await playwright_instance.stop()
            
        playwright_instance = await async_playwright().start()

        # 启动浏览器，增强忽略证书错误的选项
        launch_options = {
            "headless": False,
            "ignore_default_args": ["--enable-automation"],  # 隐藏自动化标志
            "args": [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-ipc-flooding-protection',
                '--disable-renderer-backgrounding',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-breakpad',
                '--disable-component-extensions-with-background-pages',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                '--disable-hang-monitor',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--disable-sync',
                '--disable-web-security',  # 禁用Web安全，有助于绕过某些限制
                '--disable-client-side-phishing-detection',
                '--disable-component-update',
                '--enable-unsafe-swiftshader',
                '--hide-scrollbars',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-default-browser-check',
                '--no-first-run',
                '--password-store=basic',
                '--use-mock-keychain',
                '--remote-debugging-port=0',
                '--ignore-certificate-errors',  # 忽略证书错误
                '--ignore-certificate-errors-spki-list',
                '--ignore-ssl-errors',
                '--allow-running-insecure-content',  # 允许不安全内容
                '--allow-insecure-localhost',  # 允许不安全的localhost
                '--disable-site-isolation-trials',  # 禁用站点隔离
            ],
        }

        browser = await playwright_instance.chromium.launch(**launch_options)
        
        # 创建上下文，增强忽略HTTPS错误的设置
        context_options = {
            "viewport": {'width': 1280, 'height': 720},
            "user_agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            "ignore_https_errors": ignore_https_errors,  # 忽略HTTPS错误
            "java_script_enabled": True,
            "bypass_csp": True,  # 绕过内容安全策略
            "accept_downloads": False,
        }
        
        context = await browser.new_context(**context_options)
        
        # 添加初始化脚本，绕过自动化检测
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en'],
            });
        """)
        
        page = await context.new_page()
        
        # 设置页面级别的忽略证书错误
        await page.route('**/*', lambda route: route.continue_())
        
        logger.info(f"浏览器初始化成功，ignore_https_errors={ignore_https_errors}")
        return True
    except Exception as e:
        logger.error(f"浏览器初始化失败: {e}")
        return False

async def cleanup_browser():
    """清理浏览器资源"""
    global browser, context, page, playwright_instance
    
    try:
        if page and not page.is_closed():
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright_instance:
            await playwright_instance.stop()
        
        browser = context = page = playwright_instance = None
        logger.info("浏览器资源清理完成")
    except Exception as e:
        logger.error(f"浏览器资源清理失败: {e}")

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化浏览器"""
    await init_browser(ignore_https_errors=True)

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await cleanup_browser()

@app.post("/navigate", response_model=BrowserResponse)
async def navigate_to_url(request: NavigateRequest):
    """导航到指定URL"""
    global page, context
    
    # 如果页面不存在或者需要重新初始化，则重新初始化浏览器
    if not page or page.is_closed():
        if not await init_browser(ignore_https_errors=request.ignore_https_errors):
            raise HTTPException(status_code=500, detail="浏览器初始化失败")
    
    try:
        # 设置视口大小
        await page.set_viewport_size({
            'width': request.viewport_width,
            'height': request.viewport_height
        })
        
        # 导航到URL，增强错误处理和等待条件
        navigation_options = {
            'wait_until': request.wait_until, 
            'timeout': 60000,
            'referer': None  # 不发送referer头
        }
        
        # 添加页面错误处理
        page_errors = []
        def handle_page_error(error):
            page_errors.append(error)
        
        page.on("pageerror", handle_page_error)
        
        # 执行导航
        response = await page.goto(request.url, **navigation_options)
        
        # 等待页面加载
        if request.wait_time > 0:
            await asyncio.sleep(request.wait_time)
        
        # 获取页面信息
        title = await page.title()
        url = page.url
        html = await page.content()
        
        # 检查页面状态
        status = "loaded"
        if response:
            status_code = response.status
            if status_code >= 400:
                status = f"http_error_{status_code}"
        else:
            status = "no_response"
        
        return BrowserResponse(
            message=f"成功导航到 {url}",
            data={
                "url": url,
                "title": title,
                "status": status,
                "status_code": status_code if response else None,
                "errors": page_errors
            },
            html=html,
            url=url,
            title=title
        )
        
    except Exception as e:
        logger.error(f"导航失败: {e}")
        
        # 尝试重新初始化浏览器并重试
        try:
            await cleanup_browser()
            await init_browser(ignore_https_errors=True)
            
            # 重新尝试导航
            await page.goto(request.url, wait_until=request.wait_until, timeout=60000)
            await asyncio.sleep(request.wait_time)
            
            title = await page.title()
            url = page.url
            html = await page.content()
            
            return BrowserResponse(
                message=f"通过重试成功导航到 {url}",
                data={
                    "url": url,
                    "title": title,
                    "loaded": True,
                    "retried": True
                },
                html=html,
                url=url,
                title=title
            )
            
        except Exception as retry_error:
            logger.error(f"重试导航也失败: {retry_error}")
            
            # 如果是证书错误，建议用户使用ignore_https_errors选项
            if any(error in str(e).lower() for error in ["certificate", "ssl", "https", "secure"]):
                error_msg = f"导航失败（证书错误）: {str(e)}。已自动重试但失败: {str(retry_error)}"
            else:
                error_msg = f"导航失败: {str(e)}，重试也失败: {str(retry_error)}"
            
            raise HTTPException(status_code=500, detail=error_msg)

@app.post("/click", response_model=BrowserResponse)
async def click_element(request: ClickRequest):
    """点击页面元素"""
    global page
    
    if not page or page.is_closed():
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        # 等待元素出现并可见
        await page.wait_for_selector(request.selector, state="visible", timeout=15000)
        
        # 点击元素，使用强制点击以防元素被遮挡
        await page.click(request.selector, force=True)
        
        # 等待页面响应
        await asyncio.sleep(request.wait_time)
        
        # 获取更新后的页面信息
        title = await page.title()
        url = page.url
        html = await page.content()
        
        return BrowserResponse(
            message=f"成功点击元素: {request.selector}",
            data={
                "selector": request.selector,
                "url": url,
                "title": title
            },
            html=html,
            url=url,
            title=title
        )
        
    except Exception as e:
        logger.error(f"点击失败: {e}")
        # 尝试使用JavaScript点击
        try:
            await page.evaluate(f"document.querySelector('{request.selector}').click()")
            await asyncio.sleep(request.wait_time)
            
            title = await page.title()
            url = page.url
            html = await page.content()
            
            return BrowserResponse(
                message=f"通过JavaScript成功点击元素: {request.selector}",
                data={
                    "selector": request.selector,
                    "url": url,
                    "title": title,
                    "method": "javascript"
                },
                html=html,
                url=url,
                title=title
            )
        except Exception as js_error:
            logger.error(f"JavaScript点击也失败: {js_error}")
            raise HTTPException(status_code=500, detail=f"点击失败: {str(e)}，JavaScript点击也失败: {str(js_error)}")

@app.post("/fill", response_model=BrowserResponse)
async def fill_input(request: FillRequest):
    """填充输入框"""
    global page
    
    if not page or page.is_closed():
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        # 等待元素出现
        await page.wait_for_selector(request.selector, timeout=10000)
        
        # 先点击输入框确保焦点
        await page.click(request.selector)
        await asyncio.sleep(0.5)
        
        # 清空并填充输入框
        await page.fill(request.selector, request.value)
        
        # 等待
        await asyncio.sleep(request.wait_time)
        
        return BrowserResponse(
            message=f"成功填充输入框: {request.selector}",
            data={
                "selector": request.selector,
                "value": request.value
            }
        )
        
    except Exception as e:
        logger.error(f"填充失败: {e}")
        raise HTTPException(status_code=500, detail=f"填充失败: {str(e)}")

@app.post("/scroll", response_model=BrowserResponse)
async def scroll_page(request: ScrollRequest):
    """滚动页面"""
    global page
    
    if not page or page.is_closed():
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        if request.direction == "down":
            await page.evaluate(f"window.scrollBy(0, {request.pixels})")
        elif request.direction == "up":
            await page.evaluate(f"window.scrollBy(0, -{request.pixels})")
        elif request.direction == "top":
            await page.evaluate("window.scrollTo(0, 0)")
        elif request.direction == "bottom":
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        else:
            # 自定义滚动到指定位置
            await page.evaluate(f"window.scrollTo(0, {request.pixels})")
        
        await asyncio.sleep(1)
        
        # 获取滚动位置
        scroll_position = await page.evaluate("""() => {
            return {
                x: window.scrollX,
                y: window.scrollY
            };
        }""")
        
        return BrowserResponse(
            message=f"页面滚动完成: {request.direction}",
            data={
                "direction": request.direction, 
                "pixels": request.pixels,
                "scroll_position": scroll_position
            }
        )
        
    except Exception as e:
        logger.error(f"滚动失败: {e}")
        raise HTTPException(status_code=500, detail=f"滚动失败: {str(e)}")

@app.get("/current_page", response_model=BrowserResponse)
async def get_current_page():
    """获取当前页面信息"""
    global page
    
    if not page or page.is_closed():
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        title = await page.title()
        url = page.url
        html = await page.content()
        
        # 获取更多页面信息
        page_info = await page.evaluate("""() => {
            return {
                url: window.location.href,
                title: document.title,
                readyState: document.readyState,
                cookieEnabled: navigator.cookieEnabled,
                userAgent: navigator.userAgent
            };
        }""")
        
        return BrowserResponse(
            message="获取当前页面信息成功",
            data={
                "url": url,
                "title": title,
                "html_length": len(html),
                "page_info": page_info
            },
            html=html,
            url=url,
            title=title
        )
        
    except Exception as e:
        logger.error(f"获取页面信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取页面信息失败: {str(e)}")

@app.post("/wait_for_element")
async def wait_for_element(selector: str, timeout: int = 15000, state: str = "visible"):
    """等待元素出现"""
    global page
    
    if not page or page.is_closed():
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        await page.wait_for_selector(selector, timeout=timeout, state=state)
        return BrowserResponse(
            message=f"元素已出现: {selector}",
            data={"selector": selector, "found": True, "state": state}
        )
    except Exception as e:
        logger.error(f"等待元素失败: {e}")
        raise HTTPException(status_code=500, detail=f"等待元素失败: {str(e)}")

@app.post("/screenshot")
async def take_screenshot(full_page: bool = False):
    """截取页面截图"""
    global page
    
    if not page or page.is_closed():
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        screenshot = await page.screenshot(full_page=full_page, type="jpeg", quality=80)
        import base64
        screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')
        
        return BrowserResponse(
            message="截图成功",
            data={
                "screenshot": screenshot_base64,
                "full_page": full_page,
                "format": "base64_jpeg"
            }
        )
    except Exception as e:
        logger.error(f"截图失败: {e}")
        raise HTTPException(status_code=500, detail=f"截图失败: {str(e)}")

@app.post("/evaluate_script")
async def evaluate_script(script: str):
    """执行JavaScript代码"""
    global page
    
    if not page or page.is_closed():
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        result = await page.evaluate(script)
        return BrowserResponse(
            message="JavaScript执行成功",
            data={"result": result}
        )
    except Exception as e:
        logger.error(f"JavaScript执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"JavaScript执行失败: {str(e)}")

@app.post("/restart_browser")
async def restart_browser(ignore_https_errors: bool = True):
    """重启浏览器"""
    await cleanup_browser()
    success = await init_browser(ignore_https_errors=ignore_https_errors)
    
    if success:
        return BrowserResponse(message="浏览器重启成功")
    else:
        raise HTTPException(status_code=500, detail="浏览器重启失败")

@app.get("/")
async def root():
    return {
        "message": "Browser MCP Server is running", 
        "browser_ready": page is not None and not page.is_closed()
    }

@app.get("/health")
async def health_check():
    """健康检查接口"""
    browser_status = "healthy" if browser and not browser.is_connected() else "unhealthy"
    page_status = "ready" if page and not page.is_closed() else "closed"
    
    return {
        "status": "healthy",
        "service": "Browser MCP Server",
        "browser_initialized": browser is not None,
        "browser_status": browser_status,
        "page_ready": page is not None,
        "page_status": page_status
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)