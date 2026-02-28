from pydantic import BaseModel
from typing import Optional


class RestaurantCreate(BaseModel):
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None


class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None
    admin_id: Optional[int] = None


class RestaurantResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    owner_id: int
    admin_id: Optional[int]

    class Config:
        from_attributes = True


class AdminAssign(BaseModel):
    admin_id: int
