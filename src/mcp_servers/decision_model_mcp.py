import json
import logging
import re
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union
import uvicorn

app = FastAPI(
    title="Decision Model MCP Server",
    description="基于LLM的智能决策模型，用于大学网站内容收集",
    version="2.0"
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/decision_model.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("decision_model")

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
    基于当前页面内容和上下文做出智能决策
    """
    try:
        logger.info(f"开始决策分析 - 大学: {request.university.name}, 页面: {request.current_page.url}")
        
        # 分析当前页面，决定下一步操作
        decision = make_decision(
            current_page=request.current_page,
            university=request.university,
            visited_pages=request.visited_pages,
            page_count=request.page_count,
            max_pages=request.max_pages,
            priority_keywords=request.priority_keywords
        )
        
        logger.info(f"决策结果: {decision.action} - {decision.reason}")
        return decision
        
    except Exception as e:
        logger.error(f"决策过程出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"决策过程出错: {str(e)}")

def make_decision(current_page: PageContent, university: UniversityInfo, 
                 visited_pages: List[str], page_count: int, max_pages: int = 10,
                 priority_keywords: List[str] = None) -> DecisionResponse:
    """
    基于当前页面内容和上下文做出智能决策
    """
    # 如果已经访问了足够多的页面，停止
    if page_count >= max_pages:
        return DecisionResponse(
            action="stop",
            reason=f"已达到最大页面访问数量({max_pages})",
            confidence=1.0,
            priority=0
        )
    
    # 提取当前页面的关键信息
    title = current_page.title or ""
    links = current_page.links or []
    buttons = current_page.buttons or []
    forms = current_page.forms or []
    headings = current_page.headings or []
    navigation = current_page.navigation or []
    
    # 定义关键词优先级（从高到低）
    college_keywords = ["college", "学院", "school", "faculty", "department", "院系", "系", "部门", 
                       "engineering", "工程", "business", "商学", "medicine", "医学", "law", "法学",
                       "arts", "文学", "science", "理学", "education", "教育", "graduate", "研究生"]
    
    academic_keywords = ["academic", "学术", "research", "研究", "program", "项目", "course", "课程",
                        "degree", "学位", "major", "专业", "curriculum", "课程设置"]
    
    about_keywords = ["about", "关于", "overview", "概述", "history", "历史", "mission", "使命",
                     "vision", "愿景", "profile", "简介"]
    
    admission_keywords = ["admission", "招生", "apply", "申请", "enrollment", "入学", "requirement", "要求",
                         "application", "申请表", "tuition", "学费"]
    
    contact_keywords = ["contact", "联系", "address", "地址", "phone", "电话", "email", "邮箱",
                       "location", "位置", "directory", "目录"]
    
    # 优先级顺序：二级学院 > 学术 > 关于 > 招生 > 联系方式
    priority_keywords_list = [college_keywords, academic_keywords, about_keywords, admission_keywords, contact_keywords]
    
    # 如果用户提供了自定义优先关键词，优先使用
    if priority_keywords:
        priority_keywords_list.insert(0, priority_keywords)
    
    # 首先检查是否有搜索表单，如果有，可以考虑搜索大学相关信息
    search_form = find_search_form(forms)
    if search_form and page_count < 2:  # 只在前几个页面尝试搜索
        search_term = university.name.split()[0]  # 使用大学名称的第一个词作为搜索词
        return DecisionResponse(
            action="fill_form",
            target=Target(
                form_selector=f"form#{search_form.get('id')}" if search_form.get('id') else "form",
                form_data={
                    f"input[name='{search_form.get('inputs', [{}])[0].get('name')}']" if search_form.get('inputs') and search_form['inputs'][0].get('name') else "input[type='text']": search_term
                },
                confidence=0.8
            ),
            reason=f"搜索大学相关信息: {search_term}",
            confidence=0.8,
            priority=5
        )
    
    # 按优先级检查链接
    for priority_level, keywords in enumerate(priority_keywords_list):
        # 首先检查导航链接
        for nav in navigation:
            for link in nav.get("links", []):
                link_text = link.get("text", "").lower()
                link_href = link.get("href", "").lower()
                
                # 检查链接文本和URL是否包含关键词
                if any(keyword.lower() in link_text or keyword.lower() in link_href for keyword in keywords):
                    # 检查是否已访问过
                    if link.get("href") not in visited_pages:
                        confidence = calculate_link_confidence(link, keywords)
                        return DecisionResponse(
                            action="click_link",
                            target=Target(
                                selector=f"a[href='{link.get('href')}']" if link.get("href") else f"a:contains('{link.get('text')}')",
                                href=link.get("href"),
                                text=link.get("text"),
                                confidence=confidence
                            ),
                            reason=f"导航到相关页面: {link.get('text')}",
                            confidence=confidence,
                            priority=10 - priority_level
                        )
        
        # 然后检查普通链接
        for link in links:
            link_text = link.get("text", "").lower()
            link_href = link.get("href", "").lower()
            
            # 检查链接文本和URL是否包含关键词
            if any(keyword.lower() in link_text or keyword.lower() in link_href for keyword in keywords):
                # 检查是否已访问过
                if link.get("href") not in visited_pages:
                    confidence = calculate_link_confidence(link, keywords)
                    return DecisionResponse(
                        action="click_link",
                        target=Target(
                            selector=f"a[href='{link.get('href')}']" if link.get("href") else f"a:contains('{link.get('text')}')",
                            href=link.get("href"),
                            text=link.get("text"),
                            confidence=confidence
                        ),
                        reason=f"导航到相关页面: {link.get('text')}",
                        confidence=confidence,
                        priority=10 - priority_level
                    )
    
    # 如果没有找到优先级高的链接，尝试查找任何看起来有用的链接
    for link in links:
        # 跳过已访问的链接
        if link.get("href") in visited_pages:
            continue
            
        # 跳过外部链接
        if link.get("href") and (link.get("href").startswith("http") and university.website not in link.get("href")):
            continue
            
        # 跳过不相关的链接
        if should_skip_link(link):
            continue
            
        # 如果链接看起来有用，点击它
        confidence = 0.3  # 备选链接的置信度较低
        return DecisionResponse(
            action="click_link",
            target=Target(
                selector=f"a[href='{link.get('href')}']" if link.get("href") else f"a:contains('{link.get('text')}')",
                href=link.get("href"),
                text=link.get("text"),
                confidence=confidence
            ),
            reason=f"探索页面: {link.get('text')}",
            confidence=confidence,
            priority=1
        )
    
    # 如果没有找到有用的链接，尝试点击按钮
    for button in buttons:
        if should_skip_button(button):
            continue
            
        # 如果按钮看起来有用，点击它
        confidence = 0.4
        return DecisionResponse(
            action="click_button",
            target=Target(
                selector=f"button:contains('{button.get('text')}')",
                text=button.get("text"),
                confidence=confidence
            ),
            reason=f"点击按钮: {button.get('text')}",
            confidence=confidence,
            priority=1
        )
    
    # 如果没有找到任何有用的交互元素，停止
    return DecisionResponse(
        action="stop",
        reason="没有找到有用的交互元素",
        confidence=1.0,
        priority=0
    )

def calculate_link_confidence(link: Dict[str, Any], keywords: List[str]) -> float:
    """
    计算链接的置信度
    """
    confidence = 0.5
    link_text = link.get("text", "").lower()
    link_href = link.get("href", "").lower()
    
    # 基于关键词匹配数量增加置信度
    matched_keywords = sum(1 for keyword in keywords if keyword.lower() in link_text or keyword.lower() in link_href)
    confidence += matched_keywords * 0.2
    
    # 基于链接位置增加置信度（导航链接通常更重要）
    if "nav" in link.get("parent_tag", "").lower():
        confidence += 0.1
    
    return min(confidence, 1.0)

def should_skip_link(link: Dict[str, Any]) -> bool:
    """
    判断是否应该跳过某个链接
    """
    link_text = link.get("text", "").lower()
    link_href = link.get("href", "").lower()
    
    # 跳过社交媒体链接
    social_media = ["facebook", "twitter", "instagram", "linkedin", "youtube", "weibo", "wechat"]
    if any(sm in link_href for sm in social_media):
        return True
    
    # 跳过登录、注册链接
    skip_keywords = ["login", "登录", "sign in", "signin", "register", "注册", "logout", "退出"]
    if any(keyword in link_text for keyword in skip_keywords):
        return True
    
    # 跳过文件下载链接
    file_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar"]
    if any(ext in link_href for ext in file_extensions):
        return True
    
    # 跳过邮件链接
    if link_href.startswith("mailto:"):
        return True
    
    return False

def should_skip_button(button: Dict[str, Any]) -> bool:
    """
    判断是否应该跳过某个按钮
    """
    button_text = button.get("text", "").lower()
    
    # 跳过登录、注册按钮
    skip_keywords = ["login", "登录", "sign in", "signin", "register", "注册", "logout", "退出", "submit", "提交"]
    if any(keyword in button_text for keyword in skip_keywords):
        return True
    
    return False

def find_search_form(forms: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    查找搜索表单
    """
    for form in forms:
        # 检查表单是否有搜索相关的特征
        form_id = form.get("id", "").lower()
        form_classes = " ".join(form.get("classes", [])).lower()
        
        # 检查表单ID或类是否包含搜索相关关键词
        if "search" in form_id or "search" in form_classes:
            return form
        
        # 检查表单是否有搜索输入框
        for input_field in form.get("inputs", []):
            input_name = input_field.get("name", "").lower()
            input_id = input_field.get("id", "").lower()
            input_placeholder = input_field.get("placeholder", "").lower()
            input_type = input_field.get("type", "").lower()
            
            # 检查输入框是否是搜索框
            if (input_type == "text" or input_type == "search") and \
               ("search" in input_name or "search" in input_id or "search" in input_placeholder):
                return form
    
    return None

@app.get("/")
async def root():
    return {
        "message": "Decision Model MCP Server is running",
        "version": "2.0",
        "description": "基于LLM的智能决策模型，用于大学网站内容收集"
    }

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "Decision Model MCP Server",
        "version": "2.0",
        "features": [
            "intelligent_decision_making",
            "priority_based_navigation",
            "link_confidence_scoring",
            "form_detection",
            "content_filtering",
            "university_focused_crawling"
        ],
        "supported_actions": [
            "click_link",
            "click_button",
            "fill_form",
            "scroll",
            "wait",
            "stop"
        ]
    }

@app.get("/keywords")
async def get_default_keywords():
    """获取默认关键词配置"""
    return {
        "college_keywords": ["college", "学院", "school", "faculty", "department", "院系", "系", "部门", 
                           "engineering", "工程", "business", "商学", "medicine", "医学", "law", "法学",
                           "arts", "文学", "science", "理学", "education", "教育", "graduate", "研究生"],
        "academic_keywords": ["academic", "学术", "research", "研究", "program", "项目", "course", "课程",
                             "degree", "学位", "major", "专业", "curriculum", "课程设置"],
        "about_keywords": ["about", "关于", "overview", "概述", "history", "历史", "mission", "使命",
                          "vision", "愿景", "profile", "简介"],
        "admission_keywords": ["admission", "招生", "apply", "申请", "enrollment", "入学", "requirement", "要求",
                              "application", "申请表", "tuition", "学费"],
        "contact_keywords": ["contact", "联系", "address", "地址", "phone", "电话", "email", "邮箱",
                            "location", "位置", "directory", "目录"]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)