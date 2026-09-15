import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./paperlab.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    mode: str = os.getenv("DATA_MODE", "replay")
    alpaca_key: str = os.getenv("ALPACA_API_KEY", "")
    alpaca_secret: str = os.getenv("ALPACA_SECRET_KEY", "")
    us_limit: int = min(30, max(1, int(os.getenv("US_STREAM_LIMIT", "30"))))
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    replay_file: str = os.getenv("REPLAY_FILE", "data/replay/demo.csv")
    ksa_catalog: str = os.getenv("KSA_CATALOG_FILE", "data/imports/ksa.csv")
    token: str = os.getenv("APP_TOKEN", "")

    def __post_init__(self):
        if self.mode not in {"replay", "live"}:
            raise ValueError("DATA_MODE must be replay or live; execution is always simulated")


settings = Settings()
