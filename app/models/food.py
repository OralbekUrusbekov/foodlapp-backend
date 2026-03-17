import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from . import Base


class MenuType(enum.Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    REGULAR = "REGULAR"


class Food(Base):
    __tablename__ = "foods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    calories = Column(Integer)
    ingredients = Column(Text)
    
    menu_type = Column(SQLAlchemyEnum(MenuType), default=MenuType.REGULAR, nullable=False)
    
    # either owner_id (for SUBSCRIPTION) or restaurant_id (for REGULAR) should be set
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=True)

    owner = relationship("User", back_populates="created_foods", foreign_keys=[owner_id])
    restaurant = relationship("Restaurant", back_populates="regular_foods", foreign_keys=[restaurant_id])
    
    order_items = relationship("OrderItem", back_populates="food")
    images = relationship("FoodImage", back_populates="food", cascade="all, delete")
    branch_menus = relationship("BranchMenu", back_populates="food", cascade="all, delete")
    subscription_menus = relationship("SubscriptionMenu", back_populates="food", cascade="all, delete")

