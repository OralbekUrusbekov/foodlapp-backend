from pydantic import BaseModel
from typing import Optional

class FoodResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    calories: Optional[int]
    ingredients: Optional[str]
    image_url: Optional[str]
    is_available: bool
    branch_id: int
    
    class Config:
        from_attributes = True

class CreateFoodRequest(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    calories: Optional[int] = None
    ingredients: Optional[str] = None
    image_url: Optional[str] = None
    # branch_id міндетті емес, себебі backend автоматты қосады

class UpdateFoodRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    calories: Optional[int] = None
    ingredients: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
