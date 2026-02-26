from datetime import datetime

from pydantic import BaseModel, Field

from app.config import config

_ui = config.features.client_ui.settings


# --- WebSocket messages ---


class AnalyzeRequest(BaseModel):
    action: str  # "analyze"
    ticker: str


class AnalysisResultMessage(BaseModel):
    type: str = "analysis_result"
    ticker: str
    metric: str
    value: float
    timestamp: datetime


class ErrorMessage(BaseModel):
    type: str = "error"
    detail: str


# --- Portfolio state stored in Redis ---


class CurrentAnalysis(BaseModel):
    ticker: str
    started_at: datetime


class MetricResult(BaseModel):
    ticker: str
    metric: str
    value: float
    timestamp: datetime


class PortfolioState(BaseModel):
    session_id: str
    holdings: dict[str, int] = Field(
        default_factory=lambda: dict(_ui.default_holdings)
    )
    total_value: float = Field(default_factory=lambda: _ui.initial_total_value)
    current_analysis: CurrentAnalysis | None = None
    analysis_results: list[MetricResult] = Field(default_factory=list)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
