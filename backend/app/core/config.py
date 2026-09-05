from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    MONGO_URI: str = "mongodb+srv://dani9629198934dani_db_user:SxGJSGhhNqTWuD6R@cluster0.d84ctwd.mongodb.net/?appName=Cluster0"
    MONGO_DB_NAME: str = "skill_intelligence"
    REDIS_URL: str = "redis://default:R7MjAPdAkNtKcTNBqcMjHcqUJLXWGUiE@matchless-marvellous-topiary-27115.db.redis.io:17312"
    JWT_SECRET: str = "supersecret_jwt_key_skill_intelligence_platform_2026_change_in_prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    APP_ENV: str = "development"
    YOUTUBE_API_KEY: str = ""
    MEDIUM_ANALYSIS_MODEL_NAME: str = "all-MiniLM-L6-v2"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("GROQ_MODEL", "GROQ_BASE_URL", "APP_ENV")
    @classmethod
    def validate_model_configuration(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Groq model and base URL values cannot be blank")
        return value

settings = Settings()
