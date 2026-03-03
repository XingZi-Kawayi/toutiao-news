import httpx
from typing import List, Optional
import json

# AI 服务配置
DASHSCOPE_API_KEY = "sk-9c4d89982a6a4bd3b7494d94751fe81c"
DASHSCOPE_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen3-max-preview"


class AIService:
    """AI 服务类 - 封装通义千问 API 调用"""
    
    def __init__(self):
        self.api_key = DASHSCOPE_API_KEY
        self.endpoint = DASHSCOPE_ENDPOINT
        self.model = DEFAULT_MODEL
    
    async def _call_llm(self, messages: List[dict], stream: bool = False) -> Optional[dict]:
        """调用 LLM API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
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
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"LLM API 调用失败：{e}")
                return None
    
    async def generate_summary(self, content: str, max_length: int = 200) -> Optional[str]:
        """生成新闻摘要"""
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
        
        result = await self._call_llm(messages)
        if result and "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"].strip()
        return None
    
    async def chat(self, messages: List[dict]) -> Optional[str]:
        """通用对话"""
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
        """提取关键词"""
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
        
        result = await self._call_llm(messages)
        if result and "choices" in result and len(result["choices"]) > 0:
            keywords_str = result["choices"][0]["message"]["content"].strip()
            return [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
        return []
    
    async def analyze_sentiment(self, content: str) -> Optional[str]:
        """情感分析"""
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
        
        result = await self._call_llm(messages)
        if result and "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"].strip()
        return None


# 创建全局 AI 服务实例
ai_service = AIService()
