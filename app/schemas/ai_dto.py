from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"



class ActivityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class AIProfileBase(BaseModel):
    age: Optional[int] = None
    gender: Optional[Gender] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    goal: Optional[str] = None
    activity_level: Optional[ActivityLevel] = None
    allergies: Optional[str] = None
    dislikes: Optional[str] = None
    diet_type: Optional[str] = None

class AIProfileUpdate(AIProfileBase):
    pass

class AIProfileDTO(AIProfileBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

class WeightEntryCreate(BaseModel):
    weight: float

class WeightHistoryDTO(BaseModel):
    id: int
    weight: float
    date: datetime

    class Config:
        from_attributes = True

class RationDTO(BaseModel):
    id: int
    date: datetime
    meal_type: str
    food_name: str
    calories: Optional[float] = None
    proteins: Optional[float] = None
    fats: Optional[float] = None
    carbs: Optional[float] = None
    is_orderable: bool
    food_id: Optional[int] = None

    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
