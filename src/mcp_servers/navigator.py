import json
import logging
import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
import uvicorn

# 导入增强版askAI模块
from askAI_enhanced import make_decision_with_ai

app = FastAPI(
    title="AI Decision MCP Server",
    description="基于外部AI的智能决策模型，用于大学网站内容收集",
    version="1.0"
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/ai_decision.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ai_decision")

# 获取API密钥
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    logger.warning("未设置DEEPSEEK_API_KEY环境变量，AI决策功能将无法正常工作")

# 数据模型（与原决策模型保持兼容）
class UniversityInfo(BaseModel):
    """大学信息模型"""
    rank: int = Field(..., description="QS排名")
    name: str = Field(..., description="大学名称")
    website: str = Field(..., description="大学官网URL")
    processed: bool = Field(default=False, description="是否已处理")

class PageContent(BaseModel):
    """页面内容模型"""
    url: str = Field(..., description="页面URL")
    title: Optional[str] = Field(None, description="页面标题")
    meta_description: Optional[str] = Field(None, description="页面描述")
    headings: List[Dict[str, Any]] = Field(default_factory=list, description="标题列表")
    links: List[Dict[str, Any]] = Field(default_factory=list, description="链接列表")
    buttons: List[Dict[str, Any]] = Field(default_factory=list, description="按钮列表")
    forms: List[Dict[str, Any]] = Field(default_factory=list, description="表单列表")
    images: List[Dict[str, Any]] = Field(default_factory=list, description="图片列表")
    text_blocks: List[str] = Field(default_factory=list, description="文本块列表")
    navigation: List[Dict[str, Any]] = Field(default_factory=list, description="导航菜单")
    contact_info: Dict[str, List[str]] = Field(default_factory=dict, description="联系信息")
    social_links: List[Dict[str, str]] = Field(default_factory=list, description="社交媒体链接")
    processing_time: float = Field(default=0.0, description="处理时间")

class DecisionRequest(BaseModel):
    """决策请求模型"""
    university: UniversityInfo = Field(..., description="大学信息")
    current_page: PageContent = Field(..., description="当前页面内容")
    visited_pages: List[str] = Field(..., description="已访问页面URL列表")
    page_count: int = Field(..., description="已访问页面数量")
    max_pages: int = Field(default=10, description="最大页面访问数量")
    priority_keywords: List[str] = Field(default_factory=list, description="优先关键词")

class Target(BaseModel):
    """操作目标模型"""
    selector: Optional[str] = Field(None, description="CSS选择器")
    href: Optional[str] = Field(None, description="链接地址")
    text: Optional[str] = Field(None, description="文本内容")
    form_selector: Optional[str] = Field(None, description="表单选择器")
    form_data: Optional[Dict[str, str]] = Field(None, description="表单数据")
    confidence: float = Field(default=0.0, description="置信度")

class DecisionResponse(BaseModel):
    """决策响应模型"""
    action: str = Field(..., description="操作类型: click_link, click_button, fill_form, scroll, wait, stop")
    target: Optional[Target] = Field(None, description="操作目标")
    reason: str = Field(..., description="决策原因")
    confidence: float = Field(default=0.0, description="决策置信度")
    priority: int = Field(default=0, description="优先级")
    timestamp: datetime = Field(default_factory=datetime.now, description="决策时间")

@app.post("/decide", response_model=DecisionResponse)
async def decide(request: DecisionRequest):
    """
    基于当前页面内容和上下文，使用外部AI做出智能决策
    """
    try:
        logger.info(f"开始AI决策分析 - 大学: {request.university.name}, 页面: {request.current_page.url}")
        
        if not DEEPSEEK_API_KEY:
            logger.error("未设置DEEPSEEK_API_KEY环境变量，无法使用AI决策")
            return DecisionResponse(
                action="stop",
                reason="系统配置错误：未设置AI API密钥",
                confidence=0.0,
                priority=0
            )
        
        # 调用外部AI进行决策
        ai_decision = make_decision_with_ai(
            api_key=DEEPSEEK_API_KEY,
            page_content=request.current_page.dict(),
            university_info=request.university.dict(),
            visited_pages=request.visited_pages,
            page_count=request.page_count,
            max_pages=request.max_pages
        )
        
        # 构建响应
        target_data = ai_decision.get("target", {})
        target = Target(**target_data) if target_data else None
        
        decision = DecisionResponse(
            action=ai_decision.get("action", "stop"),
            target=target,
            reason=ai_decision.get("reason", "AI决策"),
            confidence=ai_decision.get("confidence", 0.5),
            priority=0  # 优先级固定为0
        )
        
        logger.info(f"AI决策结果: {decision.action} - {decision.reason}")
        return decision
        
    except Exception as e:
        logger.error(f"AI决策过程出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI决策过程出错: {str(e)}")

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "AI Decision MCP Server"}

if __name__ == "__main__":
    print("启动AI决策MCP服务器...")
    uvicorn.run(app, host="0.0.0.0", port=8001)