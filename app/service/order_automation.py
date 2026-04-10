import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.order import Order, OrderStatus
from app.models.branch_revenue import BranchRevenue
from app.configuration.websocket.websocket_server import websocket_manager

logger = logging.getLogger(__name__)

class OrderAutomationService:
    @staticmethod
    async def auto_complete_stale_orders():
        """
        Background task to automatically complete orders that have been in 
        pending, accepted, or ready status for more than 1 hour.
        """
        while True:
            try:
                # Run every 10 minutes
                await asyncio.sleep(600)
                
                db: Session = SessionLocal()
                try:
                    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                    
                    # Find orders in non-final statuses created more than 1 hour ago
                    stale_orders = db.query(Order).filter(
                        Order.status.in_([
                            OrderStatus.PENDING, 
                            OrderStatus.ACCEPTED, 
                            OrderStatus.COOKING, 
                            OrderStatus.READY
                        ]),
                        Order.created_at <= one_hour_ago
                    ).all()
                    
                    if not stale_orders:
                        continue
                        
                    logger.info(f"[Automation] Found {len(stale_orders)} stale orders to auto-complete")
                    
                    for order in stale_orders:
                        old_status = order.status
                        order.status = OrderStatus.GIVEN
                        
                        # Record revenue (same as manual completion)
                        revenue = BranchRevenue(
                            branch_id=order.branch_id,
                            order_id=order.id,
                            subscription_id=order.subscription_id,
                            user_id=order.user_id,
                            amount=0.0,
                            discount_amount=0.0,
                            final_amount=0.0,
                        )
                        db.add(revenue)
                        
                        # Broadcast update via WebSocket
                        await websocket_manager.broadcast_order_update({
                            "id": order.id,
                            "status": OrderStatus.GIVEN,
                            "is_paid": order.is_paid,
                            "branch_id": order.branch_id,
                            "user_id": order.user_id,
                            "automation": True
                        })
                        
                        logger.info(f"[Automation] Order #{order.id} auto-completed (was {old_status})")
                    
                    db.commit()
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"[Automation] Error during stale order cleanup: {e}")
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"[Automation] Unexpected error in background loop: {e}")
                await asyncio.sleep(60) # Wait a bit before retrying if loop fails
