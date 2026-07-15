"""Central configuration loaded from environment variables.

API credentials (LLM key, URL, model) are configured exclusively
through the Settings panel in the UI and persisted to data/runtime_config.json.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Confidence thresholds
    CONFIDENCE_AUTO_THRESHOLD: float = 0.80
    CONFIDENCE_REVIEW_LOWER: float = 0.50
    MAX_UPLOAD_SIZE_MB: int = 25

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
