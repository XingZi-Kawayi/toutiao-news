from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from config.config import get_db
from utils.ai_service import ai_service, LLMAuthError, LLMRateLimitError, LLMServiceError
from utils.auth import get_current_user
from models.users import User
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/ai", tags=["AI 服务"])


class SummaryRequest(BaseModel):
    content: str = Field(..., description="新闻内容", max_length=10000)
    max_length: int = Field(default=200, description="摘要最大字数", ge=50, le=500)


class SummaryResponse(BaseModel):
    summary: str
    original_length: int
    summary_length: int


class ChatRequest(BaseModel):
    messages: List[dict] = Field(..., description="对话消息列表")


class ChatResponse(BaseModel):
    response: str


class KeywordsRequest(BaseModel):
    content: str = Field(..., description="文本内容", max_length=10000)
    top_k: int = Field(default=5, description="关键词数量", ge=1, le=20)


class KeywordsResponse(BaseModel):
    keywords: List[str]


def handle_llm_error(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except LLMAuthError:
            logger.error("LLM authentication error")
            raise HTTPException(
                status_code=500,
                detail="AI 服务配置错误，请联系管理员"
            )
        except LLMRateLimitError:
            logger.warning("LLM rate limit exceeded")
            raise HTTPException(
                status_code=429,
                detail="请求过于频繁，请稍后再试"
            )
        except LLMServiceError as e:
            logger.error(f"LLM service error: {e}")
            raise HTTPException(
                status_code=503,
                detail="AI 服务暂时不可用，请稍后重试"
            )
        except Exception as e:
            logger.error(f"Unexpected error in LLM call: {e}")
            raise HTTPException(
                status_code=500,
                detail="生成失败，请稍后重试"
            )
    return wrapper


@router.post("/summary")
@handle_llm_error
async def generate_summary(
    request: SummaryRequest,
    db: AsyncSession = Depends(get_db)
):
    """生成新闻摘要"""
    summary = await ai_service.generate_summary(request.content, request.max_length)
    
    if not summary:
        raise HTTPException(status_code=500, detail="生成摘要失败，请稍后重试")
    
    return {
        "code": 200,
        "message": "生成摘要成功",
        "data": {
            "summary": summary,
            "original_length": len(request.content),
            "summary_length": len(summary)
        }
    }


@router.post("/chat")
@handle_llm_error
async def ai_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """AI 对话"""
    response = await ai_service.chat(request.messages)
    
    if not response:
        raise HTTPException(status_code=500, detail="AI 响应失败，请稍后重试")
    
    return {
        "code": 200,
        "message": "success",
        "data": {
            "response": response
        }
    }


@router.post("/keywords")
@handle_llm_error
async def extract_keywords(
    request: KeywordsRequest,
    db: AsyncSession = Depends(get_db)
):
    """提取关键词"""
    keywords = await ai_service.extract_keywords(request.content, request.top_k)
    
    return {
        "code": 200,
        "message": "提取关键词成功",
        "data": {
            "keywords": keywords
        }
    }


@router.get("/news/{news_id}/summary")
@handle_llm_error
async def get_news_summary(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取新闻摘要（需要登录）"""
    from crud import news as news_crud
    news_detail = await news_crud.get_news_detail(db, news_id)
    
    if not news_detail:
        raise HTTPException(status_code=404, detail="新闻不存在")
    
    summary = await ai_service.generate_summary(news_detail.content)
    
    if not summary:
        raise HTTPException(status_code=500, detail="生成摘要失败")
    
    return {
        "code": 200,
        "message": "生成摘要成功",
        "data": {
            "news_id": news_id,
            "title": news_detail.title,
            "summary": summary
        }
    }
