from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, AsyncGenerator
from functools import wraps
from sqlalchemy.ext.asyncio import AsyncSession
from config.config import get_db
from utils.ai_service import ai_service, LLMAuthError, LLMRateLimitError, LLMServiceError
from utils.auth import get_current_user
from models.users import User
import logging
import json

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


class SentimentRequest(BaseModel):
    content: str = Field(..., description="文本内容", max_length=10000)


class SentimentResponse(BaseModel):
    sentiment: str


def handle_llm_error(func):
    @wraps(func)
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
    """AI 对话（非流式）"""
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


@router.post("/chat/stream")
async def ai_chat_stream(request: ChatRequest):
    """AI 对话（流式响应 SSE）"""
    async def generate():
        try:
            async for chunk in ai_service.chat_stream(request.messages):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except LLMAuthError:
            logger.error("LLM authentication error")
            yield f"data: {json.dumps({'error': 'AI 服务配置错误'}, ensure_ascii=False)}\n\n"
        except LLMRateLimitError:
            logger.warning("LLM rate limit exceeded")
            yield f"data: {json.dumps({'error': '请求过于频繁'}, ensure_ascii=False)}\n\n"
        except LLMServiceError as e:
            logger.error(f"LLM service error: {e}")
            yield f"data: {json.dumps({'error': 'AI 服务暂时不可用'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Unexpected error in stream: {e}")
            yield f"data: {json.dumps({'error': '生成失败: ' + str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )


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


@router.post("/sentiment")
@handle_llm_error
async def analyze_sentiment(
    request: SentimentRequest,
    db: AsyncSession = Depends(get_db)
):
    """情感分析"""
    sentiment = await ai_service.analyze_sentiment(request.content)
    
    if not sentiment:
        raise HTTPException(status_code=500, detail="情感分析失败，请稍后重试")
    
    return {
        "code": 200,
        "message": "情感分析成功",
        "data": {
            "sentiment": sentiment
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
