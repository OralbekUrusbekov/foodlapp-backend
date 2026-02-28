from sqlalchemy import Column, Integer, String, Boolean, Time, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String)
    opening_time = Column(Time)
    closing_time = Column(Time)
    is_active = Column(Boolean, default=True)

    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)

    restaurant = relationship("Restaurant", back_populates="branches")
    staff = relationship("User", back_populates="managed_branch", foreign_keys=[staff_id])

    foods = relationship("Food", back_populates="branch")
    orders = relationship("Order", back_populates="branch")



    users = relationship("User", back_populates="branch", foreign_keys="[User.branch_id]")
