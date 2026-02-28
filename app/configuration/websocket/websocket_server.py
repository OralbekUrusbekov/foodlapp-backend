import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from websockets.server import WebSocketServer

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Рөлге байланысты активті WebSocket байланыстар
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "cashier": set(),
            "admin": set(),
            "canteen_admin": set(),
            "owner": set(),
            "client": set()
        }
        # Филиалға байланысты байланыстар
        self.branch_connections: Dict[int, Set[WebSocket]] = {}
        # WebSocket-тің ID-сіне байланысты рөлдер
        self.connection_roles: Dict[str, str] = {}
        # WebSocket-тің ID-сіне байланысты филиалдар
        self.connection_branches: Dict[str, int] = {}

    async def connect(self, websocket: WebSocket, role: str, branch_id: int = None):
        """WebSocket байланысын орнату"""
        await websocket.accept()
        
        # WebSocket-ке уникал ID беру
        connection_id = id(websocket)
        
        # Рөлге байланысты сақтау
        if role not in self.active_connections:
            self.active_connections[role] = set()
        self.active_connections[role].add(websocket)
        self.connection_roles[connection_id] = role
        
        # Филиалға байланысты сақтау
        if branch_id:
            if branch_id not in self.branch_connections:
                self.branch_connections[branch_id] = set()
            self.branch_connections[branch_id].add(websocket)
            self.connection_branches[connection_id] = branch_id
        
        logger.info(f"WebSocket байланысы орнатылды: role={role}, branch_id={branch_id}")
        
        # Қош келдіңіз хабарламасы
        await self.send_personal_message({
            "type": "connection",
            "message": "WebSocket байланысы орнатылды",
            "role": role,
            "branch_id": branch_id
        }, websocket)

    def disconnect(self, websocket: WebSocket):
        """WebSocket байланысын үзу"""
        connection_id = id(websocket)
        role = self.connection_roles.get(connection_id)
        branch_id = self.connection_branches.get(connection_id)
        
        # Рөлден алып тастау
        if role and role in self.active_connections:
            self.active_connections[role].discard(websocket)
        
        # Филиалдан алып тастау
        if branch_id and branch_id in self.branch_connections:
            self.branch_connections[branch_id].discard(websocket)
        
        # ID-лерден алып тастау
        self.connection_roles.pop(connection_id, None)
        self.connection_branches.pop(connection_id, None)
        
        logger.info(f"WebSocket байланысы үзілді: role={role}, branch_id={branch_id}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Жеке хабарлама жіберу"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Жеке хабарлама жіберу қатесі: {e}")

    async def broadcast_to_role(self, message: dict, role: str):
        """Рөлге байланысты барлық байланыстарға хабарлама жіберу"""
        if role not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[role]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Рөлге хабарлама жіберу қатесі: {e}")
                disconnected.add(connection)
        
        # Үзілген байланыстарды жою
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_to_branch(self, message: dict, branch_id: int):
        """Филиалға байланысты барлық байланыстарға хабарлама жіберу"""
        if branch_id not in self.branch_connections:
            return
        
        disconnected = set()
        for connection in self.branch_connections[branch_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Филиалға хабарлама жіберу қатесі: {e}")
                disconnected.add(connection)
        
        # Үзілген байланыстарды жою
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_order_update(self, order_data: dict):
        """Заказ обновлениесі туралы хабарлама жіберу"""
        message = {
            "type": "order_update",
            "data": order_data
        }
        
        # Кассирлерге жіберу
        await self.broadcast_to_role(message, "cashier")
        
        # Админдерге жіберу
        await self.broadcast_to_role(message, "admin")
        await self.broadcast_to_role(message, "canteen_admin")
        
        # Егер филиал белгілі болса, сол филиалға да жіберу
        if "branch_id" in order_data:
            await self.broadcast_to_branch(message, order_data["branch_id"])

    async def broadcast_new_order(self, order_data: dict):
        """Жаңа заказ туралы хабарлама жіберу"""
        message = {
            "type": "new_order",
            "data": order_data
        }
        
        # Кассирлерге жіберу
        await self.broadcast_to_role(message, "cashier")
        
        # Админдерге жіберу
        await self.broadcast_to_role(message, "admin")
        await self.broadcast_to_role(message, "canteen_admin")
        
        # Егер филиал белгілі болса, сол филиалға да жіберу
        if "branch_id" in order_data:
            await self.broadcast_to_branch(message, order_data["branch_id"])

    async def send_notification(self, title: str, message: str, role: str = None, branch_id: int = None, notification_type: str = "system", data: dict = None):
        """Уведомлениелерді жіберу"""
        notification_message = {
            "type": "notification",
            "data": {
                "title": title,
                "message": message,
                "type": notification_type,
                "timestamp": asyncio.get_event_loop().time(),
                **(data or {})
            }
        }
        
        if role:
            # Белгілі рөлге жіберу
            await self.broadcast_to_role(notification_message, role)
        elif branch_id:
            # Белгілі филиалға жіберу
            await self.broadcast_to_branch(notification_message, branch_id)
        else:
            # Барлық құлдарға жіберу
            for role_name in self.active_connections:
                await self.broadcast_to_role(notification_message, role_name)

# Глобалдық WebSocket менеджері
websocket_manager = WebSocketManager()
