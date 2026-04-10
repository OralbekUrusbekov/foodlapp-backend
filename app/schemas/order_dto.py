from pydantic import BaseModel, ValidationError
from typing import List, Optional
from datetime import datetime

class OrderItemRequest(BaseModel):
    food_id: int
    quantity: int = 1

    class Config:
        extra = "forbid"

class CreateOrderRequest(BaseModel):
    branch_id: int
    items: List[OrderItemRequest]

    class Config:
        extra = "forbid"

class OrderItemResponse(BaseModel):
    id: int
    food_id: int
    food_name: str
    quantity: int
    
    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    user_id: int
    branch_id: int
    status: str
    qr_code: Optional[str]
    qr_used: bool
    is_paid: Optional[bool] = None
    receipt_url: Optional[str] = None
    created_at: datetime
    branch_name: Optional[str] = None
    items: List[OrderItemResponse]
    
    class Config:
        from_attributes = True
