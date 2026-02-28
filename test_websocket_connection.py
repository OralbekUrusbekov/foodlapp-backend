#!/usr/bin/env python3
"""
WebSocket connection test script
"""
import asyncio
import websockets
import json
from jose import jwt
from datetime import datetime, timedelta

# Test JWT token creation (matching backend settings)
SECRET_KEY = "super_secret_long_random_key_for_canteen_app_2025_oralbek_project_12345"
ALGORITHM = "HS256"

def create_test_token():
    """Create a test JWT token"""
    payload = {
        "sub": "12",  # User ID
        "role": "cashier",  # User role
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def test_websocket_connection():
    """Test WebSocket connection"""
    token = create_test_token()
    ws_url = f"ws://10.251.176.163:8000/api/ws/cashier?token={token}"
    
    try:
        print(f"Connecting to WebSocket: {ws_url}")
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connection established")
            
            # Test ping message
            ping_message = {
                "type": "ping",
                "timestamp": datetime.now().timestamp()
            }
            await websocket.send(json.dumps(ping_message))
            print("📤 Sent ping message")
            
            # Wait for response
            response = await websocket.recv()
            message = json.loads(response)
            print(f"📥 Received: {message}")
            
            # Test get_active_orders
            active_orders_message = {
                "type": "get_active_orders"
            }
            await websocket.send(json.dumps(active_orders_message))
            print("📤 Sent get_active_orders message")
            
            # Wait for orders response
            response = await websocket.recv()
            message = json.loads(response)
            print(f"📥 Received orders: {message}")
            
            print("✅ All tests passed!")
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())
