from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.user import User
from app.configuration.websocket.websocket_server import websocket_manager
import json
import logging

logger = logging.getLogger(__name__)

# Valid WebSocket roles
VALID_ROLES = ['cashier', 'admin', 'canteen_admin', 'owner', 'client']

router = APIRouter()

@router.websocket("/{role}")
async def websocket_endpoint(
    websocket: WebSocket,
    role: str,
    token: str = None,
    db: Session = Depends(get_db)
):
    """
    WebSocket байланысын орнату
    Рөлдер: cashier, admin, canteen_admin, owner, client
    """
    try:
        # Validate role
        if role not in VALID_ROLES:
            logger.error(f"Жарамсыз рөл: {role}")
            await websocket.close(code=4002, reason="Invalid role")
            return
            
        logger.info(f"WebSocket байланысы сұранысы: role={role}, token={token[:20] if token else 'None'}...")
        
        # Токен арқылы пайдаланушыны тексеру
        user = None
        if token:
            try:
                # Токен тексеру логикасы
                from app.service.auth_service import AuthService
                payload = AuthService.decode_token(token)
                user_id = payload.get("sub")
                user = db.query(User).filter(User.id == user_id).first()
                
                if user:
                    # Verify user role matches requested role
                    if user.role.value != role:
                        logger.error(f"Рөл сәйкес келмейді: user.role={user.role.value}, requested={role}")
                        await websocket.close(code=4003, reason="Role mismatch")
                        return
                        
                    logger.info(f"Пайдаланушы табылды: id={user.id}, role={user.role.value}")
                else:
                    logger.error(f"Пайдаланушы табылмады: user_id={user_id}")
                    await websocket.close(code=4001, reason="User not found")
                    return
                    
            except Exception as e:
                logger.error(f"WebSocket токен тексеру қатесі: {e}")
                await websocket.close(code=4004, reason="Token verification failed")
                return
        else:
            logger.error("Токен жоқ")
            await websocket.close(code=4001, reason="Token required")
            return
        
        # Байланысты орнату
        branch_id = None
        if user and hasattr(user, 'branch_id') and user.branch_id:
            branch_id = user.branch_id
        
        await websocket_manager.connect(websocket, role, branch_id)
        
        # Хабарламаларды тыңдау
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Хабарлама түріне қарай өңдеу
                await handle_websocket_message(websocket, message, user, db)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket хабарлама өңдеу қатесі: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket байланыс қатесі: {e}")
    finally:
        websocket_manager.disconnect(websocket)

async def handle_websocket_message(websocket: WebSocket, message: dict, user: User, db: Session):
    """WebSocket хабарламаларын өңдеу"""
    
    # Validate message structure
    if not isinstance(message, dict) or 'type' not in message:
        logger.error(f"Жарамсыз хабарлама құрылымы: {message}")
        await websocket_manager.send_personal_message({
            "type": "error",
            "message": "Invalid message format"
        }, websocket)
        return
        
    message_type = message.get("type")
    
    if message_type == "ping":
        # Pong жауабы
        await websocket_manager.send_personal_message({
            "type": "pong",
            "timestamp": message.get("timestamp")
        }, websocket)
    
    elif message_type == "order_status_update":
        # Заказ статусін жаңарту
        # Extract from data object (frontend sends data wrapped)
        message_data = message.get("data", {})
        order_id = message_data.get("order_id")
        new_status = message_data.get("status")
        
        # Fallback: check if parameters are directly in message (for compatibility)
        if not order_id:
            order_id = message.get("order_id")
        if not new_status:
            new_status = message.get("status")
        
        # Validate parameters
        if not order_id or not new_status:
            logger.error(f"order_status_update үшін параметрлер жоқ: order_id={order_id}, status={new_status}")
            await websocket_manager.send_personal_message({
                "type": "error",
                "message": "order_id and status are required"
            }, websocket)
            return
            
        # Validate status
        valid_statuses = ['pending', 'accepted', 'completed', 'cancelled']
        if new_status not in valid_statuses:
            logger.error(f"Жарамсыз статус: {new_status}")
            await websocket_manager.send_personal_message({
                "type": "error",
                "message": f"Invalid status. Must be one of: {valid_statuses}"
            }, websocket)
            return
        
        if order_id and new_status:
            try:
                # Заказ статусін жаңарту логикасы
                from app.models.order import Order
                order = db.query(Order).filter(Order.id == order_id).first()
                
                if order:
                    order.status = new_status
                    db.commit()
                    
                    # Барлық байланыстарға хабарлама жіберу
                    await websocket_manager.broadcast_order_update({
                        "id": order.id,
                        "status": order.status,
                        "branch_id": order.branch_id,
                        "updated_by": user.id if user else None
                    })
                    
            except Exception as e:
                logger.error(f"Заказ статусін жаңарту қатесі: {e}")
                await websocket_manager.send_personal_message({
                    "type": "error",
                    "message": "Заказ статусін жаңарту мүмкін болмады"
                }, websocket)
    
    elif message_type == "get_active_orders":
        # Белсенді заказдарды алу
        try:
            from app.models.order import Order
            from sqlalchemy import and_
            
            # Пайдаланушының филиалына қарай заказдарды алу
            query = db.query(Order).filter(
                Order.status.in_(["pending", "accepted"])
            )
            
            if user and hasattr(user, 'branch_id') and user.branch_id:
                query = query.filter(Order.branch_id == user.branch_id)
            
            orders = query.all()
            
            orders_data = []
            for order in orders:
                orders_data.append({
                    "id": order.id,
                    "status": order.status,
                    "total_price": order.total_price,
                    "branch_id": order.branch_id,
                    "created_at": order.created_at.isoformat(),
                    "user_id": order.user_id
                })
            
            await websocket_manager.send_personal_message({
                "type": "active_orders",
                "data": orders_data
            }, websocket)
            
        except Exception as e:
            logger.error(f"Белсенді заказдарды алу қатесі: {e}")
            await websocket_manager.send_personal_message({
                "type": "error",
                "message": "Белсенді заказдарды алу мүмкін болмады"
            }, websocket)

# WebSocket менеджерді экспорттау
__all__ = ["websocket_manager"]
