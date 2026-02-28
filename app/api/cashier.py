from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.configuration.security.dependencies import get_cashier_user
from app.service.order_service import OrderService
from app.models.user import User
from app.models.order import Order, OrderStatus

router = APIRouter()


@router.post("/orders/{id}/cooking")
def cooking(id: int, db: Session = Depends(get_db)):
    order = db.get(Order, id)
    order.status = OrderStatus.COOKING
    db.commit()
    return order


@router.post("/orders/{id}/ready")
def ready(id: int, db: Session = Depends(get_db)):
    order = db.get(Order, id)
    order.status = OrderStatus.READY
    db.commit()
    return order


@router.post("/orders/{id}/given")
def given(id: int, db: Session = Depends(get_db)):
    order = db.get(Order, id)
    order.status = OrderStatus.GIVEN
    db.commit()
    return order



@router.get("/orders/pending")
def get_pending_orders(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Күтіп тұрған заказдар"""
    orders = db.query(Order).filter(
        Order.status == OrderStatus.PENDING,
        Order.branch_id == current_user.branch_id
    ).all()

    return orders

@router.get("/orders/accepted")
def get_accepted_orders(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Қабылданған заказдар"""
    orders = db.query(Order).filter(Order.status == OrderStatus.ACCEPTED,
                                    Order.branch_id == current_user.branch_id).all()
    return orders

@router.post("/orders/verify-qr/{qr_code}")
def verify_qr(qr_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """QR кодты тексеру"""
    order = OrderService.verify_qr_code(db, qr_code)
    return {
        "valid": True,
        "order": order,
        "message": "QR код жарамды"
    }

@router.post("/orders/{order_id}/accept")
def accept_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Заказды қабылдау"""
    order = OrderService.accept_order(db, order_id)
    return {
        "message": "Заказ қабылданды",
        "order": order
    }

@router.post("/orders/{order_id}/complete")
def complete_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Заказды аяқтау"""
    order = OrderService.complete_order(db, order_id)
    return {
        "message": "Заказ дайын",
        "order": order
    }
