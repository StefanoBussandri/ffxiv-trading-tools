from pydantic import BaseModel


class Opportunity(BaseModel):
    itemId: int
    name: str
    quality: str
    buy_world: str
    buy_price: int
    sell_world: str
    sell_price: int
    profit: int
    roi_pct: float
    velocity: float
    profit_per_day: float
    buy_upload_ts: int
    sell_upload_ts: int
    source: str
