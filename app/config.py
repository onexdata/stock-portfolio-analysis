from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 86400  # 24 hours
    market_update_interval_seconds: float = 30.0
    analysis_metrics: list[str] = [
        "portfolio_risk",
        "concentration",
        "correlation",
        "momentum",
        "allocation_score",
    ]

    model_config = {"env_prefix": "PORTFOLIO_"}


settings = Settings()
