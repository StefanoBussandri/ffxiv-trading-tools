from pydantic import BaseModel


class HistoryAggregate(BaseModel):
    item_id: int
    name: str
    quality: str
    source: str
    appearances: int
    avg_profit: float
    avg_roi_pct: float
    avg_velocity: float
    avg_profit_per_day: float
    last_seen: int
