from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database.connection import get_db
from app.configuration.security.dependencies import get_cashier_user
from app.service.order_service import OrderService
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.configuration.websocket.websocket_server import websocket_manager
from app.schemas.order_dto import OrderResponse
from typing import List

router = APIRouter()

async def broadcast_status(order: Order):
    """WebSocket арқылы заказ статусын барлығына хабарлау"""
    await websocket_manager.broadcast_order_update({
        "id": order.id,
        "status": order.status,
        "is_paid": order.is_paid,
        "branch_id": order.branch_id,
        "user_id": order.user_id
    })

@router.post("/orders/{id}/cooking", response_model=OrderResponse)
async def cooking(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    order = db.get(Order, id)
    if not order or (current_user.branch_id is not None and order.branch_id != current_user.branch_id):
        raise HTTPException(status_code=404, detail="Заказ табылмады")
    order.status = OrderStatus.COOKING
    db.commit()
    await broadcast_status(order)
    return order

@router.post("/orders/{id}/ready", response_model=OrderResponse)
async def ready(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    order = db.get(Order, id)
    if not order or (current_user.branch_id is not None and order.branch_id != current_user.branch_id):
        raise HTTPException(status_code=404, detail="Заказ табылмады")
    order.status = OrderStatus.READY
    db.commit()
    await broadcast_status(order)
    return order

@router.post("/orders/{id}/given", response_model=OrderResponse)
async def given(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    order = db.get(Order, id)
    if not order or (current_user.branch_id is not None and order.branch_id != current_user.branch_id):
        raise HTTPException(status_code=404, detail="Заказ табылмады")
    order.status = OrderStatus.GIVEN
    db.commit()
    await broadcast_status(order)
    return order


@router.get("/orders/active", response_model=List[OrderResponse])
def get_active_orders(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Барлық белсенді заказдар"""
    query = db.query(Order).options(joinedload(Order.branch), joinedload(Order.items)).filter(
        Order.status.in_([OrderStatus.PENDING, OrderStatus.ACCEPTED, OrderStatus.COOKING, OrderStatus.READY]),
        Order.is_paid == True
    )
    if current_user.branch_id is not None:
        query = query.filter(Order.branch_id == current_user.branch_id)
    return query.all()

@router.get("/orders/history", response_model=List[OrderResponse])
def get_order_history(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Аяқталған және бас тартылған заказдар"""
    query = db.query(Order).options(joinedload(Order.branch), joinedload(Order.items)).filter(
        Order.status.in_([OrderStatus.GIVEN, OrderStatus.CANCELLED])
    )
    if current_user.branch_id is not None:
        query = query.filter(Order.branch_id == current_user.branch_id)
    return query.order_by(Order.created_at.desc()).limit(100).all()

@router.get("/orders/pending", response_model=List[OrderResponse])
def get_pending_orders(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Күтіп тұрған заказдар"""
    query = db.query(Order).options(joinedload(Order.branch), joinedload(Order.items)).filter(
        Order.status == OrderStatus.PENDING,
        Order.is_paid == True
    )
    if current_user.branch_id is not None:
        query = query.filter(Order.branch_id == current_user.branch_id)
    return query.all()

@router.get("/orders/accepted", response_model=List[OrderResponse])
def get_accepted_orders(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Қабылданған заказдар"""
    query = db.query(Order).options(joinedload(Order.branch), joinedload(Order.items)).filter(
        Order.status == OrderStatus.ACCEPTED,
        Order.is_paid == True
    )
    if current_user.branch_id is not None:
        query = query.filter(Order.branch_id == current_user.branch_id)
    return query.all()

@router.post("/orders/verify-qr/{qr_code}")
async def verify_qr(qr_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """QR кодты тексеру"""
    order = OrderService.verify_qr_code(db, qr_code)
    await broadcast_status(order)
    return {
        "valid": True,
        "order": order,
        "message": "QR код жарамды"
    }

@router.post("/orders/{order_id}/accept")
async def accept_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Заказды қабылдау"""
    try:
        print(f"Accepting order {order_id} by cashier {current_user.id}")
        order = OrderService.accept_order(db, order_id)
        await broadcast_status(order)
        return {
            "message": "Заказ қабылданды",
            "order": order
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Accept order error: {e}")
        raise HTTPException(status_code=400, detail=f"Заказды қабылдау қатесі: {str(e)}")

@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Заказды аяқтау"""
    order = OrderService.complete_order(db, order_id)
    await broadcast_status(order)
    return {
        "message": "Заказ дайын",
        "order": order
    }

@router.post("/orders/{order_id}/generate-qr")
def generate_order_qr(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Заказ үшін QR код генерациялау"""
    qr_data = OrderService.generate_order_qr(db, order_id, current_user.branch_id)
    return {
        "message": "QR код сәтті жасалды",
        "qr_code": qr_data["qr_code"],
        "expires_at": qr_data["expires_at"],
        "order_id": order_id
    }
