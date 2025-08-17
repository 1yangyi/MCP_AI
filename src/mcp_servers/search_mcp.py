import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import uvicorn
from pathlib import Path

app = FastAPI(title="Search MCP Server")

# 数据模型
class University(BaseModel):
    rank: int
    school: str
    website: str
    country: Optional[str] = None
    processed: bool = False

class UniversityResponse(BaseModel):
    universities: List[University]
    total: int
    status: str = "success"

class SingleUniversityResponse(BaseModel):
    university: Optional[University]
    status: str = "success"
    message: Optional[str] = None

# 全局变量存储大学数据
universities_data: List[University] = []

def load_universities_data():
    """加载大学数据"""
    global universities_data
    
    # 获取数据文件路径
    current_dir = Path(__file__).parent
    data_file = current_dir.parent.parent / "data" / "input" / "top500_school_websites.json"
    
    try:
        # 尝试多种编码格式
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']
        
        for encoding in encodings:
            try:
                with open(data_file, 'r', encoding=encoding) as f:
                    data = json.load(f)
                    universities_data = [University(**item) for item in data]
                    print(f"成功加载 {len(universities_data)} 所大学数据")
                    return
            except UnicodeDecodeError:
                continue
                
        raise Exception("无法使用任何编码格式读取文件")
        
    except Exception as e:
        print(f"加载大学数据失败: {e}")
        universities_data = []

@app.on_event("startup")
async def startup_event():
    """应用启动时加载数据"""
    load_universities_data()

@app.get("/universities", response_model=UniversityResponse)
async def get_all_universities():
    """获取所有大学列表"""
    return UniversityResponse(
        universities=universities_data,
        total=len(universities_data)
    )

@app.get("/universities/{university_id}", response_model=SingleUniversityResponse)
async def get_university_by_id(university_id: int):
    """根据ID获取单个大学信息"""
    if university_id < 1 or university_id > len(universities_data):
        raise HTTPException(status_code=404, detail="大学不存在")
    
    university = universities_data[university_id - 1]
    return SingleUniversityResponse(university=university)

@app.get("/universities/range/{start}/{end}", response_model=UniversityResponse)
async def get_universities_range(start: int, end: int):
    """获取指定范围的大学列表"""
    if start < 1 or end < start or start > len(universities_data):
        raise HTTPException(status_code=400, detail="无效的范围参数")
    
    # 调整索引（API使用1基索引，Python使用0基索引）
    start_idx = start - 1
    end_idx = min(end, len(universities_data))
    
    selected_universities = universities_data[start_idx:end_idx]
    
    return UniversityResponse(
        universities=selected_universities,
        total=len(selected_universities)
    )

@app.get("/universities/search/{school_name}", response_model=SingleUniversityResponse)
async def search_university_by_name(school_name: str):
    """根据学校名称搜索大学"""
    for university in universities_data:
        if school_name.lower() in university.school.lower():
            return SingleUniversityResponse(university=university)
    
    return SingleUniversityResponse(
        university=None,
        status="not_found",
        message=f"未找到名称包含 '{school_name}' 的大学"
    )

@app.put("/universities/{university_id}/processed")
async def mark_university_processed(university_id: int, processed: bool = True):
    """标记大学为已处理状态"""
    if university_id < 1 or university_id > len(universities_data):
        raise HTTPException(status_code=404, detail="大学不存在")
    
    universities_data[university_id - 1].processed = processed
    
    return {
        "status": "success",
        "message": f"大学 {universities_data[university_id - 1].school} 已标记为 {'已处理' if processed else '未处理'}"
    }

@app.get("/universities/stats")
async def get_processing_stats():
    """获取处理统计信息"""
    total = len(universities_data)
    processed = sum(1 for u in universities_data if u.processed)
    pending = total - processed
    
    return {
        "total": total,
        "processed": processed,
        "pending": pending,
        "progress_percentage": round((processed / total) * 100, 2) if total > 0 else 0
    }

@app.post("/universities/reload")
async def reload_universities_data():
    """重新加载大学数据"""
    load_universities_data()
    return {
        "status": "success",
        "message": f"已重新加载 {len(universities_data)} 所大学数据"
    }

@app.get("/")
async def root():
    return {"message": "Search MCP Server is running", "total_universities": len(universities_data)}

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "Search MCP Server",
        "universities_loaded": len(universities_data)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)