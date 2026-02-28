from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str  # "order", "payment", "system"
    status: str  # "unread", "read", "archived"
    order_id: Optional[int] = None
    branch_id: Optional[int] = None
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int


class CreateNotificationDTO(BaseModel):
    title: str
    message: str
    type: str
    order_id: Optional[int] = None
    branch_id: Optional[int] = None
    data: Optional[dict] = None
