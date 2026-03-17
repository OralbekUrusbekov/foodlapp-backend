from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.configuration.security.dependencies import get_cashier_user
from app.service.order_service import OrderService
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.configuration.websocket.websocket_server import websocket_manager

router = APIRouter()

async def broadcast_status(order: Order):
    """WebSocket арқылы заказ статусын барлығына хабарлау"""
    await websocket_manager.broadcast_order_update({
        "id": order.id,
        "status": order.status,
        "branch_id": order.branch_id
    })

@router.post("/orders/{id}/cooking")
async def cooking(id: int, db: Session = Depends(get_db)):
    order = db.get(Order, id)
    order.status = OrderStatus.COOKING
    db.commit()
    await broadcast_status(order)
    return order

@router.post("/orders/{id}/ready")
async def ready(id: int, db: Session = Depends(get_db)):
    order = db.get(Order, id)
    order.status = OrderStatus.READY
    db.commit()
    await broadcast_status(order)
    return order

@router.post("/orders/{id}/given")
async def given(id: int, db: Session = Depends(get_db)):
    order = db.get(Order, id)
    order.status = OrderStatus.GIVEN
    db.commit()
    await broadcast_status(order)
    return order


@router.get("/orders/active")
def get_active_orders(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Барлық белсенді заказдар"""
    orders = db.query(Order).filter(
        Order.status.in_([OrderStatus.PENDING, OrderStatus.ACCEPTED, OrderStatus.COOKING, OrderStatus.READY]),
        Order.branch_id == current_user.branch_id
    ).all()
    return orders

@router.get("/orders/history")
def get_order_history(db: Session = Depends(get_db), current_user: User = Depends(get_cashier_user)):
    """Аяқталған және бас тартылған заказдар"""
    orders = db.query(Order).filter(
        Order.status.in_([OrderStatus.GIVEN, OrderStatus.CANCELLED]),
        Order.branch_id == current_user.branch_id
    ).order_by(Order.created_at.desc()).limit(100).all()
    return orders

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
