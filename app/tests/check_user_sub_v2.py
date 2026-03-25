import sys
import os
sys.path.append(os.getcwd())
from app.database.connection import SessionLocal
from app.models.subscription import UserSubscription, Subscription
from app.models.order import Order
from datetime import datetime

with open("output_report.txt", "w", encoding="utf-8") as f:
    db = SessionLocal()
    user_id = 1 # Assuming user 1 since it's the most common test user

    active_sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.is_active == True
    ).first()

    if active_sub:
        f.write(f"Active UserSubscription: ID={active_sub.id}, SubID={active_sub.subscription_id}, Remaining={active_sub.remaining_meals}, EndDate={active_sub.end_date}\n")
        sub = active_sub.subscription
        f.write(f"Subscription Specs: DailyLimit={sub.daily_limit}, Time={sub.allowed_from}-{sub.allowed_to}\n")
        
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        today_used = db.query(Order).filter(
            Order.user_id == user_id,
            Order.subscription_id == sub.id,
            Order.created_at >= today_start,
            Order.paid_by_subscription == True
        ).count()
        f.write(f"Today Used (per OrderService logic): {today_used}\n")
        
        last_orders = db.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(5).all()
        for o in last_orders:
            f.write(f"Order ID={o.id}, CreatedAt={o.created_at}, PaidBySub={o.paid_by_subscription}, Status={o.status}\n")
    else:
        f.write("No active subscription found for user 1\n")
