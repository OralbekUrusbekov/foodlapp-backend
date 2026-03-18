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

    return [{"name": r[0], "count": r[1]} for r in rows]



# Тағамдарды басқару
@router.get("/foods")
def get_branch_foods(db: Session = Depends(get_db), current_user: User = Depends(get_canteen_admin_user)):
    """Менің филиалымның тағамдары (Кәдімгі + Абонемент)"""
    if not current_user.branch_id:
        raise HTTPException(status_code=400, detail="Сізге филиал тағайындалмаған")

    from app.models.food import Food, MenuType
    from app.models.branch import Branch
    from app.models.restaurant import Restaurant as RestaurantModel
    from app.models.branch_menu import BranchMenu
    
    branch = db.query(Branch).filter(Branch.id == current_user.branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады")
        
    restaurant = db.query(RestaurantModel).filter(RestaurantModel.id == branch.restaurant_id).first()

    # Get all foods applicable to this branch
    # 1. Regular foods created by the Admin for this Restaurant
    # 2. Subscription foods created by the Owner of this Restaurant
    foods = db.query(Food).filter(
        (Food.restaurant_id == restaurant.id) | 
        (Food.owner_id == restaurant.owner_id)
    ).all()
    
    # Get the current branch availability settings
    branch_menus = db.query(BranchMenu).filter(BranchMenu.branch_id == branch.id).all()
    availability_map = {bm.food_id: bm.is_available for bm in branch_menus}
    
    result = []
    for f in foods:
        result.append({
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "price": f.price,
            "calories": f.calories,
            "ingredients": f.ingredients,
            "image_url": f.image_url,
            "menu_type": f.menu_type.value,
            "is_available": availability_map.get(f.id, False) # Default to false if not in BranchMenu
        })
        
    return result

class ToggleFoodRequest(BaseModel):
    is_available: bool

@router.put("/foods/{food_id}/toggle")
def toggle_food_availability(
    food_id: int,
    data: ToggleFoodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_canteen_admin_user)
):
    """Филиалдағы тағамның бүгінгі қолжетімділігін өзгерту"""
    if not current_user.branch_id:
        raise HTTPException(status_code=400, detail="Сізге филиал тағайындалмаған")
        
    from app.models.food import Food
    from app.models.branch_menu import BranchMenu
    from app.models.branch import Branch
    from app.models.restaurant import Restaurant as RestaurantModel
    
    food = db.query(Food).filter(Food.id == food_id).first()
    if not food:
        raise HTTPException(status_code=404, detail="Тағам табылмады")
        
    branch = db.query(Branch).filter(Branch.id == current_user.branch_id).first()
    restaurant = db.query(RestaurantModel).filter(RestaurantModel.id == branch.restaurant_id).first()
    
    # Verify food belongs to this branch's ecosystem
    if food.restaurant_id != restaurant.id and food.owner_id != restaurant.owner_id:
        raise HTTPException(status_code=403, detail="Бұл тағам сіздің филиалға тиесілі емес")
        
    branch_menu = db.query(BranchMenu).filter(
        BranchMenu.branch_id == current_user.branch_id,
        BranchMenu.food_id == food_id
    ).first()
    
    if branch_menu:
        branch_menu.is_available = data.is_available
    else:
        branch_menu = BranchMenu(
            branch_id=current_user.branch_id,
            food_id=food_id,
            is_available=data.is_available
        )
        db.add(branch_menu)
        
    db.commit()
    
    return {"message": "Қолжетімділік жаңартылды", "is_available": data.is_available, "food_id": food_id}


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
        branch_id=current_user.branch_id,
        is_email_verified=True
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
