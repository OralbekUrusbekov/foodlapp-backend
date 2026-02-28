from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from . import Base

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    COOKING = "cooking"
    READY = "ready"
    GIVEN = "given"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(
        SQLEnum(
            OrderStatus,
            name="orderstatus",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=OrderStatus.PENDING,
        nullable=False
    )
    qr_code = Column(String, unique=True)
    qr_used = Column(Boolean, default=False)
    qr_expire_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    branch = relationship("Branch", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    food_id = Column(Integer, ForeignKey("foods.id"), nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    paid_by_subscription = Column(Boolean, default=False)


    
    # Relationships
    order = relationship("Order", back_populates="items")
    food = relationship("Food", back_populates="order_items")
    subscription = relationship("Subscription")

