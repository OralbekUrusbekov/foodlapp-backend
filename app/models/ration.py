from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from . import Base

class Ration(Base):
    __tablename__ = "rations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    date = Column(DateTime(timezone=True), nullable=False)
    meal_type = Column(String, nullable=False) # e.g., breakfast, lunch, dinner, snack
    food_name = Column(String, nullable=False)
    
    calories = Column(Float, nullable=True)
    proteins = Column(Float, nullable=True)
    fats = Column(Float, nullable=True)
    carbs = Column(Float, nullable=True)
    
    is_orderable = Column(Boolean, default=False)
    food_id = Column(Integer, ForeignKey("foods.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
