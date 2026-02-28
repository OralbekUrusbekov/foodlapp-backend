import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://10.128.45.163:8000/api/ws/cashier?token=test"
    try:
        async with websockets.connect(uri) as websocket:
            print("WebSocket байланысы орнатылды")
            await websocket.send("ping")
            response = await websocket.recv()
            print(f"Жауап: {response}")
    except Exception as e:
        print(f"WebSocket қатесі: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
