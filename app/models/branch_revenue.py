from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from . import Base


class BranchRevenue(Base):
    __tablename__ = "branch_revenue"

    id = Column(Integer, primary_key=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


    amount = Column(Float, nullable=False, default=0)
    discount_amount = Column(Float, nullable=False, default=0)
    final_amount = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


    branch = relationship("Branch")
    order = relationship("Order")
    subscription = relationship("Subscription")
    user = relationship("User")