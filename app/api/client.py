from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
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
from fastapi import File, UploadFile, Form
from app.utils.s3_upload import upload_file_to_s3
from app.models.user import User
from app.models.branch import Branch
from app.configuration.websocket.websocket_server import websocket_manager
from fastapi_cache.decorator import cache
from datetime import datetime
from sqlalchemy.orm import joinedload

router = APIRouter()

# Ресторандар
@router.get("/restaurants")
@cache(expire=300) # 5 минут кеш
async def get_all_restaurants(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Барлық белсенді асханаларды көру"""
    from sqlalchemy.orm import joinedload
    return db.query(Restaurant).options(joinedload(Restaurant.branches)).filter(Restaurant.is_active == True).all()


# Филиалдар
@router.get("/restaurants/{restaurant_id}/branches")
@cache(expire=300)
async def get_branches_by_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_client_user)
):
    return db.query(Branch).filter(
        Branch.restaurant_id == restaurant_id,
        Branch.is_active == True
    ).all()



@router.get("/branch/{branch_id}")
@cache(expire=300)
async def get_branch(branch_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_active == True).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады немесе белсенді емес")
    return branch


@router.get("/branches")
@cache(expire=300)
async def get_all_branches(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Барлық белсенді филиалдарды алу (басты бет үшін)"""
    from sqlalchemy.orm import joinedload
    branches = db.query(Branch).options(joinedload(Branch.restaurant)).filter(Branch.is_active == True).all()
    
    result = []
    for b in branches:
        result.append({
            "id": b.id,
            "name": b.name,
            "address": b.address,
            "phone": b.phone,
            "opening_time": b.opening_time.strftime("%H:%M") if b.opening_time else None,
            "closing_time": b.closing_time.strftime("%H:%M") if b.closing_time else None,
            "restaurant_id": b.restaurant_id,
            "restaurant_name": b.restaurant.name,
            "restaurant_logo": b.restaurant.logo_url
        })
    return result


def check_sub_limit_status(sub_record, db, user_id):
    if not sub_record:
        return False, "NO_SUBSCRIPTION"
        
    now_utc = datetime.utcnow()
    # Today start in UTC (00:00:00 UTC)
    today_start_utc = datetime(now_utc.year, now_utc.month, now_utc.day)
    sub = sub_record.subscription
    
    from app.models.order import Order, OrderStatus
    
    # Debug logging
    print(f"[DEBUG] check_sub_limit_status: user_id={user_id}, today_start_utc={today_start_utc}")
    
    # 1. Total usage limit check
    if sub_record.remaining_meals is not None and sub_record.remaining_meals <= 0:
        print(f"[DEBUG] check_sub_limit_status: MEALS_EXHAUSTED (remaining={sub_record.remaining_meals})")
        return False, "MEALS_EXHAUSTED"
    
    # 2. Daily limit check
    if getattr(sub, "daily_limit", None):
        today_used_query = db.query(Order).filter(
            Order.user_id == user_id,
            Order.subscription_id == sub.id,
            Order.created_at >= today_start_utc,
            Order.paid_by_subscription == True,
            Order.status != OrderStatus.CANCELLED
        )
        today_used = today_used_query.count()
        
        print(f"[DEBUG] check_sub_limit_status: daily_limit={sub.daily_limit}, today_used={today_used}")
        if today_used > 0:
            first_order = today_used_query.first()
            print(f"[DEBUG] check_sub_limit_status: today_order_id={first_order.id}, created_at={first_order.created_at}, status={first_order.status}")

        if today_used >= sub.daily_limit:
            return False, "DAILY_LIMIT_REACHED"

    # 3. Time window check
    if getattr(sub, "allowed_from", None) and getattr(sub, "allowed_to", None):
        from datetime import datetime as dt_local
        now_local = dt_local.now() # Server local time
        current_time = now_local.time()
        if not (sub.allowed_from <= current_time <= sub.allowed_to):
            return False, "OUTSIDE_WINDOW"
            
    return True, "OK"


@router.get("/foods/{branch_id}")
def get_foods(branch_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Филиал бойынша қолжетімді тағамдарды алу"""
    from app.models.food import Food, MenuType
    from app.models.branch_menu import BranchMenu
    from app.models.branch import Branch
    from app.models.restaurant import Restaurant as RestaurantModel
    from app.models.subscription import SubscriptionMenu

    branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_active == True).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады немесе белсенді емес")
        
    restaurant = db.query(RestaurantModel).filter(RestaurantModel.id == branch.restaurant_id).first()
    user_sub = SubscriptionService.get_user_subscription(db, current_user.id)
    allowed_sub_food_ids = []
    can_order_sub = False
    sub_limit_reason = "OK"

    if user_sub:
        can_order_sub, sub_limit_reason = check_sub_limit_status(user_sub, db, current_user.id)
        
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
        ((Food.restaurant_id == restaurant.id) | (Food.owner_id == restaurant.owner_id)),
        Food.menu_type == MenuType.SUBSCRIPTION # Strictly subscription system
    )
    
    if user_sub:
        # Strictly only foods allowed by THIS specific subscription
        query = query.filter(Food.id.in_(allowed_sub_food_ids))
        
    foods = query.all()
    
    return [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "calories": f.calories,
            "ingredients": f.ingredients,
            "image_url": f.image_url or (f.images[0].url if f.images and len(f.images) > 0 else None),
            "menu_type": f.menu_type.value if hasattr(f.menu_type, 'value') else f.menu_type,
            "can_order_sub": can_order_sub and (f.id in allowed_sub_food_ids),
            "sub_limit_reason": sub_limit_reason if (f.id in allowed_sub_food_ids) else "NOT_IN_MENU",
            "branch_id": branch.id,
            "branch_name": branch.name,
            "restaurant_name": restaurant.name
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
    subscription_id: int = Form(...),
    receipt: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_client_user)
):
    """Абонемент сатып алу өтініші (Чекпен бірге)"""
    if not receipt.content_type.startswith("image/") and receipt.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Тек сурет немесе PDF жүктеңіз")
        
    receipt_url = upload_file_to_s3(receipt, receipt.content_type, folder="receipts")
    
    subscription = SubscriptionService.purchase_subscription(
        db, current_user.id, subscription_id, receipt_url
    )
    return subscription

@router.get("/subscriptions/my", response_model=Optional[UserSubscriptionResponse])
def get_my_subscription(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Менің белсенді абонементім"""
    return SubscriptionService.get_latest_user_subscription(db, current_user.id)

@router.post("/subscriptions/cancel")
def cancel_my_subscription(db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Белсенді абонементті тоқтату"""
    return SubscriptionService.cancel_subscription(db, current_user.id)

# Заказдар
@router.post("/orders", status_code=201)
async def create_order(
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
        
        # Кассирге және кезекке хабарлама жіберу (төленген-төленбегеніне қарамастан)
        from app.configuration.websocket.websocket_server import websocket_manager
        await websocket_manager.broadcast_new_order({
            "id": order.id,
            "status": order.status,
            "branch_id": order.branch_id,
            "created_at": order.created_at.isoformat() if hasattr(order.created_at, 'isoformat') else str(order.created_at),
            "is_paid": order.is_paid,
            "user_name": current_user.full_name,
            "items": [{"food_name": i.food.name, "quantity": i.quantity} for i in order.items]
        })
        
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

@router.post("/orders/{order_id}/pay")
async def pay_order(
    order_id: int, 
    receipt: UploadFile = File(...),
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_client_user)
):
    """Заказ үшін төлем жасау (Kaspi чек жүктеу)"""
    from app.models.order import Order
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ табылмады")
        
    if receipt:
        if not receipt.content_type.startswith("image/") and receipt.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Тек сурет немесе PDF жүктеңіз")
        receipt_url = upload_file_to_s3(receipt, receipt.content_type, folder="receipts")
        order.receipt_url = receipt_url
        
    order.is_paid = True
    db.commit()
    db.refresh(order)
    
    # Кассирге статус жаңарғанын хабарлау (төленді)
    from app.configuration.websocket.websocket_server import websocket_manager
    # 1. Срочный обновление (badge және т.б.)
    await websocket_manager.broadcast_order_update({
        "id": order.id,
        "status": order.status,
        "is_paid": order.is_paid,
        "branch_id": order.branch_id,
        "user_id": order.user_id
    })
    # 2. Жаңа тапсырыс ретінде қосу (өйткені бұған дейін кассирде көрінбеді)
    await websocket_manager.broadcast_new_order({
        "id": order.id,
        "status": order.status,
        "branch_id": order.branch_id,
        "created_at": order.created_at.isoformat() if hasattr(order.created_at, 'isoformat') else str(order.created_at),
        "is_paid": order.is_paid,
        "items": [{"food_name": i.food.name, "quantity": i.quantity} for i in order.items]
    })
    
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

async def broadcast_status(order):
    """WebSocket арқылы заказ статусын барлығына хабарлау"""
    await websocket_manager.broadcast_order_update({
        "id": order.id,
        "status": order.status,
        "branch_id": order.branch_id
    })

@router.post("/orders/verify-qr/{qr_code}")
async def client_verify_qr(qr_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Клиент QR кодты тексеру және қабылдау"""
    order = OrderService.client_verify_qr_code(db, qr_code, current_user.id)
    await broadcast_status(order)
    return {
        "message": "Заказ қабылданды",
        "order": order
    }

@router.post("/orders/scan/{qr_code}")
async def scan_order_qr(qr_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_client_user)):
    """Клиент QR код сканерлеу арқылы заказды алу"""
    result = OrderService.scan_order_by_qr(db, qr_code, current_user.id)
    if "order" in result:
        await broadcast_status(result["order"])
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
    
    # Бүх қолжетімді тағамдарды алу (Join арқылы оптимизациялау)
    from sqlalchemy.orm import joinedload
    from app.models.food import Food
    from app.models.branch_menu import BranchMenu
    from app.models.branch import Branch
    from app.models.restaurant import Restaurant as RestaurantModel

    # BranchMenu арқылы Food, Branch және Restaurant-ты бірден алу
    # Бірақ sqlalchemy-де мұндай күрделі join-ды реттеуден көрі, алдымен филиалдар мен ресторандарды кэштеп алған дұрыс
    all_branches = {b.id: b for b in db.query(Branch).filter(Branch.is_active == True).all()}
    all_restaurants = {r.id: r for r in db.query(RestaurantModel).filter(RestaurantModel.is_active == True).all()}
    
    available_branch_menus = db.query(BranchMenu).filter(BranchMenu.is_available == True).all()
    
    if not available_branch_menus:
        return []
        
    user_sub = SubscriptionService.get_user_subscription(db, current_user.id)
    allowed_sub_food_ids = []
    can_order_sub = False
    sub_limit_reason = "OK"
    
    if user_sub:
        can_order_sub, sub_limit_reason = check_sub_limit_status(user_sub, db, current_user.id)
        subs = db.query(SubscriptionMenu.food_id).filter(
            SubscriptionMenu.subscription_id == user_sub.subscription_id
        ).all()
        allowed_sub_food_ids = [s[0] for s in subs]
        
    result = []
    seen_food_ids = set()
    
    # Тағамдарды топтамамен алу (N+1 мәселесін шешу)
    food_ids = [bm.food_id for bm in available_branch_menus]
    all_foods = {f.id: f for f in db.query(Food).options(joinedload(Food.images)).filter(Food.id.in_(food_ids)).all()}
    
    for bm in available_branch_menus:
        if bm.food_id in seen_food_ids:
            continue
            
        food = all_foods.get(bm.food_id)
        if food:
            m_type = food.menu_type.value if hasattr(food.menu_type, 'value') else food.menu_type
            
            # Show all subscription foods to everyone, but filter specific sub foods for subbed users
            if user_sub and food.id not in allowed_sub_food_ids:
                continue
            
            if m_type != "SUBSCRIPTION": # Skip legacy regular foods if any
                continue
            
            branch = all_branches.get(bm.branch_id)
            restaurant = all_restaurants.get(branch.restaurant_id) if branch else None
                
            result.append({
                "id": food.id,
                "name": food.name,
                "description": food.description,
                "image_url": food.image_url or (food.images[0].url if food.images and len(food.images) > 0 else None),
                "menu_type": m_type,
                "branch_id": bm.branch_id,
                "branch_name": branch.name if branch else None,
                "restaurant_name": restaurant.name if restaurant else None,
                "can_order_sub": can_order_sub if user_sub else False,
                "sub_limit_reason": sub_limit_reason if user_sub else "NO_SUBSCRIPTION"
            })
            seen_food_ids.add(food.id)
                
    return result
