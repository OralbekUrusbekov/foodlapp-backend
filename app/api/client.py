from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import ValidationError

from app.models import Restaurant
from app.database.connection import get_db
from app.configuration.security.dependencies import get_client_user
from app.service.order_service import OrderService
from app.service.subscription_service import SubscriptionService
from app.service.food_service import FoodService
from app.schemas.order_dto import CreateOrderRequest, OrderResponse
from app.schemas.subscription_dto import SubscriptionResponse, UserSubscriptionResponse, PurchaseSubscriptionRequest
from app.schemas.food_dto import FoodResponse
from app.models.user import User
from app.models.branch import Branch

router = APIRouter()

# Ресторандар
@router.get("/restaurants")
def get_all_restaurants(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Барлық белсенді асханаларды көру"""
    from sqlalchemy.orm import joinedload
    return db.query(Restaurant).options(joinedload(Restaurant.branches)).filter(Restaurant.is_active == True).all()


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



@router.get("/branch/{branch_id}")
def get_branch(branch_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_active == True).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады немесе белсенді емес")
    return branch


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
    try:
        print(f"Received order request: {request}")
        order = OrderService.create_order(
            db, current_user.id, request.branch_id, request.items
        )
        return order
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Валидация қатесі: {e.errors()}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Create order error: {e}")
        print(f"Request data: {request}")
        print(f"User ID: {current_user.id}")
        raise HTTPException(status_code=400, detail=f"Заказ жасау қатесі: {str(e)}")

@router.get("/orders")
def get_my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Менің заказдарым"""
    orders = OrderService.get_user_orders(db, current_user.id)
    return orders

@router.get("/orders/{order_id}")
def get_order_by_id(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Заказды ID бойынша алу"""
    order = OrderService.get_user_order_by_id(db, current_user.id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ табылмады")
    return order

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

@router.post("/orders/verify-qr/{qr_code}")
def client_verify_qr(qr_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Клиент QR кодты тексеру және қабылдау"""
    order = OrderService.client_verify_qr_code(db, qr_code, current_user.id)
    return {
        "message": "Заказ қабылданды",
        "order": order
    }

@router.post("/orders/scan/{qr_code}")
def scan_order_qr(qr_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Клиент QR код сканерлеу арқылы заказды алу"""
    result = OrderService.scan_order_by_qr(db, qr_code, current_user.id)
    return result

@router.get("/menu/today")
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
