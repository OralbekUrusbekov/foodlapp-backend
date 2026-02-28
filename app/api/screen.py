from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.configuration.security.dependencies import get_current_user
from app.models.order import Order, OrderStatus

router = APIRouter()

@router.get("/screen/orders")
def screen_orders(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    orders = db.query(Order).filter(
        Order.branch_id == current_user.branch_id,
        Order.status.in_([
            OrderStatus.ACCEPTED,
            OrderStatus.COOKING,
            OrderStatus.READY
        ])
    ).all()

    return orders
