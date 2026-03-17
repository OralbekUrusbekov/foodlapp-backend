from sqlalchemy import Column, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from . import Base

class BranchMenu(Base):
    """
    BranchMenu is exclusively used to toggle the availability 
    of a Food item for a specific branch.
    """
    __tablename__ = "branch_menus"

    id = Column(Integer, primary_key=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    food_id = Column(Integer, ForeignKey("foods.id"), nullable=False)
    
    # is_available defaults to False, meaning canteen admin has to explicitly 
    # turn it on for today/the specific branch
    is_available = Column(Boolean, default=False, nullable=False)

    # A food item can only have one availability toggle per branch
    __table_args__ = (
        UniqueConstraint('branch_id', 'food_id', name='uq_branch_food'),
    )

    branch = relationship("Branch", back_populates="branch_menus")
    food = relationship("Food", back_populates="branch_menus")
