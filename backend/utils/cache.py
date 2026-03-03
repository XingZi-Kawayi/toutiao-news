import hashlib
import json
import asyncio
from typing import Optional, Any, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)

try:
    import redis
    from redis.asyncio import Redis as AsyncRedis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache")


class CacheManager:
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, 
                 redis_password: str = "", redis_db: int = 0, default_ttl: int = 86400):
        self.default_ttl = default_ttl
        self._redis_client: Optional[AsyncRedis] = None
        self._in_memory_cache: dict = {}
        self._use_redis = REDIS_AVAILABLE
        self._in_memory_cache: dict = {}
        
        if self._use_redis:
            try:
                self._redis_client = AsyncRedis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password if redis_password else None,
                    db=redis_db,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                logger.info("Redis cache initialized (connection will be tested on first use)")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client: {e}, falling back to in-memory cache")
                self._use_redis = False
    
    async def close(self):
        if self._redis_client:
            await self._redis_client.close()
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        key_data = f"{prefix}:{repr(args)}:{repr(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        if self._use_redis and self._redis_client:
            try:
                data = await self._redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                return self._in_memory_cache.get(key)
        else:
            return self._in_memory_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        ttl = ttl or self.default_ttl
        serialized = json.dumps(value, ensure_ascii=False)
        
        if self._use_redis and self._redis_client:
            try:
                await self._redis_client.setex(key, ttl, serialized)
            except Exception as e:
                logger.warning(f"Redis set failed: {e}, using in-memory cache")
                self._in_memory_cache[key] = value
        else:
            self._in_memory_cache[key] = value
    
    async def delete(self, key: str):
        if self._use_redis and self._redis_client:
            try:
                await self._redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        if key in self._in_memory_cache:
            del self._in_memory_cache[key]
    
    def cache(self, prefix: str, ttl: Optional[int] = None):
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                key = f"{prefix}:{self._generate_key('', *args[1:], **kwargs)}"
                cached = await self.get(key)
                if cached is not None:
                    logger.debug(f"Cache hit for {prefix}")
                    return cached
                
                result = await func(*args, **kwargs)
                if result is not None:
                    await self.set(key, result, ttl)
                return result
            return wrapper
        return decorator


_cache_instance: Optional[CacheManager] = None


def init_cache(redis_host: str = "localhost", redis_port: int = 6379, 
               redis_password: str = "", redis_db: int = 0, default_ttl: int = 86400) -> CacheManager:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_password=redis_password,
            redis_db=redis_db,
            default_ttl=default_ttl
        )
    return _cache_instance


def get_cache() -> CacheManager:
    global _cache_instance
    if _cache_instance is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return _cache_instance
