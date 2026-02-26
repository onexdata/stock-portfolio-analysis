from datetime import datetime

from pydantic import BaseModel, Field


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
    holdings: dict[str, int] = Field(default_factory=lambda: {
        "AAPL": 100, "GOOGL": 50, "MSFT": 75,
    })
    total_value: float = 125000.00
    current_analysis: CurrentAnalysis | None = None
    analysis_results: list[MetricResult] = Field(default_factory=list)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
