from datetime import time, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.models import Order
from app.models.branch import Branch
from app.models.subscription import Subscription, SubscriptionMenu
from app.database.connection import get_db
from app.configuration.security.dependencies import get_owner_user
from app.models.user import User, UserRole
from app.service.restaurant_service import RestaurantService
from app.service.auth_service import AuthService
from app.schemas.restaurant_dto import RestaurantCreate, RestaurantUpdate, AdminAssign
from app.models.food import Food, MenuType

router = APIRouter()


# Ресторандарды басқару
@router.post("/restaurants", status_code=201)
def create_restaurant(
        restaurant: RestaurantCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Жаңа ресторан қосу"""
    return RestaurantService.create_restaurant(db, current_user.id, restaurant)


@router.get("/restaurants")
def get_my_restaurants(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Менің ресторандарым"""
    return RestaurantService.get_owner_restaurants(db, current_user.id)


@router.put("/restaurants/{restaurant_id}")
def update_restaurant(
        restaurant_id: int,
        restaurant: RestaurantUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Ресторанды өзгерту"""
    return RestaurantService.update_restaurant(db, restaurant_id, current_user.id, restaurant)


@router.delete("/restaurants/{restaurant_id}")
def delete_restaurant(
        restaurant_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Ресторанды өшіру"""
    return RestaurantService.delete_restaurant(db, restaurant_id, current_user.id)


@router.post("/restaurants/{restaurant_id}/assign-admin")
def assign_admin_to_restaurant(
        restaurant_id: int,
        admin_data: AdminAssign,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Ресторанға Admin тағайындау"""
    return RestaurantService.assign_admin(db, restaurant_id, current_user.id, admin_data.admin_id)


# Admins басқару
@router.post("/admins", status_code=201)
def create_admin(
        full_name: str,
        email: str,
        password: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Жаңа Admin қосу"""
    # Email-ды тазалау және тексеру
    clean_email = email.strip().lower()

    # Бұл email-дың бар-жоғын тексеру (case-insensitive)
    existing_user = db.query(User).filter(
        User.email.ilike(clean_email)
    ).first()

    if existing_user:
        print(f"Email already exists: {clean_email}, Existing user: {existing_user.email}")
        raise HTTPException(status_code=400, detail=f"Бұл email тіркелген (Қазір: {existing_user.email})")

    hashed_password = AuthService.get_password_hash(password)
    admin = User(
        full_name=full_name,
        email=clean_email,  # Тазартылған email
        hashed_password=hashed_password,
        role=UserRole.ADMIN
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@router.get("/admins")
def get_all_admins(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Барлық Admin-дерді көру"""
    admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
    return admins


@router.delete("/admins/{admin_id}")
def delete_admin(
        admin_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Admin-ді өшіру"""
    admin = db.query(User).filter(User.id == admin_id, User.role == UserRole.ADMIN).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin табылмады")

    db.delete(admin)
    db.commit()
    return {"message": "Admin өшірілді"}


# Жүйе ақпараты
@router.get("/system/info")
def get_system_info(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Жүйе ақпараты"""
    from datetime import datetime
    import platform

    return {
        "version": "1.0.0",
        "database": "PostgreSQL",
        "api": "FastAPI",
        "uptime": "99.9%",
        "server_time": datetime.now().isoformat(),
        "platform": platform.system()
    }


# Мүмкіндіктер
@router.get("/features")
def get_features(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Мүмкіндіктер тізімі"""
    features = [
        {
            "id": 1,
            "name": "QR код сканері",
            "description": "Заказдар үшін QR код генерациясы және сканерлеу",
            "category": "Басты",
            "enabled": True
        },
        {
            "id": 2,
            "name": "Абонементтер",
            "description": "Тұтынушылар үшін абонемент жүйесі",
            "category": "Басты",
            "enabled": True
        },
        {
            "id": 3,
            "name": "Статистика",
            "description": "Күнделікті статистикалық есептер",
            "category": "Аналитика",
            "enabled": True
        },
        {
            "id": 4,
            "name": "Хабарландырулар",
            "description": "Push хабарландырулар жіберу",
            "category": "Коммуникация",
            "enabled": False
        }
    ]
    return features


# Логтар
@router.get("/logs")
def get_logs(
        filter: str = "all",
        db: Session = Depends(get_db),
        current_user: User = Depends(get_owner_user)
):
    """Жүйе логтары"""
    from datetime import datetime, timedelta

    # Қарапайым логтарды генерациялау
    logs = []
    levels = ["info", "warning", "error", "debug"]

    for i in range(50):
        level = levels[i % len(levels)]
        timestamp = datetime.now() - timedelta(hours=i)

        if level == "error":
            message = f"API қатесі: {['orders', 'payments', 'auth'][i % 3]} endpoint"
        elif level == "warning":
            message = f"Ескерту: {['Database connection slow', 'Memory usage high', 'Cache miss'][i % 3]}"
        elif level == "info":
            message = f"Ақпарат: {['User login', 'Order created', 'Payment processed'][i % 3]}"
        else:
            message = f"Debug: {['API request', 'Database query', 'Cache update'][i % 3]}"

        logs.append({
            "level": level,
            "message": message,
            "timestamp": timestamp.isoformat(),
            "details": f"Log entry #{i+1} with {level} level"
        })

    # Фильтрлеу
    if filter != "all":
        logs = [log for log in logs if log["level"] == filter]

    return logs[:20]  # Max 20 logs





class SubscriptionCreate(BaseModel):
    name: str
    description: str | None = None
    price: float
    duration_days: int
    meal_limit: int | None = None

    daily_limit: int | None = None
    allowed_from: time | None = None
    allowed_to: time | None = None
    branch_restriction: bool = False


@router.post("/subscriptions", status_code=201)
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user),
):
    try:
        if data.allowed_from and data.allowed_to:
            if data.allowed_from >= data.allowed_to:
                raise HTTPException(400, "allowed_from < allowed_to болуы керек")

        # GLOBAL абонемент – филиалға байламаймыз
        sub = Subscription(**data.model_dump())

        db.add(sub)
        db.commit()
        db.refresh(sub)

        return sub

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(e)

        raise HTTPException(
            status_code=500,
            detail="Абонемент жасау кезінде қате пайда болды",
        )


@router.get("/subscriptions")
def get_all_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    return db.query(Subscription).all()


@router.put("/subscriptions/{sub_id}")
def update_subscription(
    sub_id: int,
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(404)

    for k, v in data.model_dump().items():
        setattr(sub, k, v)

    db.commit()
    db.refresh(sub)
    return sub


@router.get("/stats/subscription-usage")
def subscription_usage_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    from app.models.order import Order
    from app.models.subscription import Subscription
    from app.models.branch import Branch
    from sqlalchemy import func

    rows = (
        db.query(
            Branch.name.label("branch"),
            Subscription.name.label("subscription"),
            func.count(Order.id).label("orders")
        )
        .join(Order, Order.branch_id == Branch.id)
        .join(Subscription, Subscription.id == Order.subscription_id)
        .filter(Order.paid_by_subscription == True)
        .group_by(Branch.name, Subscription.name)
        .all()
    )

    result = {}
    for r in rows:
        result.setdefault(r.branch, []).append({
            "subscription": r.subscription,
            "orders": r.orders
        })

    return result


@router.get("/subscriptions/{sub_id}/menu")
def get_subscription_menu(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонементке бекітілген тағамдарды алу"""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(404, "Абонемент табылмады")

    from sqlalchemy.orm import joinedload
    menu_items = db.query(SubscriptionMenu).filter(
        SubscriptionMenu.subscription_id == sub_id
    ).options(joinedload(SubscriptionMenu.food)).all()
    
    return [
        {
            "id": item.food.id,
            "name": item.food.name,
            "description": item.food.description,
            "price": item.food.price,
            "menu_type": item.food.menu_type.value if hasattr(item.food.menu_type, "value") else item.food.menu_type
        }
        for item in menu_items
        if item.food
    ]


class AddMenuItemRequest(BaseModel):
    food_id: int


@router.post("/subscriptions/{sub_id}/menu")
def add_food_to_subscription_menu(
    sub_id: int,
    data: AddMenuItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонемент мәзіріне тағам қосу"""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(404, "Абонемент табылмады")
        
    from app.models.food import Food, MenuType
    from app.models.restaurant import Restaurant as RestaurantModel
    
    food = db.query(Food).filter(Food.id == data.food_id).first()
    if not food:
        raise HTTPException(404, "Тағам табылмады")
        
    if food.menu_type == MenuType.SUBSCRIPTION and food.owner_id != current_user.id:
        raise HTTPException(403, "Өзге ресторанның тағамын қосуға болмайды")
    elif food.menu_type == MenuType.REGULAR:
        rest = db.query(RestaurantModel).filter(RestaurantModel.id == food.restaurant_id).first()
        if rest and rest.owner_id != current_user.id:
            raise HTTPException(403, "Өзге ресторанның тағамын қосуға болмайды")

    exists = db.query(SubscriptionMenu).filter(
        SubscriptionMenu.subscription_id == sub_id,
        SubscriptionMenu.food_id == data.food_id
    ).first()
    
    if exists:
        raise HTTPException(400, "Тағам абонементте бар")
        
    new_item = SubscriptionMenu(subscription_id=sub_id, food_id=data.food_id)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return {"message": "Тағам қосылды"}


@router.delete("/subscriptions/{sub_id}/menu/{food_id}")
def remove_food_from_subscription_menu(
    sub_id: int,
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонемент мәзірінен тағамды өшіру"""
    item = db.query(SubscriptionMenu).filter(
        SubscriptionMenu.subscription_id == sub_id,
        SubscriptionMenu.food_id == food_id
    ).first()
    
    if not item:
        raise HTTPException(404, "Мәзірде мұндай тағам жоқ")
        
    db.delete(item)
    db.commit()
    return {"message": "Тағам өшірілді"}


@router.get("/foods")
def get_owner_foods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Owner-дің барлық абонемент тағамдарын алу"""
    print(f"Fetching owner foods for user_id: {current_user.id}")
    
    try:
        foods = db.query(Food).filter(
            Food.owner_id == current_user.id,
            Food.menu_type == MenuType.SUBSCRIPTION
        ).all()
        
        print(f"Found {len(foods)} owner foods")
        
        result = []
        for f in foods:
            m_type = f.menu_type.value if hasattr(f.menu_type, "value") else f.menu_type
            result.append({
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "price": f.price,
                "calories": f.calories,
                "ingredients": f.ingredients,
                "menu_type": m_type
            })
        
        print(f"Successfully serialized {len(result)} foods")
        return result
    except Exception as e:
        print(f"Error in get_owner_foods: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Тағамдарды алу қатесі: {str(e)}")

class CreateSubscriptionFoodRequest(BaseModel):
    name: str
    description: str | None = None
    price: float
    calories: int | None = None
    ingredients: str | None = None

@router.post("/foods", status_code=201)
def create_subscription_food(
    food_data: CreateSubscriptionFoodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонементке арналған жаңа тағам қосу (Глобалды)"""
    from app.models.food import Food, MenuType
    
    food = Food(
        name=food_data.name,
        description=food_data.description,
        price=food_data.price,
        calories=food_data.calories,
        ingredients=food_data.ingredients,
        menu_type=MenuType.SUBSCRIPTION,
        owner_id=current_user.id
    )
    db.add(food)
    db.commit()
    db.refresh(food)
    
    return {
        "id": food.id,
        "name": food.name,
        "description": food.description,
        "price": food.price,
        "calories": food.calories,
        "ingredients": food.ingredients,
        "menu_type": food.menu_type.value
    }

class UpdateSubscriptionFoodRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    calories: int | None = None
    ingredients: str | None = None

@router.put("/foods/{food_id}")
def update_subscription_food(
    food_id: int,
    food_data: UpdateSubscriptionFoodRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонемент тағамын жаңарту"""
    from app.models.food import Food, MenuType
    food = db.query(Food).filter(
        Food.id == food_id,
        Food.owner_id == current_user.id,
        Food.menu_type == MenuType.SUBSCRIPTION
    ).first()
    
    if not food:
        raise HTTPException(404, "Тағам табылмады немесе сізге тиесілі емес")
        
    for k, v in food_data.model_dump(exclude_unset=True).items():
        setattr(food, k, v)
        
    db.commit()
    db.refresh(food)
    
    return {
        "id": food.id,
        "name": food.name,
        "description": food.description,
        "price": food.price,
        "calories": food.calories,
        "ingredients": food.ingredients,
        "menu_type": food.menu_type.value
    }

@router.delete("/foods/{food_id}")
def delete_subscription_food(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонемент тағамын өшіру"""
    from app.models.food import Food, MenuType
    food = db.query(Food).filter(
        Food.id == food_id,
        Food.owner_id == current_user.id,
        Food.menu_type == MenuType.SUBSCRIPTION
    ).first()
    
    if not food:
        raise HTTPException(404, "Тағам табылмады немесе сізге тиесілі емес")
        
    db.delete(food)
    db.commit()
    return {"message": "Тағам өшірілді"}


@router.delete("/subscriptions/{sub_id}")
def delete_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонементті өшіру (деактивация)"""
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(404, "Абонемент табылмады")

    sub.is_active = False
    db.commit()
    return {"message": "Абонемент деактивацияланды"}


# --------------------------
# 📊 SUBSCRIPTION STATS (Owner-only, cross-restaurant)
# Stats aggregate across ALL owner's restaurants by default.
# Pass ?restaurant_id=N to filter to a specific one.
# --------------------------
from datetime import date as date_type
from app.models.restaurant import Restaurant as RestaurantModel


def _get_owner_branch_ids(db: Session, owner_id: int, restaurant_id: int | None = None) -> list[int]:
    """Owner-ға тиесілі барлық филиал ID-лерін алу."""
    q = db.query(Branch.id).join(RestaurantModel, RestaurantModel.id == Branch.restaurant_id)
    q = q.filter(RestaurantModel.owner_id == owner_id)
    if restaurant_id:
        # Ownership check
        restaurant = db.query(RestaurantModel).filter(
            RestaurantModel.id == restaurant_id,
            RestaurantModel.owner_id == owner_id
        ).first()
        if not restaurant:
            raise HTTPException(403, "Бұл ресторан сізге тиесілі емес")
        q = q.filter(Branch.restaurant_id == restaurant_id)
    return [b[0] for b in q.all()]


@router.get("/stats/subscription/overview")
def get_subscription_overview(
    restaurant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонементтер бойынша жалпы статистика (барлық ресторандар немесе бір ресторан)"""
    branch_ids = _get_owner_branch_ids(db, current_user.id, restaurant_id)

    active_subscriptions = db.query(Subscription).filter(Subscription.is_active == True).count()

    today = datetime.utcnow().date()
    today_usage = (
        db.query(func.count(func.distinct(Order.id)))
        .filter(
            Order.branch_id.in_(branch_ids),
            Order.paid_by_subscription == True,
            Order.subscription_id.isnot(None),
            func.date(Order.created_at) == today,
        )
        .scalar()
    ) or 0

    total_subscription_orders = (
        db.query(func.count(func.distinct(Order.id)))
        .filter(
            Order.branch_id.in_(branch_ids),
            Order.paid_by_subscription == True,
            Order.subscription_id.isnot(None),
        )
        .scalar()
    ) or 0

    return {
        "active_subscriptions": active_subscriptions,
        "today_usage": today_usage,
        "total_subscription_orders": total_subscription_orders,
        "branches_included": len(branch_ids),
    }


@router.get("/stats/subscription/daily")
def get_daily_subscription_stats(
    days: int = 7,
    restaurant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Күнделікті абонемент қолдану статистикасы"""
    branch_ids = _get_owner_branch_ids(db, current_user.id, restaurant_id)

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    daily_stats = (
        db.query(
            func.date(Order.created_at).label("date"),
            func.count(func.distinct(Order.id)).label("total_orders"),
            func.count(func.distinct(Order.user_id)).label("total_customers"),
        )
        .filter(
            Order.branch_id.in_(branch_ids),
            Order.paid_by_subscription == True,
            Order.subscription_id.isnot(None),
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at).desc())
        .all()
    )

    return [
        {
            "date": stat.date.isoformat(),
            "total_orders": stat.total_orders,
            "total_customers": stat.total_customers
        }
        for stat in daily_stats
    ]


@router.get("/stats/subscription/by-branch")
def get_subscription_stats_by_branch(
    restaurant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Филиалдар бойынша абонемент статистикасы"""
    branch_ids = _get_owner_branch_ids(db, current_user.id, restaurant_id)
    branches = db.query(Branch).filter(Branch.id.in_(branch_ids)).all()

    result = []
    for branch in branches:
        orders = (
            db.query(Order)
            .filter(
                Order.branch_id == branch.id,
                Order.paid_by_subscription == True,
                Order.subscription_id.isnot(None),
            )
            .all()
        )

        top_subscription = (
            db.query(
                Subscription.name,
                func.count(func.distinct(Order.id)).label("count"),
            )
            .join(Order, Order.subscription_id == Subscription.id)
            .filter(
                Order.branch_id == branch.id,
                Order.paid_by_subscription == True,
            )
            .group_by(Subscription.name)
            .order_by(func.count(func.distinct(Order.id)).desc())
            .first()
        )

        result.append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_orders": len(orders),
            "total_customers": len(set(o.user_id for o in orders)),
            "top_subscription": top_subscription[0] if top_subscription else None,
            "top_subscription_count": top_subscription[1] if top_subscription else 0
        })

    return result


@router.get("/stats/subscription/by-subscription")
def get_subscription_stats_by_type(
    restaurant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонемент түрлері бойынша статистика"""
    branch_ids = _get_owner_branch_ids(db, current_user.id, restaurant_id)

    stats = (
        db.query(
            Subscription.id,
            Subscription.name,
            Subscription.price,
            Subscription.duration_days,
            Subscription.meal_limit,
            func.count(func.distinct(Order.id)).label("total_orders"),
            func.count(func.distinct(Order.user_id)).label("total_users"),
        )
        .join(Order, Order.subscription_id == Subscription.id)
        .filter(
            Order.branch_id.in_(branch_ids),
            Order.paid_by_subscription == True,
        )
        .group_by(
            Subscription.id,
            Subscription.name,
            Subscription.price,
            Subscription.duration_days,
            Subscription.meal_limit,
        )
        .order_by(func.count(func.distinct(Order.id)).desc())
        .all()
    )

    return [
        {
            "subscription_id": stat.id,
            "subscription_name": stat.name,
            "price": stat.price,
            "duration_days": stat.duration_days,
            "meal_limit": stat.meal_limit,
            "total_orders": stat.total_orders,
            "total_users": stat.total_users
        }
        for stat in stats
    ]


class DateRangeRequest(BaseModel):
    start_date: date_type
    end_date: date_type
    branch_id: int | None = None
    subscription_id: int | None = None
    restaurant_id: int | None = None


@router.post("/stats/subscription/custom-range")
def get_subscription_stats_custom_range(
    request: DateRangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Кез келген кезеңдегі абонемент статистикасы"""
    branch_ids = _get_owner_branch_ids(db, current_user.id, request.restaurant_id)

    query = (
        db.query(
            Branch.id.label("branch_id"),
            Branch.name.label("branch_name"),
            Subscription.id.label("subscription_id"),
            Subscription.name.label("subscription_name"),
            func.count(func.distinct(Order.id)).label("total_orders"),
            func.count(func.distinct(Order.user_id)).label("total_customers"),
        )
        .join(Order, Order.branch_id == Branch.id)
        .join(Subscription, Subscription.id == Order.subscription_id)
        .filter(
            Branch.id.in_(branch_ids),
            Order.paid_by_subscription == True,
            func.date(Order.created_at) >= request.start_date,
            func.date(Order.created_at) <= request.end_date,
        )
    )

    if request.branch_id:
        query = query.filter(Branch.id == request.branch_id)
    if request.subscription_id:
        query = query.filter(Subscription.id == request.subscription_id)

    query = query.group_by(
        Branch.id, Branch.name, Subscription.id, Subscription.name
    ).order_by(func.count(Order.id).desc())

    results = query.all()

    return [
        {
            "branch_id": r.branch_id,
            "branch_name": r.branch_name,
            "subscription_id": r.subscription_id,
            "subscription_name": r.subscription_name,
            "total_orders": r.total_orders,
            "total_customers": r.total_customers
        }
        for r in results
    ]


@router.get("/stats/subscription/export")
def export_subscription_stats(
    restaurant_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    """Абонемент статистикасын экспорттау (CSV)"""
    import csv
    from io import StringIO

    branch_ids = _get_owner_branch_ids(db, current_user.id, restaurant_id)

    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.utcnow().date().isoformat()

    stats = (
        db.query(
            func.date(Order.created_at).label("date"),
            Branch.name.label("branch_name"),
            Subscription.name.label("subscription_name"),
            User.full_name.label("user_name"),
            Order.total_price,
        )
        .join(Branch, Branch.id == Order.branch_id)
        .join(Subscription, Subscription.id == Order.subscription_id)
        .join(User, User.id == Order.user_id)
        .filter(
            Order.branch_id.in_(branch_ids),
            Order.paid_by_subscription == True,
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Күні', 'Филиал', 'Абонемент', 'Клиент', 'Заказ сомасы'])
    for stat in stats:
        writer.writerow([
            stat.date,
            stat.branch_name,
            stat.subscription_name,
            stat.user_name,
            stat.total_price,
        ])

    return {
        "csv_data": output.getvalue(),
        "filename": f"subscription_stats_{start_date}_{end_date}.csv",
        "count": len(stats)
    }
