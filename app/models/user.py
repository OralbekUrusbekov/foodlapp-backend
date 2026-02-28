from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
import enum
from . import Base

class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    CANTEEN_ADMIN = "canteen_admin"
    CASHIER = "cashier"
    SCREEN = "screen"
    CLIENT = "client"



class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(
        SQLEnum(
            UserRole,
            name="userrole",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
    )
    is_active = Column(Boolean, default=True)

    # Profile fields
    avatar_url = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    address = Column(String, nullable=True)

    # ForeignKey-лерді User-ден толық алып тастаймыз!

    # Relationships (back-references)
    owned_restaurants = relationship(
        "Restaurant",
        back_populates="owner",
        foreign_keys="Restaurant.owner_id"  # нақты қай FK екенін көрсетеміз
    )

    managed_restaurant = relationship(
        "Restaurant",
        back_populates="admin",
        foreign_keys="Restaurant.admin_id",  # ОСЫ ЖЕРДЕ НАҚТЫ КӨРСЕТЕМІЗ!
        uselist=False  # бір admin бір ғана асхана басқарады
    )

    managed_branch = relationship(
        "Branch",
        back_populates="staff",
        foreign_keys="Branch.staff_id",
        uselist=False
    )

    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    branch = relationship("Branch", back_populates="users", foreign_keys=[branch_id])

    orders = relationship("Order", back_populates="user")
    subscriptions = relationship("UserSubscription", back_populates="user")
    notifications = relationship("Notification", back_populates="user")