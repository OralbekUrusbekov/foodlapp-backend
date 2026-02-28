from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    logo_url = Column(String)
    is_active = Column(Boolean, default=True)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)  # unique – бір admin бір асхана

    # Relationships
    owner = relationship("User", back_populates="owned_restaurants", foreign_keys=[owner_id])
    admin = relationship("User", back_populates="managed_restaurant", foreign_keys=[admin_id])

    branches = relationship("Branch", back_populates="restaurant")