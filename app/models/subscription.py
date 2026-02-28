from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base
from sqlalchemy import Time



class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)

    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)

    meal_limit = Column(Integer)
    discount_percentage = Column(Float, default=0.0)

    is_active = Column(Boolean, default=True)

    daily_limit = Column(Integer, nullable=True)
    allowed_from = Column(Time, nullable=True)
    allowed_to = Column(Time, nullable=True)
    branch_restriction = Column(Boolean, default=False)


    # GLOBAL subscription — branch байланыс жоқ
    user_subscriptions = relationship("UserSubscription", back_populates="subscription")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)

    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)

    remaining_meals = Column(Integer)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="subscriptions")
    subscription = relationship("Subscription", back_populates="user_subscriptions")
