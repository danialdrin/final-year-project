import logging
from redis.asyncio import Redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class ResilientRedis:
    def __init__(self, url: str):
        self.url = url
        self._real_client = Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.8)
        self._fake_client = None
        self._use_fake = False

    async def _get_client(self):
        if self._use_fake:
            return self._fake_client
        try:
            await self._real_client.ping()
            return self._real_client
        except Exception:
            self._use_fake = True
            if self._fake_client is None:
                import fakeredis.aioredis
                self._fake_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
            logger.info("Local Redis server not reachable; using in-memory cache fallback.")
            return self._fake_client

    async def get(self, key: str):
        c = await self._get_client()
        return await c.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        c = await self._get_client()
        return await c.set(key, value, ex=ex)

    async def setex(self, key: str, time: int, value: str):
        c = await self._get_client()
        return await c.set(key, value, ex=time)

    async def ping(self):
        c = await self._get_client()
        return await c.ping()

    async def aclose(self):
        if self._real_client is not None:
            try:
                await self._real_client.aclose()
            except Exception:
                pass
        if self._fake_client is not None:
            try:
                await self._fake_client.aclose()
            except Exception:
                pass

_redis_client: ResilientRedis | None = None

def get_redis_client() -> ResilientRedis:
    global _redis_client
    if _redis_client is None:
        _redis_client = ResilientRedis(settings.REDIS_URL)
    return _redis_client

async def close_redis_connection():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
