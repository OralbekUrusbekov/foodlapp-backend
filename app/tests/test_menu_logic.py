import sys
import os
sys.path.append(os.getcwd())
from app.database.connection import SessionLocal
from app.models.subscription import UserSubscription, Subscription
from app.api.client import get_today_menu
from app.models.user import User
from datetime import datetime, time

db = SessionLocal()
user = db.query(User).filter(User.role == "client").first()

print(f"Testing Today's Menu for user: {user.email if user else 'None'}")

if user:
    # 🧪 TEST 1: Get today's menu
    menu = get_today_menu(db, user)
    print(f"Items in menu: {len(menu)}")
    for item in menu:
        print(f"- {item['name']} ({item['menu_type']})")

    # 🧪 TEST 2: Check if subscription foods are included appropriately
    active_sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id, UserSubscription.is_active == True).first()
    if active_sub:
        sub = active_sub.subscription
        print(f"Active sub: {sub.name}, Daily limit: {sub.daily_limit}, Time: {sub.allowed_from}-{sub.allowed_to}")
        
    else:
        print("No active subscription for test user")
else:
    print("Could not find a client user to test with")
