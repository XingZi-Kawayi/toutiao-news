import httpx
from typing import List, Optional
import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_ENDPOINT,
    DEFAULT_MODEL,
    LLM_TIMEOUT,
    CACHE_TTL,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB
)
from utils.cache import init_cache, get_cache

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMAuthError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMServiceError(LLMError):
    pass


class AIService:
    def __init__(self):
        self.api_key = DASHSCOPE_API_KEY
        self.endpoint = DASHSCOPE_ENDPOINT
        self.model = DEFAULT_MODEL
        self.timeout = LLM_TIMEOUT
        self._init_cache()
    
    def _init_cache(self):
        try:
            init_cache(
                redis_host=REDIS_HOST,
                redis_port=REDIS_PORT,
                redis_password=REDIS_PASSWORD,
                redis_db=REDIS_DB,
                default_ttl=CACHE_TTL
            )
            self.cache = get_cache()
        except Exception as e:
            logger.warning(f"Failed to initialize cache: {e}")
            self.cache = None
    
    async def _call_llm(self, messages: List[dict], stream: bool = False) -> Optional[dict]:
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": stream
                    }
                )
                
                if response.status_code == 401:
                    raise LLMAuthError("Invalid API key")
                elif response.status_code == 429:
                    raise LLMRateLimitError("Rate limit exceeded")
                elif response.status_code >= 500:
                    raise LLMServiceError(f"Server error: {response.status_code}")
                
                response.raise_for_status()
                return response.json()
        
        try:
            return await _make_request()
        except LLMAuthError as e:
            logger.error(f"LLM auth error: {e}")
            raise
        except LLMRateLimitError as e:
            logger.warning(f"LLM rate limit: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM API call failed after retries: {e}")
            return None
    
    async def generate_summary(self, content: str, max_length: int = 200) -> Optional[str]:
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的新闻编辑，请为新闻内容生成简洁准确的摘要。"
            },
            {
                "role": "user",
                "content": f"请为以下新闻内容生成一个不超过{max_length}字的摘要，只输出摘要内容，不要有其他说明：\n\n{content}"
            }
        ]
        
        cache_key = f"summary:{hashlib.md5((content + str(max_length)).encode()).hexdigest()}"
        
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug("Summary cache hit")
                return cached
        
        result = await self._call_llm(messages)
        if result and "choices" in result and len(result["choices"]) > 0:
            summary = result["choices"][0]["message"]["content"].strip()
            if self.cache and summary:
                await self.cache.set(cache_key, summary)
            return summary
        return None
    
    async def chat(self, messages: List[dict]) -> Optional[str]:
        system_message = {
            "role": "system",
            "content": "你是一个专业的新闻助手，可以帮助用户了解新闻、解答问题。回答要简洁明了，有条理。"
        }
        messages_with_system = [system_message] + messages
        
        result = await self._call_llm(messages_with_system)
        if result and "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"].strip()
        return None
    
    async def extract_keywords(self, content: str, top_k: int = 5) -> List[str]:
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的内容分析师，请从文本中提取关键词。"
            },
            {
                "role": "user",
                "content": f"请从以下文本中提取{top_k}个关键词，用逗号分隔，只输出关键词，不要有其他说明：\n\n{content}"
            }
        ]
        
        cache_key = f"keywords:{hashlib.md5((content + str(top_k)).encode()).hexdigest()}"
        
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug("Keywords cache hit")
                return cached
        
        result = await self._call_llm(messages)
        if result and "choices" in result and len(result["choices"]) > 0:
            keywords_str = result["choices"][0]["message"]["content"].strip()
            keywords = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
            if self.cache and keywords:
                await self.cache.set(cache_key, keywords)
            return keywords
        return []
    
    async def analyze_sentiment(self, content: str) -> Optional[str]:
        messages = [
            {
                "role": "system",
                "content": "你是一个情感分析专家，请判断文本的情感倾向。"
            },
            {
                "role": "user",
                "content": f"请判断以下新闻的情感倾向，只输出'正面'、'负面'或'中性'中的一个：\n\n{content}"
            }
        ]
        
        cache_key = f"sentiment:{hashlib.md5(content.encode()).hexdigest()}"
        
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug("Sentiment cache hit")
                return cached
        
        result = await self._call_llm(messages)
        if result and "choices" in result and len(result["choices"]) > 0:
            sentiment = result["choices"][0]["message"]["content"].strip()
            if self.cache and sentiment:
                await self.cache.set(cache_key, sentiment)
            return sentiment
        return None


import hashlib


ai_service = AIService()
