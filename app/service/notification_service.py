from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType, NotificationStatus
from datetime import datetime
from typing import List, Optional, Union
import json


class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        notification_type: Union[NotificationType, str] = NotificationType.SYSTEM,
        order_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        data: Optional[dict] = None
    ) -> Notification:
        """Жаңа уведомлениелер жасау"""
        # Convert string to enum if needed
        if isinstance(notification_type, str):
            notification_type = NotificationType[notification_type.upper()]
        
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
            order_id=order_id,
            branch_id=branch_id,
            data=json.dumps(data) if data else None,
            status=NotificationStatus.UNREAD
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        status: Optional[NotificationStatus] = None
    ) -> List[Notification]:
        """Пайдаланушының уведомлениелерін алу"""
        query = db.query(Notification).filter(Notification.user_id == user_id)
        
        if status:
            query = query.filter(Notification.status == status)
        
        return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """Оқылмаған уведомлениелердің саны"""
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.status == NotificationStatus.UNREAD
        ).count()

    @staticmethod
    def mark_as_read(db: Session, notification_id: int) -> Notification:
        """Уведомлениелерді оқығанды белгілеу"""
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.status = NotificationStatus.READ
            notification.read_at = datetime.utcnow()
            db.commit()
            db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        """Барлық уведомлениелерді оқығанды белгілеу"""
        notifications = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.status == NotificationStatus.UNREAD
        ).all()
        
        for notification in notifications:
            notification.status = NotificationStatus.READ
            notification.read_at = datetime.utcnow()
        
        db.commit()
        return len(notifications)

    @staticmethod
    def delete_notification(db: Session, notification_id: int) -> bool:
        """Уведомлениелерді өндіктеу"""
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.status = NotificationStatus.ARCHIVED
            db.commit()
            return True
        return False

    @staticmethod
    def clear_old_notifications(db: Session, user_id: int) -> int:
        """Ескі уведомлениелерді өндіктеу (30 күннен ет)"""
        from datetime import timedelta
        
        old_date = datetime.utcnow() - timedelta(days=30)
        notifications = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.created_at < old_date,
            Notification.status != NotificationStatus.UNREAD
        ).all()
        
        for notification in notifications:
            notification.status = NotificationStatus.ARCHIVED
        
        db.commit()
        return len(notifications)
