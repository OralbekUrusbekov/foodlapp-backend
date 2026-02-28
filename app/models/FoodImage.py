from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from . import Base

class FoodImage(Base):
    __tablename__ = "food_images"

    id = Column(Integer, primary_key=True, index=True)
    image_url = Column(String, nullable=False)
    food_id = Column(Integer, ForeignKey("foods.id", ondelete="CASCADE"))

    food = relationship("Food", back_populates="images")