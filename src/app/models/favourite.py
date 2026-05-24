from pydantic import BaseModel, Field


class Favourite(BaseModel):
    item_id: int
    quality: str
    added_at: int


class FavouriteAdd(BaseModel):
    item_id: int = Field(..., gt=0)
    quality: str


class FavouriteAlert(BaseModel):
    buy_target: int | None = None
    buy_dir: str | None = None
    sell_target: int | None = None
    sell_dir: str | None = None
