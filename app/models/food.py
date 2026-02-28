from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from . import Base


class Food(Base):
    __tablename__ = "foods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    calories = Column(Integer)
    ingredients = Column(Text)
    is_available = Column(Boolean, default=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)

    branch = relationship("Branch", back_populates="foods")
    order_items = relationship("OrderItem", back_populates="food")
    images = relationship("FoodImage", back_populates="food", cascade="all, delete")
