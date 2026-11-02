from datetime import datetime
from typing import Literal , Optional

from pydantic import BaseModel, Field

AlertMetric = Literal[
    "error_rate",
    "p95_latency_ms",
    "daily_cost_usd",
]


class AlertRuleCreate(BaseModel):
    metric_name: str = Field(
        ...,
        pattern=r"^(error_rate|p95_latency_ms|daily_cost_usd)$",
    )
    threshold: float = Field(..., gt=0, allow_inf_nan=False)
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    threshold: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    enabled: Optional[bool] = None


class ReportCreate(BaseModel):
    period: Literal["daily"] = "daily"


class TraceEventResponse(BaseModel):
    id: str
    event_type: str
    name: str
    status: str
    model_name: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    error_type: str | None
    started_at: datetime


class TraceResponse(BaseModel):
    trace_id: str
    status: str
    latency_ms: int | None
    event_count: int
    started_at: datetime
    finished_at: datetime | None
    events: list[TraceEventResponse]