from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from typing import Optional

from app.database.connection import get_db
from app.configuration.security.dependencies import get_admin_user
from app.models.user import User, UserRole
from app.models.branch import Branch
from app.models.restaurant import Restaurant
from app.models.order import Order, OrderItem
from app.models.subscription import Subscription
from app.service.auth_service import AuthService

router = APIRouter()


# --------------------------
# HELPER: Admin-ға бекітілген ресторанды алу
# --------------------------
def get_admin_restaurant(db: Session, admin_id: int) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.admin_id == admin_id).first()
    if not restaurant:
        raise HTTPException(
            status_code=403,
            detail="Сізге ресторан тағайындалмаған"
        )
    return restaurant


# --------------------------
# BRANCH CRUD (ӨЗГЕРІССІЗ)
# --------------------------
class BranchCreate(BaseModel):
    name: str
    address: str
    phone: str | None = None


@router.post("/branches", status_code=201)
def create_branch(
        branch: BranchCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = db.query(Restaurant).filter(Restaurant.admin_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=403,
            detail="Сізге ресторан тағайындалмаған"
        )

    branch_obj = Branch(
        name=branch.name,
        address=branch.address,
        phone=branch.phone,
        restaurant_id=restaurant.id
    )
    db.add(branch_obj)
    db.commit()
    db.refresh(branch_obj)
    return branch_obj



@router.get("/branches")
def get_my_branches(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)
    branches = db.query(Branch).filter(Branch.restaurant_id == restaurant.id).all()
    return branches


@router.put("/branches/{branch_id}")
def update_branch(
        branch_id: int,
        name: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        is_active: bool | None = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.restaurant_id == restaurant.id
    ).first()

    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады")

    if name: branch.name = name
    if address: branch.address = address
    if phone: branch.phone = phone
    if is_active is not None: branch.is_active = is_active

    db.commit()
    db.refresh(branch)
    return branch


@router.delete("/branches/{branch_id}")
def delete_branch(
        branch_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)
    branch = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.restaurant_id == restaurant.id
    ).first()

    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады")

    db.delete(branch)
    db.commit()
    return {"message": "Филиал өшірілді"}


# --------------------------
# CANTEEN ADMIN CRUD (ӨЗГЕРІССІЗ)
# --------------------------
class CanteenAdminCreate(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str
    branch_id: int


@router.post("/canteen-admins", status_code=201)
def create_canteen_admin(
        admin: CanteenAdminCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)

    branch = db.query(Branch).filter(
        Branch.id == admin.branch_id,
        Branch.restaurant_id == restaurant.id
    ).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Филиал табылмады")

    if db.query(User).filter(User.email == admin.email).first():
        raise HTTPException(status_code=400, detail="Email тіркелген")

    hashed_password = AuthService.get_password_hash(admin.password)
    canteen_admin = User(
        full_name=admin.full_name,
        email=admin.email,
        phone=admin.phone,
        hashed_password=hashed_password,
        role=UserRole.CANTEEN_ADMIN,
        branch_id=admin.branch_id
    )

    db.add(canteen_admin)
    db.commit()
    db.refresh(canteen_admin)
    return canteen_admin


@router.get("/canteen-admins")
def get_canteen_admins(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    admins = db.query(User).filter(
        User.role == UserRole.CANTEEN_ADMIN,
        User.branch_id.in_(branch_ids)
    ).all()
    return admins


@router.delete("/canteen-admins/{admin_id}")
def delete_canteen_admin(
        admin_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    restaurant = get_admin_restaurant(db, current_user.id)

    admin = db.query(User).filter(User.id == admin_id, User.role == UserRole.CANTEEN_ADMIN).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Администратор табылмады")

    branch = db.query(Branch).filter(Branch.id == admin.branch_id).first()
    if not branch or branch.restaurant_id != restaurant.id:
        raise HTTPException(status_code=403, detail="Қол жеткізу рұқсат етілмеген")

    db.delete(admin)
    db.commit()
    return {"message": "Администратор өшірілді"}


# --------------------------
# 📊 SUBSCRIPTION STATS - АБОНЕМЕНТ СТАТИСТИКАСЫ (ЖАҢА)
# --------------------------

class DailySubscriptionUsage(BaseModel):
    date: str
    branch_id: int
    branch_name: str
    subscription_id: int
    subscription_name: str
    total_orders: int
    total_customers: int
    total_discount: float


class BranchSubscriptionSummary(BaseModel):
    branch_id: int
    branch_name: str
    subscription_id: int
    subscription_name: str
    total_orders: int
    total_customers: int
    total_discount: float
    last_used: Optional[str]


class DateRangeRequest(BaseModel):
    start_date: date
    end_date: date
    branch_id: Optional[int] = None
    subscription_id: Optional[int] = None


@router.get("/stats/subscription/overview")
def get_subscription_overview(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    """Абонементтер бойынша жалпы статистика"""
    restaurant = get_admin_restaurant(db, current_user.id)
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    # Барлық белсенді абонементтер
    active_subscriptions = db.query(Subscription).filter(
        Subscription.is_active == True
    ).count()

    # Бүгін қолданылған абонементтер (OrderItem арқылы)
    today = datetime.utcnow().date()
    today_usage = (
        db.query(func.count(func.distinct(Order.id)))
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            Order.branch_id.in_(branch_ids),
            OrderItem.paid_by_subscription == True,
            OrderItem.subscription_id.isnot(None),
            func.date(Order.created_at) == today,
        )
        .scalar()
    )

    # Барлық абонемент арқылы жасалған заказдар (OrderItem-ке join)
    total_subscription_orders = (
        db.query(func.count(func.distinct(Order.id)))
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            Order.branch_id.in_(branch_ids),
            OrderItem.paid_by_subscription == True,
            OrderItem.subscription_id.isnot(None),
        )
        .scalar()
    )

    # Жалпы жеңілдік сомасы (егер discount есептелсе)
    # Бұл үшін BranchRevenue-ге discount поле қосу керек
    total_discount = 0  # Уақытша

    return {
        "active_subscriptions": active_subscriptions,
        "today_usage": today_usage,
        "total_subscription_orders": total_subscription_orders,
        "total_discount": total_discount
    }


@router.get("/stats/subscription/daily")
def get_daily_subscription_stats(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user),
        days: int = 7
):
    """Күнделікті абонемент қолдану статистикасы"""
    restaurant = get_admin_restaurant(db, current_user.id)
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    # Күндер бойынша топтастыру
    daily_stats = (
        db.query(
            func.date(Order.created_at).label("date"),
            func.count(func.distinct(Order.id)).label("total_orders"),
            func.count(func.distinct(Order.user_id)).label("total_customers"),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            Order.branch_id.in_(branch_ids),
            OrderItem.paid_by_subscription == True,
            OrderItem.subscription_id.isnot(None),
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at).desc())
        .all()
    )

    result = []
    for stat in daily_stats:
        result.append({
            "date": stat.date.isoformat(),
            "total_orders": stat.total_orders,
            "total_customers": stat.total_customers
        })

    return result


@router.get("/stats/subscription/by-branch")
def get_subscription_stats_by_branch(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    """Филиалдар бойынша абонемент статистикасы"""
    restaurant = get_admin_restaurant(db, current_user.id)

    # Барлық филиалдар
    branches = db.query(Branch).filter(Branch.restaurant_id == restaurant.id).all()

    result = []
    for branch in branches:
        # Филиалдағы абонемент арқылы жасалған заказдар
        orders = (
            db.query(Order)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .filter(
                Order.branch_id == branch.id,
                OrderItem.paid_by_subscription == True,
                OrderItem.subscription_id.isnot(None),
            )
            .all()
        )

        # Әр филиалдағы ең көп қолданылған абонемент
        top_subscription = (
            db.query(
                Subscription.name,
                func.count(func.distinct(Order.id)).label("count"),
            )
            .join(OrderItem, OrderItem.subscription_id == Subscription.id)
            .join(Order, Order.id == OrderItem.order_id)
            .filter(
                Order.branch_id == branch.id,
                OrderItem.paid_by_subscription == True,
                OrderItem.subscription_id.isnot(None),
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
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    """Абонемент түрлері бойынша статистика"""
    restaurant = get_admin_restaurant(db, current_user.id)
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    # Әр абонемент бойынша статистика
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
        .join(OrderItem, OrderItem.subscription_id == Subscription.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.branch_id.in_(branch_ids),
            OrderItem.paid_by_subscription == True,
            OrderItem.subscription_id.isnot(None),
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

    result = []
    for stat in stats:
        result.append({
            "subscription_id": stat.id,
            "subscription_name": stat.name,
            "price": stat.price,
            "duration_days": stat.duration_days,
            "meal_limit": stat.meal_limit,
            "total_orders": stat.total_orders,
            "total_users": stat.total_users
        })

    return result


@router.post("/stats/subscription/custom-range")
def get_subscription_stats_custom_range(
        request: DateRangeRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    """Кез келген кезеңдегі абонемент статистикасы"""
    restaurant = get_admin_restaurant(db, current_user.id)
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    # Базалық фильтр
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
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Subscription, Subscription.id == OrderItem.subscription_id)
        .filter(
            Branch.id.in_(branch_ids),
            OrderItem.paid_by_subscription == True,
            OrderItem.subscription_id.isnot(None),
            func.date(Order.created_at) >= request.start_date,
            func.date(Order.created_at) <= request.end_date,
        )
    )

    # Фильтрлер
    if request.branch_id:
        query = query.filter(Branch.id == request.branch_id)
    if request.subscription_id:
        query = query.filter(Subscription.id == request.subscription_id)

    # Группировка
    query = query.group_by(
        Branch.id,
        Branch.name,
        Subscription.id,
        Subscription.name
    ).order_by(
        func.count(Order.id).desc()
    )

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
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user),
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
):
    """Абонемент статистикасын экспорттау (CSV)"""
    from datetime import datetime
    import csv
    from io import StringIO

    restaurant = get_admin_restaurant(db, current_user.id)
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    # Кезеңді анықтау
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.utcnow().date().isoformat()

    # Деректерді алу
    stats = (
        db.query(
            func.date(Order.created_at).label("date"),
            Branch.name.label("branch_name"),
            Subscription.name.label("subscription_name"),
            User.full_name.label("user_name"),
            Order.total_price,
        )
        .join(Branch, Branch.id == Order.branch_id)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Subscription, Subscription.id == OrderItem.subscription_id)
        .join(User, User.id == Order.user_id)
        .filter(
            Order.branch_id.in_(branch_ids),
            OrderItem.paid_by_subscription == True,
            OrderItem.subscription_id.isnot(None),
            func.date(Order.created_at) >= start_date,
            func.date(Order.created_at) <= end_date,
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    # CSV генерация
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


# --------------------------
# 📈 REVENUE STATS (ТЕК АБОНЕМЕНТ ҮШІН)
# --------------------------
@router.get("/stats/revenue/subscription")
def get_subscription_revenue(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_admin_user)
):
    """Абонементтерден түскен табыс (егер есептелсе)"""
    restaurant = get_admin_restaurant(db, current_user.id)
    branch_ids = db.query(Branch.id).filter(Branch.restaurant_id == restaurant.id).all()
    branch_ids = [b[0] for b in branch_ids]

    # Бұл жерде BranchRevenue-ден subscription_id бойынша табысты алу керек
    # Қазіргі кезде BranchRevenue-де amount жоқ, тек байланыс қана бар
    # Уақытша 0 қайтарамыз
    return {
        "total_subscription_revenue": 0,
        "monthly_subscription_revenue": 0,
        "daily_subscription_revenue": 0
    }