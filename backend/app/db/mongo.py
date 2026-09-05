from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

_client: AsyncIOMotorClient | None = None

def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client

def get_database():
    client = get_mongo_client()
    return client[settings.MONGO_DB_NAME]

def get_collection(name: str):
    db = get_database()
    return db[name]

async def close_mongo_connection():
    global _client
    if _client is not None:
        _client.close()
        _client = None
