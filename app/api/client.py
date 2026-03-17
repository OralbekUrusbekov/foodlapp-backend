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


@router.get("/foods/{branch_id}")
def get_foods(branch_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Филиал бойынша қолжетімді тағамдарды алу"""
    from app.models.food import Food, MenuType
    from app.models.branch_menu import BranchMenu
    from app.models.branch import Branch
    from app.models.restaurant import Restaurant as RestaurantModel
    from app.models.subscription import SubscriptionMenu
    from app.models.order import Order
    from datetime import datetime

    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_active == True).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады немесе белсенді емес")
        
    restaurant = db.query(RestaurantModel).filter(RestaurantModel.id == branch.restaurant_id).first()

    user_sub = SubscriptionService.get_user_subscription(db, current_user.id)
    can_order_sub = False
    allowed_sub_food_ids = []
    
    if user_sub:
        now = datetime.now() # Use local time for business window checks
        now_utc = datetime.utcnow()
        sub = user_sub.subscription
        
        can_order_sub = True
        
        # 1. Total usage limit check
        if user_sub.remaining_meals is not None and user_sub.remaining_meals <= 0:
            can_order_sub = False
        
        # 2. Daily limit check
        if can_order_sub and getattr(sub, "daily_limit", None):
            today_start_utc = datetime(now_utc.year, now_utc.month, now_utc.day)
            today_used = db.query(Order).filter(
                Order.user_id == current_user.id,
                Order.subscription_id == sub.id,
                Order.created_at >= today_start_utc,
                Order.paid_by_subscription == True
            ).count()
            if today_used >= sub.daily_limit:
                can_order_sub = False

        # 3. Time window check
        if can_order_sub and getattr(sub, "allowed_from", None) and getattr(sub, "allowed_to", None):
            current_time = now.time()
            if not (sub.allowed_from <= current_time <= sub.allowed_to):
                can_order_sub = False

        # ALWAYS get allowed foods if they have a sub
        subs = db.query(SubscriptionMenu.food_id).filter(
            SubscriptionMenu.subscription_id == user_sub.subscription_id
        ).all()
        allowed_sub_food_ids = [s[0] for s in subs]

    # Base query for foods available at this branch
    query = db.query(Food).join(
        BranchMenu, BranchMenu.food_id == Food.id
    ).filter(
        BranchMenu.branch_id == branch_id,
        BranchMenu.is_available == True,
        ((Food.restaurant_id == restaurant.id) | (Food.owner_id == restaurant.owner_id))
    )
    
    if user_sub:
        query = query.filter(
            (Food.menu_type == MenuType.REGULAR) | 
            (Food.id.in_(allowed_sub_food_ids))
        )
    else:
        query = query.filter(Food.menu_type == MenuType.REGULAR)
        
    foods = query.all()
    
    return [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "price": f.price,
            "calories": f.calories,
            "ingredients": f.ingredients,
            "image_url": f.images[0].url if f.images and len(f.images) > 0 else None,
            "menu_type": f.menu_type.value if hasattr(f.menu_type, 'value') else f.menu_type,
            "can_order_sub": can_order_sub if f.id in allowed_sub_food_ids else True # for regular foods it is always orderable via money
        }
        for f in foods
    ]

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

@router.post("/subscriptions/cancel")
def cancel_my_subscription(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Белсенді абонементті тоқтату"""
    return SubscriptionService.cancel_subscription(db, current_user.id)

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
    from app.models.food import Food
    from app.models.branch_menu import BranchMenu
    from app.service.subscription_service import SubscriptionService
    from app.models.subscription import SubscriptionMenu
    from app.models.order import Order
    from datetime import datetime
    
    # Кездейсоқ немесе кез-келген қолжетімді 8 тағамды алу (Басты бет үшін көрсетілім)
    available_branch_menus = db.query(BranchMenu).filter(BranchMenu.is_available == True).limit(50).all()
    
    if not available_branch_menus:
        return []
        
    user_sub = SubscriptionService.get_user_subscription(db, current_user.id)
    allowed_sub_food_ids = []
    can_order_sub = False
    
    if user_sub:
        now = datetime.now()
        now_utc = datetime.utcnow()
        sub = user_sub.subscription
        
        can_order_sub = True
        
        # 1. Total usage limit check
        if user_sub.remaining_meals is not None and user_sub.remaining_meals <= 0:
            can_order_sub = False
        
        # 2. Daily limit check
        if can_order_sub and getattr(sub, "daily_limit", None):
            today_start_utc = datetime(now_utc.year, now_utc.month, now_utc.day)
            today_used = db.query(Order).filter(
                Order.user_id == current_user.id,
                Order.subscription_id == sub.id,
                Order.created_at >= today_start_utc,
                Order.paid_by_subscription == True
            ).count()
            if today_used >= sub.daily_limit:
                can_order_sub = False

        # 3. Time window check
        if can_order_sub and getattr(sub, "allowed_from", None) and getattr(sub, "allowed_to", None):
            current_time = now.time()
            if not (sub.allowed_from <= current_time <= sub.allowed_to):
                can_order_sub = False

        # ALWAYS get allowed foods if they have a sub
        subs = db.query(SubscriptionMenu.food_id).filter(
            SubscriptionMenu.subscription_id == user_sub.subscription_id
        ).all()
        allowed_sub_food_ids = [s[0] for s in subs]
        
    result = []
    seen_food_ids = set()
    
    for bm in available_branch_menus:
        if len(result) >= 8:
            break
        if bm.food_id not in seen_food_ids:
            food = db.query(Food).filter(Food.id == bm.food_id).first()
            if food:
                m_type = food.menu_type.value if hasattr(food.menu_type, 'value') else food.menu_type
                
                # Subscription тағамдарды тек рұқсат болса ғана қосамыз
                if m_type == "SUBSCRIPTION":
                    # Decoupled visibility from can_order_sub
                    if not user_sub or food.id not in allowed_sub_food_ids:
                        continue
                    
                result.append({
                    "id": food.id,
                    "name": food.name,
                    "description": food.description,
                    "price": food.price,
                    "image_url": food.images[0].url if food.images and len(food.images) > 0 else None,
                    "menu_type": m_type,
                    "branch_id": bm.branch_id,
                    "can_order_sub": can_order_sub if m_type == "SUBSCRIPTION" else True
                })
                seen_food_ids.add(food.id)
                
    return result
