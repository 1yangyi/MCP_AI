import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

app = FastAPI(title="Browser MCP Server")

# python -m src.mcp_servers.browser

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据模型
class NavigateRequest(BaseModel):
    url: str
    wait_time: Optional[int] = 3
    viewport_width: Optional[int] = 1280
    viewport_height: Optional[int] = 720

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

async def init_browser():
    """初始化浏览器"""
    global browser, context, page, playwright_instance
    
    try:
        playwright_instance = await async_playwright().start()
        browser = await playwright_instance.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        page = await context.new_page()
        logger.info("浏览器初始化成功")
        return True
    except Exception as e:
        logger.error(f"浏览器初始化失败: {e}")
        return False

async def cleanup_browser():
    """清理浏览器资源"""
    global browser, context, page, playwright_instance
    
    try:
        if page:
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
    await init_browser()

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await cleanup_browser()

@app.post("/navigate", response_model=BrowserResponse)
async def navigate_to_url(request: NavigateRequest):
    """导航到指定URL"""
    global page
    
    if not page:
        if not await init_browser():
            raise HTTPException(status_code=500, detail="浏览器初始化失败")
    
    try:
        # 设置视口大小
        await page.set_viewport_size({
            'width': request.viewport_width,
            'height': request.viewport_height
        })
        
        # 导航到URL
        await page.goto(request.url, wait_until='domcontentloaded', timeout=60000)
        
        # 等待页面加载
        await asyncio.sleep(request.wait_time)
        
        # 获取页面信息
        title = await page.title()
        url = page.url
        html = await page.content()
        
        return BrowserResponse(
            message=f"成功导航到 {url}",
            data={
                "url": url,
                "title": title,
                "loaded": True
            },
            html=html,
            url=url,
            title=title
        )
        
    except Exception as e:
        logger.error(f"导航失败: {e}")
        raise HTTPException(status_code=500, detail=f"导航失败: {str(e)}")

@app.post("/click", response_model=BrowserResponse)
async def click_element(request: ClickRequest):
    """点击页面元素"""
    global page
    
    if not page:
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        # 等待元素出现
        await page.wait_for_selector(request.selector, timeout=10000)
        
        # 点击元素
        await page.click(request.selector)
        
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
        raise HTTPException(status_code=500, detail=f"点击失败: {str(e)}")

@app.post("/fill", response_model=BrowserResponse)
async def fill_input(request: FillRequest):
    """填充输入框"""
    global page
    
    if not page:
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        # 等待元素出现
        await page.wait_for_selector(request.selector, timeout=10000)
        
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
    
    if not page:
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
        
        await asyncio.sleep(1)
        
        return BrowserResponse(
            message=f"页面滚动完成: {request.direction}",
            data={"direction": request.direction, "pixels": request.pixels}
        )
        
    except Exception as e:
        logger.error(f"滚动失败: {e}")
        raise HTTPException(status_code=500, detail=f"滚动失败: {str(e)}")

@app.get("/current_page", response_model=BrowserResponse)
async def get_current_page():
    """获取当前页面信息"""
    global page
    
    if not page:
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        title = await page.title()
        url = page.url
        html = await page.content()
        
        return BrowserResponse(
            message="获取当前页面信息成功",
            data={
                "url": url,
                "title": title,
                "html_length": len(html)
            },
            html=html,
            url=url,
            title=title
        )
        
    except Exception as e:
        logger.error(f"获取页面信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取页面信息失败: {str(e)}")

@app.post("/wait_for_element")
async def wait_for_element(selector: str, timeout: int = 10000):
    """等待元素出现"""
    global page
    
    if not page:
        raise HTTPException(status_code=400, detail="浏览器未初始化或页面未加载")
    
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return BrowserResponse(
            message=f"元素已出现: {selector}",
            data={"selector": selector, "found": True}
        )
    except Exception as e:
        logger.error(f"等待元素失败: {e}")
        raise HTTPException(status_code=500, detail=f"等待元素失败: {str(e)}")

@app.post("/restart_browser")
async def restart_browser():
    """重启浏览器"""
    await cleanup_browser()
    success = await init_browser()
    
    if success:
        return BrowserResponse(message="浏览器重启成功")
    else:
        raise HTTPException(status_code=500, detail="浏览器重启失败")

@app.get("/")
async def root():
    return {"message": "Browser MCP Server is running", "browser_ready": page is not None}

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "Browser MCP Server",
        "browser_initialized": browser is not None,
        "page_ready": page is not None
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)




