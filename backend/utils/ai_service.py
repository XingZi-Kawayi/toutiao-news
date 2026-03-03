import httpx
import hashlib
from typing import List, Optional, AsyncGenerator
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
    
    async def _call_llm_stream(self, messages: List[dict]) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-SSE": "enable"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True
                }
            ) as response:
                if response.status_code == 401:
                    raise LLMAuthError("Invalid API key")
                elif response.status_code == 429:
                    raise LLMRateLimitError("Rate limit exceeded")
                elif response.status_code >= 500:
                    raise LLMServiceError(f"Server error: {response.status_code}")
                
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str and data_str != "[DONE]":
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
    
    async def generate_summary(self, content: str, max_length: int = 200) -> Optional[str]:
        messages = [
            {
                "role": "system",
                "content": """你是一位资深的新闻编辑专家，擅长从复杂的新闻内容中提炼核心信息。

任务要求：
1. 生成不超过{max_length}字的摘要
2. 必须包含：时间、地点、关键人物、核心事件、影响/结果
3. 使用客观、中立的新闻语言
4. 避免使用模糊表述和主观判断
5. 摘要结构应该符合"倒金字塔"结构

输出格式要求：
- 只输出摘要正文，不要任何前缀、后缀或说明
- 不要使用Markdown格式
- 保持段落连贯"""
            },
            {
                "role": "user",
                "content": f"请为以下新闻内容生成一个不超过{max_length}字的摘要：\n\n{content}"
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
            "content": """你是一个专业的新闻助手，名叫"头条AI助手"。

你的职责：
1. 帮助用户了解新闻时事，解答相关问题
2. 回答要简洁明了，有条理
3. 保持客观中立的态度
4. 如果问题超出新闻领域，礼貌地说明你的专长范围
5. 引用信息时尽量注明来源（如果知道）

回答风格：
- 专业但友好
- 使用清晰的要点或段落
- 避免过于技术性的术语"""
        }
        messages_with_system = [system_message] + messages
        
        result = await self._call_llm(messages_with_system)
        if result and "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"].strip()
        return None
    
    async def chat_stream(self, messages: List[dict]) -> AsyncGenerator[str, None]:
        system_message = {
            "role": "system",
            "content": """你是一个专业的新闻助手，名叫"头条AI助手"。

你的职责：
1. 帮助用户了解新闻时事，解答相关问题
2. 回答要简洁明了，有条理
3. 保持客观中立的态度
4. 如果问题超出新闻领域，礼貌地说明你的专长范围
5. 引用信息时尽量注明来源（如果知道）

回答风格：
- 专业但友好
- 使用清晰的要点或段落
- 避免过于技术性的术语"""
        }
        messages_with_system = [system_message] + messages
        
        async for chunk in self._call_llm_stream(messages_with_system):
            yield chunk
    
    async def extract_keywords(self, content: str, top_k: int = 5) -> List[str]:
        messages = [
            {
                "role": "system",
                "content": """你是一个专业的内容分析师，擅长从文本中提取高质量关键词。

关键词提取标准：
1. 选择最能代表文本主题的词语
2. 优先选择名词和专有名词
3. 避免使用过于通用的词汇（如"的"、"是"、"和"等）
4. 关键词应该具有检索价值
5. 按重要性排序输出"""
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
                "content": """你是一个专业的情感分析专家。

情感判断标准：
- 正面：内容积极向上，传达希望、喜悦、成功等情绪
- 负面：内容消极悲观，传达失望、悲伤、失败等情绪
- 中性：内容客观中立，无明显情感倾向

输出要求：
- 只输出'正面'、'负面'或'中性'中的一个
- 不要有任何其他说明文字"""
            },
            {
                "role": "user",
                "content": f"请判断以下新闻的情感倾向：\n\n{content}"
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


ai_service = AIService()
