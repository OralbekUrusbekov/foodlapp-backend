from datetime import time

from fastapi import APIRouter, Depends, HTTPException, logger
from sqlalchemy.orm import Session

from app.models import Order
from app.database.connection import get_db
from app.configuration.security.dependencies import get_owner_user
from app.models.user import User, UserRole
from app.service.restaurant_service import RestaurantService
from app.service.auth_service import AuthService
from app.schemas.restaurant_dto import RestaurantCreate, RestaurantUpdate, AdminAssign

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



from app.models.subscription import Subscription
from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    name: str
    description: str | None = None
    price: float
    duration_days: int
    meal_limit: int | None = None
    discount_percentage: float = 0.0

    daily_limit: int | None = None
    allowed_from: time | None = None
    allowed_to: time | None = None
    branch_restriction: bool = False

@router.post("/subscriptions", status_code=201)
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    try:
        sub = Subscription(**data.model_dump())

        if data.allowed_from and data.allowed_to:
            if data.allowed_from >= data.allowed_to:
                raise HTTPException(400, "allowed_from < allowed_to болуы керек")

        db.add(sub)
        db.commit()
        db.refresh(sub)

        return sub

    except Exception as e:
        db.rollback()
        print(e)


        raise HTTPException(
            status_code=500,
            detail="Абонемент жасау кезінде қате пайда болды"
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



@router.delete("/subscriptions/{sub_id}")
def delete_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        raise HTTPException(404)

    sub.is_active = False
    db.commit()
    return {"message": "Subscription disabled"}

@router.get("/analytics/subscriptions")
def subscription_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_owner_user)
):
    from sqlalchemy import func
    from app.models.order import Order
    from app.models.subscription import Subscription
    from app.models.branch import Branch

    rows = (
        db.query(
            Branch.name,
            Subscription.name,
            func.count(Order.id)
        )
        .join(Order, Order.branch_id == Branch.id)
        .join(Subscription, Subscription.id == Order.subscription_id)
        .filter(Order.paid_by_subscription == True)
        .group_by(Branch.name, Subscription.name)
        .all()
    )

    return rows

@router.get("/analytics/top-subscriptions")
def top_subs(db: Session = Depends(get_db)):
    from sqlalchemy import func

    rows = (
        db.query(
            Subscription.name,
            func.count(Order.id)
        )
        .join(Order)
        .group_by(Subscription.name)
        .order_by(func.count(Order.id).desc())
        .all()
    )

    return rows




