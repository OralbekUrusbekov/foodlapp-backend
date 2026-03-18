from sqlalchemy.orm import Session

from app.models.branch_revenue import BranchRevenue
from app.models.order import Order, OrderItem, OrderStatus
from app.models.food import Food
from app.models.branch import Branch
from app.models.subscription import UserSubscription, Subscription
from fastapi import HTTPException, status
from datetime import datetime, timedelta
import secrets
from config import settings

class OrderService:

    @staticmethod
    def create_order(db: Session, user_id: int, branch_id: int, items: list) -> Order:
        """Жаңа заказ жасау"""
        
        print(f"Creating order - user_id: {user_id}, branch_id: {branch_id}, items: {items}")

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

        # Бір тапсырыста тек бірдей типті тағамдар болуы керек (немесе аралас мәзірді қолдамаймыз ба?)
        # Қосарлы тексеру: барлық тағамдар қолжетімді ме?
        from app.models.food import MenuType
        from app.models.branch_menu import BranchMenu
        
        has_subscription_food = False
        has_regular_food = False

        for item in items:
            print(f"Processing item: {item}")
            # Тарымды осы branch үшін BranchMenu арқылы тексеру
            food_with_menu = db.query(Food, BranchMenu).join(
                BranchMenu, BranchMenu.food_id == Food.id
            ).filter(
                Food.id == item.food_id,
                BranchMenu.branch_id == branch_id,
                BranchMenu.is_available == True
            ).first()

            if not food_with_menu:
                raise HTTPException(
                    status_code=404,
                    detail=f"Тағам ID {item.food_id} табылмады немесе бұл филиалда қолжетімсіз"
                )
                
            food = food_with_menu.Food
            
            if food.menu_type == MenuType.SUBSCRIPTION:
                has_subscription_food = True
            elif food.menu_type == MenuType.REGULAR:
                has_regular_food = True

            item_price = food.price * item.quantity
            total_price += item_price

            order_items_data.append({
                "food_id": food.id,
                "quantity": item.quantity,
                "price": item_price,
                "food_name": food.name
            })
            
        if has_subscription_food and has_regular_food:
            raise HTTPException(
                status_code=400,
                detail="Абонемент тағамдары мен кәдімгі тағамдарды бір тапсырысқа қосуға болмайды"
            )

        # ---------- Subscription ----------
        now = datetime.now() # Use local time for business rules
        
        print(f"Checking subscription for user_id: {user_id} at local time: {now}")

        paid_by_subscription = False
        subscription_id = None
        
        if has_regular_food:
            print("Order contains regular food: Proceeding as paid order (no subscription applied)")
        elif has_subscription_food:
            # Note: end_date is likely stored in UTC if using utcnow default, 
            # but for simplicity we compare with now(). If issues persist, we might need to unify.
            active_subscription = db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.is_active == True,
                UserSubscription.end_date > datetime.utcnow() # end_date is usually UTC
            ).first()

            print(f"Active subscription found: {active_subscription}")

            if not active_subscription:
                 raise HTTPException(
                    status_code=400,
                    detail="Бұл тағамдарды алу үшін белсенді абонемент қажет"
                )

            sub = active_subscription.subscription
            print(f"Subscription details: {sub}")

            from app.models.subscription import SubscriptionMenu
            
            can_use = True
            
            # 0. Menu restriction check
            sub_menu_foods = db.query(SubscriptionMenu.food_id).filter(
                SubscriptionMenu.subscription_id == sub.id
            ).all()
            
            if sub_menu_foods:
                allowed_food_ids = [sf[0] for sf in sub_menu_foods]
                for item in items:
                    if item.food_id not in allowed_food_ids:
                        raise HTTPException(400, detail="Бұл тағам сіздің абонементіңізге кірмейді")

            # 1. Total usage limit check
            if active_subscription.remaining_meals is not None and active_subscription.remaining_meals <= 0:
                raise HTTPException(400, detail="Абонемент бойынша тамақ саны таусылды")
            
            # 2. Daily limit check
            if hasattr(sub, "daily_limit") and sub.daily_limit:
                # Use local day start
                today_start_local = datetime(now.year, now.month, now.day)
                # We need to be careful: if Order.created_at is UTC, we should convert today_start to UTC or compare in UTC.
                # However, for now let's assume if it's within the same 24h block.
                # A better way is to compare with UTC range of the local day.
                # But as a hotfix, let's just use utcnow() for the limit check to stay consistent with DB.
                now_utc = datetime.utcnow()
                today_start_utc = datetime(now_utc.year, now_utc.month, now_utc.day)
                
                today_used = db.query(Order).filter(
                    Order.user_id == user_id,
                    Order.subscription_id == sub.id,
                    Order.created_at >= today_start_utc,
                    Order.paid_by_subscription == True
                ).count()

                if today_used >= sub.daily_limit:
                    raise HTTPException(400, detail=f"Абонементтің күнделікті лимиті ({sub.daily_limit} рет) таусылды")

            # 3. Time window check
            if hasattr(sub, "allowed_from") and sub.allowed_from and sub.allowed_to:
                current_time = now.time() # This is LOCAL time
                if not (sub.allowed_from <= current_time <= sub.allowed_to):
                    raise HTTPException(400, detail=f"Абонемент тек {sub.allowed_from.strftime('%H:%M')} - {sub.allowed_to.strftime('%H:%M')} арасында жұмыс істейді. Қазіргі уақыт: {current_time.strftime('%H:%M')}")

            # If all checks pass
            active_subscription.remaining_meals -= 1
            paid_by_subscription = True
            subscription_id = sub.id
            print("Subscription validated and applied successfully")
        
        if not paid_by_subscription:
            print("Proceeding without subscription (either none found or limits reached)")

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
            subscription_id=subscription_id,
            is_paid=paid_by_subscription
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
    def get_user_order_by_id(db: Session, user_id: int, order_id: int):
        """Қолданушының заказын ID бойынша алу"""
        return db.query(Order).filter(
            Order.id == order_id,
            Order.user_id == user_id
        ).first()
    
    @staticmethod
    def client_verify_qr_code(db: Session, qr_code: str, user_id: int) -> Order:
        """Клиент QR кодты тексеру және қабылдау"""
        order = db.query(Order).filter(Order.qr_code == qr_code).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR код табылмады"
            )
        
        if order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Бұл заказ сіздің емес"
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
        
        if order.status != OrderStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Заказ әлі дайын емес"
            )
        
        # Заказды берілді деп белгілеу
        order.status = OrderStatus.GIVEN
        order.qr_used = True
        
        # Revenue қосу
        revenue = BranchRevenue(
            branch_id=order.branch_id,
            order_id=order.id,
            subscription_id=order.subscription_id,
            user_id=order.user_id,
            amount=order.total_price,
            discount_amount=0,
            final_amount=order.total_price,
        )
        db.add(revenue)
        
        db.commit()
        db.refresh(order)
        return order
    
    @staticmethod
    def generate_order_qr(db: Session, order_id: int, branch_id: int) -> dict:
        """Кассир үшін заказқа арналған QR код генерациялау"""
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.branch_id == branch_id
        ).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ табылмады"
            )
        
        if order.status != OrderStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Тек READY статусы бар заказқа QR код жасауға болады"
            )
        
        # Жаңа QR код генерациялау
        qr_token = secrets.token_urlsafe(32)
        qr_expire = datetime.utcnow() + timedelta(minutes=settings.QR_CODE_EXPIRE_MINUTES)
        
        # Заказды жаңарту
        order.qr_code = qr_token
        order.qr_expire_at = qr_expire
        order.qr_used = False
        
        db.commit()
        db.refresh(order)
        
        return {
            "qr_code": qr_token,
            "expires_at": qr_expire
        }
    
    @staticmethod
    def scan_order_by_qr(db: Session, qr_code: str, user_id: int) -> dict:
        """Клиент QR код сканерлеп заказды алу"""
        order = db.query(Order).filter(Order.qr_code == qr_code).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR код табылмады"
            )
        
        if order.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Бұл заказ сіздің емес"
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
        
        if order.status != OrderStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Заказ әлі дайын емес"
            )
        
        # Заказды берілді деп белгілеу
        order.status = OrderStatus.GIVEN
        order.qr_used = True
        
        # Revenue қосу
        revenue = BranchRevenue(
            branch_id=order.branch_id,
            order_id=order.id,
            subscription_id=order.subscription_id,
            user_id=order.user_id,
            amount=order.total_price,
            discount_amount=0,
            final_amount=order.total_price,
        )
        db.add(revenue)
        
        db.commit()
        db.refresh(order)
        
        return {
            "message": "Заказ сәтті алынды",
            "order": order,
            "status": "success"
        }
    
    @staticmethod
    def accept_order(db: Session, order_id: int) -> Order:
        """Заказды қабылдау"""
        print(f"Looking for order {order_id}")
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            print(f"Order {order_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заказ табылмады"
            )
        
        print(f"Order {order_id} found with status: {order.status}")
        
        # Қабылдауға рұқсат беру (тек Pending емес, кез-келген статус үшін қателіктің алдын алу)
        if order.status == OrderStatus.GIVEN or order.status == OrderStatus.CANCELLED:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Бұл тапсырысты қабылдау мүмкін емес"
            )
        
        order.status = OrderStatus.ACCEPTED
        db.commit()
        db.refresh(order)
        print(f"Order {order_id} accepted successfully")
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

        # Тек белсенді заказды ғана аяқтауға болады
        allowed_statuses = [OrderStatus.ACCEPTED, OrderStatus.COOKING, OrderStatus.READY]
        if order.status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Заказды аяқтау мүмкін емес (статус: {order.status})"
            )

        # Статусты өзгерту
        order.status = OrderStatus.GIVEN  # COMPLETED емес, GIVEN

        revenue = BranchRevenue(
            branch_id=order.branch_id,
            order_id=order.id,
            subscription_id=order.subscription_id,
            user_id=order.user_id,
            amount=order.total_price,
            discount_amount=0,
            final_amount=order.total_price,
        )
        db.add(revenue)

        db.commit()
        db.refresh(order)
        return order

