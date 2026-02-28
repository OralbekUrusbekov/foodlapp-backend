from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class OrderItemRequest(BaseModel):
    food_id: int
    quantity: int = 1

class CreateOrderRequest(BaseModel):
    branch_id: int
    items: List[OrderItemRequest]

class OrderItemResponse(BaseModel):
    id: int
    food_id: int
    food_name: str
    quantity: int
    price: float
    
    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    user_id: int
    branch_id: int
    branch_name: str
    total_price: float
    status: str
    qr_code: Optional[str]
    qr_used: bool
    created_at: datetime
    items: List[OrderItemResponse]
    
    class Config:
        from_attributes = True
