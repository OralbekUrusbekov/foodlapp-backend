from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models import Restaurant
from app.database.connection import get_db
from app.configuration.security.dependencies import get_client_user
from app.service.order_service import OrderService
from app.service.subscription_service import SubscriptionService
from app.service.food_service import FoodService
from app.schemas.order_dto import CreateOrderRequest
from app.schemas.subscription_dto import SubscriptionResponse, UserSubscriptionResponse, PurchaseSubscriptionRequest
from app.schemas.food_dto import FoodResponse
from app.models.user import User
from app.models.branch import Branch

router = APIRouter()

# Филиалдар
@router.get("/restaurants/{restaurant_id}/branches")
def get_branches_by_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_client_user)
):
    return db.query(Branch).filter(
        Branch.restaurant_id == restaurant_id,
        Branch.is_active == True
    ).all()



@router.get("/restaurants")
def get_restaurants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_client_user)
):
    restaurants = db.query(Restaurant).filter(Restaurant.is_active == True).all()
    
    # Әр ресторанға филиалдарды қосу
    result = []
    for restaurant in restaurants:
        branches = db.query(Branch).filter(
            Branch.restaurant_id == restaurant.id,
            Branch.is_active == True
        ).all()
        
        restaurant_data = {
            "id": restaurant.id,
            "name": restaurant.name,
            "description": restaurant.description,
            "logo_url": restaurant.logo_url,
            "is_active": restaurant.is_active,
            "branches": [
                {
                    "id": branch.id,
                    "name": branch.name,
                    "address": branch.address,
                    "phone": branch.phone,
                    "is_active": branch.is_active
                }
                for branch in branches
            ]
        }
        result.append(restaurant_data)
    
    return result


# Тағамдар
@router.get("/foods/{branch_id}", response_model=List[FoodResponse])
def get_foods(branch_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Филиал бойынша тағамдарды көру"""
    foods = FoodService.get_foods_by_branch(db, branch_id)
    return foods

# Абонементтер
@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def get_subscriptions(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Барлық абонементтерді көру"""
    subscriptions = SubscriptionService.get_all_subscriptions(db)
    return subscriptions




@router.post("/subscriptions/purchase", response_model=UserSubscriptionResponse)
def purchase_subscription(
    request: PurchaseSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_client_user)
):
    """Абонемент сатып алу"""
    subscription = SubscriptionService.purchase_subscription(
        db, current_user.id, request.subscription_id
    )
    return subscription

@router.get("/subscriptions/my", response_model=UserSubscriptionResponse)
def get_my_subscription(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Менің белсенді абонементім"""
    subscription = SubscriptionService.get_user_subscription(db, current_user.id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Белсенді абонемент жоқ")
    return subscription

# Заказдар
@router.post("/orders", status_code=201)
def create_order(
    request: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_client_user)
):
    """Жаңа заказ жасау"""
    order = OrderService.create_order(
        db, current_user.id, request.branch_id, request.items
    )
    return order

@router.get("/orders")
def get_my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Менің заказдарым"""
    orders = OrderService.get_user_orders(db, current_user.id)
    return orders

@router.get("/orders/last")
def get_last_order(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Соңғы заказды көру"""
    from app.models.order import Order
    order = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc()).first()
    if not order:
        # 404 орнына 204 қайтару (заказ жоқ - бұл қате емес)
        from fastapi import status
        from fastapi.responses import Response
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return order

@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Нақты заказды көру"""
    from app.models.order import Order
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ табылмады")
    return order

@router.get("/menu/today", response_model=List[FoodResponse])
def get_today_menu(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Бүгінгі мәзірді көру"""
    from datetime import datetime
    from app.models.food import Food
    
    # Бүгінгі күн үшін тағамдарды алу (күнделгі бойынша)
    today = datetime.now().date()
    day_of_week = today.weekday()  # 0=Monday, 6=Sunday
    
    # Қарапайым: дүйсенбі=0, дүйсенбі=1, ... жексенбі=6
    # Демалыс күндері де тағамдар көрсетеміз (тест үшін)
    
    # Жұмыс күндері үшін тағамдарды кездейсоқ таңдау
    foods = db.query(Food).filter(
        Food.is_available == True
    ).limit(8).all()  # Max 8 items for today's menu
    
    return foods
