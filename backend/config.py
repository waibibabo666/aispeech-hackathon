"""Central configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = "sk-placeholder"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    MODEL_NAME: str = "gpt-4o"
    WHISPER_MODEL: str = "whisper-1"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CONFIDENCE_AUTO_THRESHOLD: float = 0.80
    CONFIDENCE_REVIEW_LOWER: float = 0.50
    MAX_UPLOAD_SIZE_MB: int = 25

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
