from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

from .restaurant import Restaurant
from .user import User
from .branch import Branch
from .food import Food, MenuType
from .FoodImage import FoodImage
from .subscription import Subscription, UserSubscription, SubscriptionMenu
from .order import Order, OrderItem
from .branch_menu import BranchMenu
from .notification import Notification
from .branch_revenue import BranchRevenue
from .ai_profile import AIProfile
from .weight_history import WeightHistory
from .ration import Ration
from .otp_code import OtpCode


__all__ = [
    "Base",
    "Restaurant",
    "User",
    "Branch",
    "Food",
    "MenuType",
    "FoodImage",
    "Subscription",
    "UserSubscription",
    "SubscriptionMenu",
    "Order",
    "OrderItem",
    "BranchMenu",
    "Notification",
    "BranchRevenue",
    "AIProfile",
    "WeightHistory",
    "Ration",
    "OtpCode"
]

