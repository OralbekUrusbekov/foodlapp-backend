from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from . import Base

class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"



class ActivityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class AIProfile(Base):
    __tablename__ = "ai_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    age = Column(Integer, nullable=True)
    gender = Column(SQLEnum(Gender, name="gender", values_callable=lambda enum: [e.value for e in enum]), nullable=True)
    height = Column(Float, nullable=True) # in cm
    weight = Column(Float, nullable=True) # in kg
    
    goal = Column(String, nullable=True) # comma separated goals
    activity_level = Column(SQLEnum(ActivityLevel, name="activitylevel", values_callable=lambda enum: [e.value for e in enum]), nullable=True)
    
    allergies = Column(String, nullable=True) # comma separated
    dislikes = Column(String, nullable=True) # comma separated
    diet_type = Column(String, nullable=True) # e.g., halal, keto, vegetarian
    
    user = relationship("User", backref="ai_profile", uselist=False)
