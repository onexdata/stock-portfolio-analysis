"""Feature-structured config from config.json + env-only deployment settings."""

import json
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ── Kebab-case alias support ────────────────────────────────────────────────

def _snake_to_kebab(name: str) -> str:
    return name.replace("_", "-")


class _KebabModel(BaseModel):
    """Base model that reads kebab-case JSON keys as snake_case Python attrs."""
    model_config = {"alias_generator": _snake_to_kebab, "populate_by_name": True}


# ── Feature settings models ────────────────────────────────────────────────


class ClientConnectivitySettings(_KebabModel):
    idle_timeout_seconds: int = 60
    auto_reconnect: bool = True
    session_id_prefix: str = "s"
    session_ttl_seconds: int = 86400


class ClientUiSettings(_KebabModel):
    theme: str = "dark"
    default_holdings: dict[str, int] = Field(
        default_factory=lambda: {"AAPL": 100, "GOOGL": 50, "MSFT": 75}
    )
    initial_total_value: float = 125000.00


class AnalysisSettings(_KebabModel):
    metrics: list[str] = Field(default_factory=lambda: [
        "portfolio_risk", "concentration", "correlation", "momentum", "allocation_score",
    ])
    max_concurrent: int = 5
    simulation_delay_range: list[float] = Field(default_factory=lambda: [2, 5])


class MarketUpdatesSettings(_KebabModel):
    interval_seconds: float = 30
    base_prices: dict[str, float] = Field(default_factory=lambda: {
        "AAPL": 185.0, "GOOGL": 140.0, "MSFT": 375.0,
        "AMZN": 155.0, "TSLA": 200.0, "META": 390.0, "NVDA": 650.0,
    })
    default_price: float = 100.0
    volatility: float = 0.02


# ── Feature wrappers ────────────────────────────────────────────────────────


class ClientConnectivityFeature(_KebabModel):
    enabled: bool = True
    settings: ClientConnectivitySettings = Field(default_factory=ClientConnectivitySettings)


class ClientUiFeature(_KebabModel):
    enabled: bool = True
    settings: ClientUiSettings = Field(default_factory=ClientUiSettings)


class AnalysisFeature(_KebabModel):
    enabled: bool = True
    settings: AnalysisSettings = Field(default_factory=AnalysisSettings)


class MarketUpdatesFeature(_KebabModel):
    enabled: bool = True
    settings: MarketUpdatesSettings = Field(default_factory=MarketUpdatesSettings)


# ── Top-level config ────────────────────────────────────────────────────────


class AppInfo(_KebabModel):
    name: str = "Portfolio Analysis"


class Features(_KebabModel):
    client_connectivity: ClientConnectivityFeature = Field(default_factory=ClientConnectivityFeature)
    client_ui: ClientUiFeature = Field(default_factory=ClientUiFeature)
    analysis: AnalysisFeature = Field(default_factory=AnalysisFeature)
    market_updates: MarketUpdatesFeature = Field(default_factory=MarketUpdatesFeature)


class AppConfig(_KebabModel):
    app: AppInfo = Field(default_factory=AppInfo)
    features: Features = Field(default_factory=Features)


# ── Loader ──────────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def _load_config() -> AppConfig:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return AppConfig.model_validate(json.load(f))
    return AppConfig()


# ── Env-only deployment settings ────────────────────────────────────────────


class EnvSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"

    model_config = {"env_prefix": "PORTFOLIO_"}


# ── Module-level exports ────────────────────────────────────────────────────

config = _load_config()
env = EnvSettings()
