from sqlalchemy.orm import Session

from app.models.branch_revenue import BranchRevenue
from app.models.order import Order, OrderItem, OrderStatus
from app.models.food import Food
from app.models.branch import Branch
from app.models.subscription import UserSubscription
from fastapi import HTTPException, status
from datetime import datetime, timedelta
import secrets
from config import settings

class OrderService:

    @staticmethod
    def create_order(db: Session, user_id: int, branch_id: int, items: list) -> Order:
        """Жаңа заказ жасау"""

        # ---------- Branch тексеру ----------
        branch = db.query(Branch).filter(
            Branch.id == branch_id,
            Branch.is_active == True
        ).first()

        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Филиал табылмады немесе белсенді емес"
            )

        # ---------- Foods + price ----------
        total_price = 0
        order_items_data = []

        for item in items:
            food = db.query(Food).filter(
                Food.id == item.food_id,
                Food.branch_id == branch_id,
                Food.is_available == True
            ).first()

            if not food:
                raise HTTPException(
                    status_code=404,
                    detail=f"Тағам ID {item.food_id} табылмады"
                )

            item_price = food.price * item.quantity
            total_price += item_price

            order_items_data.append({
                "food_id": food.id,
                "quantity": item.quantity,
                "price": item_price
            })

        # ---------- Subscription ----------
        now = datetime.utcnow()

        active_subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
            UserSubscription.is_active == True,
            UserSubscription.end_date > now
        ).first()

        paid_by_subscription = False
        subscription_id = None

        if active_subscription:
            sub = active_subscription.subscription

            # ✅ meal limit
            if active_subscription.remaining_meals is not None:
                if active_subscription.remaining_meals <= 0:
                    raise HTTPException(400, "Абонемент лимиті аяқталған")

            # ✅ DAILY LIMIT (егер бар болса)
            if hasattr(sub, "daily_limit") and sub.daily_limit:
                today_start = datetime(now.year, now.month, now.day)

                today_used = db.query(Order).filter(
                    Order.user_id == user_id,
                    Order.subscription_id == sub.id,
                    Order.created_at >= today_start
                ).count()

                if today_used >= sub.daily_limit:
                    raise HTTPException(400, "Күндік лимит бітті")

            # ✅ TIME WINDOW (егер бар болса)
            if hasattr(sub, "allowed_from") and sub.allowed_from and sub.allowed_to:
                if not (sub.allowed_from <= now.time() <= sub.allowed_to):
                    raise HTTPException(400, "Бұл уақытта қолдануға болмайды")

            # ✅ meal decrement
            if active_subscription.remaining_meals is not None:
                active_subscription.remaining_meals -= 1

            # ✅ discount
            if sub.discount_percentage:
                total_price *= (1 - sub.discount_percentage / 100)

            paid_by_subscription = True
            subscription_id = sub.id

        # ---------- QR ----------
        qr_token = secrets.token_urlsafe(32)
        qr_expire = now + timedelta(minutes=settings.QR_CODE_EXPIRE_MINUTES)

        # ---------- Order create ----------
        new_order = Order(
            user_id=user_id,
            branch_id=branch_id,
            total_price=total_price,
            status=OrderStatus.PENDING,
            qr_code=qr_token,
            qr_expire_at=qr_expire,
            paid_by_subscription=paid_by_subscription,
            subscription_id=subscription_id
        )

        db.add(new_order)
        db.flush()

        # ---------- Items ----------
        for item_data in order_items_data:
            db.add(OrderItem(order_id=new_order.id, **item_data))

        db.commit()
        db.refresh(new_order)

        return new_order

    @staticmethod
    def get_user_orders(db: Session, user_id: int):
        """Қолданушының заказдарын алу"""
        return db.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).all()
    
    @staticmethod
    def verify_qr_code(db: Session, qr_code: str) -> Order:
        """QR кодты тексеру"""
        order = db.query(Order).filter(Order.qr_code == qr_code).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR код табылмады"
            )
        
        if order.qr_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR код қолданылған"
            )
        
        if order.qr_expire_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR код мерзімі өткен"
            )
        
        return order
    
    @staticmethod
    def accept_order(db: Session, order_id: int) -> Order:
        """Заказды қабылдау"""
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ табылмады"
            )
        
        if order.status != OrderStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Заказды қабылдау мүмкін емес"
            )
        
        order.status = OrderStatus.ACCEPTED
        order.qr_used = True
        db.commit()
        db.refresh(order)
        return order
    
@staticmethod
def complete_order(db: Session, order_id: int) -> Order:
    """Заказды аяқтау"""
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ табылмады"
        )

    if order.status != OrderStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заказды аяқтау мүмкін емес"
        )

    # Статусты өзгерту
    order.status = OrderStatus.GIVEN  # COMPLETED емес, GIVEN


    discount_amount = 0
    if order.paid_by_subscription and order.subscription:
        discount_amount = order.total_price * (order.subscription.discount_percentage / 100)


    revenue = BranchRevenue(
        branch_id=order.branch_id,
        order_id=order.id,
        subscription_id=order.subscription_id,
        user_id=order.user_id,
        amount=order.total_price,
        discount_amount=discount_amount,
        final_amount=order.total_price - discount_amount
    )
    db.add(revenue)

    db.commit()
    db.refresh(order)
    return order

