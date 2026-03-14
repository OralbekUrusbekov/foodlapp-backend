from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SubscriptionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    duration_days: int
    meal_limit: Optional[int]
    discount_percentage: Optional[float] = 0.0
    is_active: bool
    
    class Config:
        from_attributes = True

class UserSubscriptionResponse(BaseModel):
    id: int
    subscription: SubscriptionResponse
    start_date: datetime
    end_date: datetime
    remaining_meals: Optional[int]
    is_active: bool
    
    class Config:
        from_attributes = True

class PurchaseSubscriptionRequest(BaseModel):
    subscription_id: int
