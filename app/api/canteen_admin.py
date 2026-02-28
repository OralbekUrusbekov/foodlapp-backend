from fastapi import APIRouter, Depends, HTTPException
import logging
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import List
from app.database.connection import get_db
from app.configuration.security.dependencies import get_canteen_admin_user
from app.service.food_service import FoodService
from app.schemas.food_dto import FoodResponse, CreateFoodRequest, UpdateFoodRequest
from app.models.user import User, UserRole
from app.models.order import Order
from app.service.auth_service import AuthService
from datetime import datetime, timedelta

router = APIRouter()
logger = logging.getLogger(__name__)



@router.get("/stats/subscriptions")
def branch_subscription_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_canteen_admin_user)
):
    from sqlalchemy import func
    from app.models.order import Order
    from app.models.subscription import Subscription

    rows = (
        db.query(
            Subscription.name,
            func.count(Order.id)
        )
        .join(Order, Order.subscription_id == Subscription.id)
        .filter(
            Order.branch_id == current_user.branch_id,
            Order.paid_by_subscription == True
        )
        .group_by(Subscription.name)
        .all()
    )

    return rows



# Тағамдарды басқару
@router.get("/foods", response_model=List[FoodResponse])
def get_branch_foods(db: Session = Depends(get_db), current_user: User = Depends(get_canteen_admin_user)):
    """Менің филиалымның тағамдары"""
    if not current_user.branch_id:
        raise HTTPException(status_code=400, detail="Сізге филиал тағайындалмаған")

    from app.models.food import Food
    foods = db.query(Food).filter(Food.branch_id == current_user.branch_id).all()
    return foods


@router.post("/foods", response_model=FoodResponse, status_code=201)
def create_food(
        food_data: CreateFoodRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_canteen_admin_user)
):
    """Жаңа тағам қосу (өз филиалыма)"""
    if not current_user.branch_id:
        raise HTTPException(status_code=400, detail="Сізге филиал тағайындалмаған")

    # Override branch_id with canteen admin's branch
    food_dict = food_data.model_dump()
    food_dict['branch_id'] = current_user.branch_id

    try:
        logger.info("Creating food: %s", {k: food_dict.get(k) for k in ['name','price','branch_id']})
        food = FoodService.create_food(db, food_dict)
        logger.info("Food created id=%s name=%s", food.id, food.name)
        return food
    except Exception as e:
        # Log full exception with stacktrace so Render captures it
        logger.exception("Error creating food")
        # Return a concise error to the client
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/foods/{food_id}", response_model=FoodResponse)
def update_food(
        food_id: int,
        food_data: UpdateFoodRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_canteen_admin_user)
):
    """Тағамды жаңарту"""
    food = FoodService.update_food(db, food_id, food_data.model_dump(exclude_unset=True))
    return food


@router.delete("/foods/{food_id}")
def delete_food(
        food_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_canteen_admin_user)
):
    """Тағамды өшіру"""
    return FoodService.delete_food(db, food_id)


class CreateCashierRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str

# Кассирлерді басқару
@router.post("/cashiers", status_code=201)
def create_cashier(
        cashier_data: CreateCashierRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_canteen_admin_user)
):
    """Жаңа кассир қосу (өз филиалыма)"""
    if not current_user.branch_id:
        raise HTTPException(status_code=400, detail="Сізге филиал тағайындалмаған")

    # Email тексеру
    if db.query(User).filter(User.email == cashier_data.email).first():
        raise HTTPException(status_code=400, detail="Email тіркелген")

    # Жаңа кассир
    hashed_password = AuthService.get_password_hash(cashier_data.password)
    cashier = User(
        full_name=cashier_data.full_name,
        email=cashier_data.email,
        hashed_password=hashed_password,
        role=UserRole.CASHIER,
        branch_id=current_user.branch_id
    )

    db.add(cashier)
    db.commit()
    db.refresh(cashier)
    return cashier


@router.get("/cashiers")
def get_branch_cashiers(db: Session = Depends(get_db), current_user: User = Depends(get_canteen_admin_user)):
    """Менің филиалымның кассирлері"""
    if not current_user.branch_id:
        raise HTTPException(status_code=400, detail="Сізге филиал тағайындалмаған")

    cashiers = db.query(User).filter(
        User.role == UserRole.CASHIER,
        User.branch_id == current_user.branch_id
    ).all()
    return cashiers


# Статистика
@router.get("/stats/orders")
def get_order_stats(db: Session = Depends(get_db), current_user: User = Depends(get_canteen_admin_user)):
    """Заказ статистикасы"""
    today = datetime.utcnow().date()
    today_orders = db.query(Order).filter(
        Order.created_at >= today,
        Order.created_at < today + timedelta(days=1)
    ).all()

    total_today = len(today_orders)
    revenue_today = sum(order.total_price for order in today_orders)

    return {
        "today_orders": total_today,
        "today_revenue": revenue_today,
        "orders": today_orders
    }
