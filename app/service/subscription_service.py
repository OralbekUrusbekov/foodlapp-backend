from sqlalchemy.orm import Session
from app.models.subscription import Subscription, UserSubscription
from app.models.user import User
from fastapi import HTTPException, status
from datetime import datetime, timedelta

class SubscriptionService:
    
    @staticmethod
    def get_all_subscriptions(db: Session):
        """Барлық белсенді абонементтерді алу"""
        return db.query(Subscription).filter(Subscription.is_active == True).all()
    
    @staticmethod
    def purchase_subscription(db: Session, user_id: int, subscription_id: int) -> UserSubscription:
        """Абонемент сатып алу"""
        # Абонементті тексеру
        subscription = db.query(Subscription).filter(
            Subscription.id == subscription_id,
            Subscription.is_active == True
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Абонемент табылмады"
            )
        
        # Қолданушыны тексеру
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Қолданушы табылмады"
            )
        
        # Белсенді абонементті тексеру
        active_sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
            UserSubscription.is_active == True,
            UserSubscription.end_date > datetime.utcnow()
        ).first()
        
        if active_sub:
            # Ескі абонементті өшіру
            active_sub.is_active = False
        
        # Жаңа абонемент жасау
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=subscription.duration_days)
        
        new_subscription = UserSubscription(
            user_id=user_id,
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            remaining_meals=subscription.meal_limit,
            is_active=True
        )
        
        db.add(new_subscription)
        db.commit()
        db.refresh(new_subscription)
        return new_subscription
    
    @staticmethod
    def get_user_subscription(db: Session, user_id: int):
        """Қолданушының белсенді абонементін алу"""
        return db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
            UserSubscription.is_active == True,
            UserSubscription.end_date > datetime.utcnow()
        ).first()
