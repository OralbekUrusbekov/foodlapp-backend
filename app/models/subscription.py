from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Time, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from . import Base


class SubscriptionMenu(Base):
    """Абонемент мәзірі — абонемент пен тағам байланысы"""
    __tablename__ = "subscription_menus"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    food_id = Column(Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("subscription_id", "food_id", name="uq_subscription_food"),
    )

    subscription = relationship("Subscription", back_populates="menu_items")
    food = relationship("Food")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)

    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)

    meal_limit = Column(Integer)

    is_active = Column(Boolean, default=True)

    daily_limit = Column(Integer, nullable=True)
    allowed_from = Column(Time, nullable=True)
    allowed_to = Column(Time, nullable=True)
    branch_restriction = Column(Boolean, default=False)

    # GLOBAL subscription — branch байланыс жоқ
    user_subscriptions = relationship("UserSubscription", back_populates="subscription")
    orders = relationship("Order", back_populates="subscription")
    menu_items = relationship("SubscriptionMenu", back_populates="subscription", cascade="all, delete-orphan")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)

    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)

    remaining_meals = Column(Integer)
    is_active = Column(Boolean, default=True)

    status = Column(String, default="ACTIVE")
    receipt_url = Column(String, nullable=True)

    user = relationship("User", back_populates="subscriptions")
    subscription = relationship("Subscription", back_populates="user_subscriptions")

