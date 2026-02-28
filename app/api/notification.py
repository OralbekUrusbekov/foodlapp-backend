from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.configuration.security.dependencies import get_current_user
from app.models.user import User
from app.models.notification import NotificationStatus, Notification
from app.service.notification_service import NotificationService
from app.schemas.notification_dto import NotificationResponse, NotificationListResponse

router = APIRouter()


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Пайдаланушының уведомлениелерін алу"""
    status_enum = None
    if status:
        try:
            status_enum = NotificationStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Жарамсыз статус: {status}"
            )
    
    notifications = NotificationService.get_user_notifications(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        status=status_enum
    )
    
    unread_count = NotificationService.get_unread_count(db, current_user.id)
    
    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                title=n.title,
                message=n.message,
                type=n.type.value,
                status=n.status.value,
                order_id=n.order_id,
                branch_id=n.branch_id,
                created_at=n.created_at,
                read_at=n.read_at
            ) for n in notifications
        ],
        total=len(notifications),
        unread_count=unread_count
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Оқылмаған уведомлениелердің саны"""
    count = NotificationService.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.put("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Бір уведомлениелерді оқығанды белгілеу"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Уведомлениелер табылмады"
        )
    
    result = NotificationService.mark_as_read(db, notification_id)
    return {
        "id": result.id,
        "status": result.status.value,
        "read_at": result.read_at
    }


@router.put("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Барлық уведомлениелерді оқығанды белгілеу"""
    count = NotificationService.mark_all_as_read(db, current_user.id)
    return {"marked_as_read": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Уведомлениелерді өндіктеу"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Уведомлениелер табылмады"
        )
    
    success = NotificationService.delete_notification(db, notification_id)
    return {"deleted": success}


@router.post("/clear-old")
async def clear_old_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ескі уведомлениелерді өндіктеу"""
    count = NotificationService.clear_old_notifications(db, current_user.id)
    return {"cleared": count}


@router.get("/branch/pending")
async def get_branch_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Филиал үшін ұстанған уведомлениелер (кассирлер үшін)"""
    # Find branch where current user is cashier
    from app.models.branch import Branch
    
    branch = db.query(Branch).filter(
        Branch.id == current_user.branch_id,
        Branch.is_active == True
    ).first()
    
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Филиал табылмады"
        )
    
    # Get all unread notifications for this branch
    notifications = db.query(Notification).filter(
        Notification.branch_id == branch.id,
        Notification.status == NotificationStatus.UNREAD,
        Notification.user_id == None  # Broadcast notifications
    ).order_by(Notification.created_at.desc()).all()
    
    return {
        "items": [
            NotificationResponse(
                id=n.id,
                title=n.title,
                message=n.message,
                type=n.type.value,
                status=n.status.value,
                order_id=n.order_id,
                branch_id=n.branch_id,
                created_at=n.created_at,
                read_at=n.read_at
            ) for n in notifications
        ],
        "total": len(notifications)
    }
