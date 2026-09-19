import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./paperlab.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    mode: str = os.getenv("DATA_MODE", "live")
    stock_poll_seconds: int = max(15, int(os.getenv("STOCK_POLL_SECONDS", "15")))
    saudi_poll_seconds: int = max(60, int(os.getenv("SAUDI_POLL_SECONDS", "60")))
    alpaca_key: str = os.getenv("ALPACA_API_KEY", "")
    alpaca_secret: str = os.getenv("ALPACA_SECRET_KEY", "")
    us_limit: int = min(30, max(1, int(os.getenv("US_STREAM_LIMIT", "30"))))
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
    replay_file: str = os.getenv("REPLAY_FILE", "data/replay/demo.csv")
    ksa_catalog: str = os.getenv("KSA_CATALOG_FILE", "data/imports/ksa.csv")
    token: str = os.getenv("APP_TOKEN", "")
    public_demo: bool = os.getenv("PUBLIC_DEMO", "false").lower() == "true"
    public_demo_loop: bool = os.getenv("PUBLIC_DEMO_LOOP", "false").lower() == "true"
    public_live_data_allowed: bool = os.getenv("PUBLIC_LIVE_DATA_ALLOWED", "false").lower() == "true"

    def __post_init__(self):
        if self.mode not in {"replay", "live"}:
            raise ValueError("DATA_MODE must be replay or live; execution is always simulated")
        if self.public_demo and not self.token:
            raise ValueError("PUBLIC_DEMO requires a private APP_TOKEN for admin actions")
        if self.public_demo_loop and not (self.public_demo and self.mode == "replay"):
            raise ValueError("PUBLIC_DEMO_LOOP requires PUBLIC_DEMO=true and DATA_MODE=replay")
        if self.public_demo and self.mode == "live" and not self.public_live_data_allowed:
            raise ValueError("Public live-data display needs verified redistribution rights")


settings = Settings()
