from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, canteen_admin, cashier, client, notification, owner, websocket, admin
import logging
from alembic.config import Config
from alembic import command


app = FastAPI()

logger = logging.getLogger(__name__)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(owner.router, prefix="/api/owner", tags=["Owner"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(canteen_admin.router, prefix="/api/canteen-admin", tags=["Canteen Admin"])
app.include_router(cashier.router, prefix="/api/cashier", tags=["Cashier"])
app.include_router(client.router, prefix="/api/client", tags=["Client"])
app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket"])
app.include_router(notification.router, prefix="/api/notifications", tags=["Notifications"])

@app.get("/")
def read_root():
    return {
        "message": "Асхана Абонемент API",
        "docs": "/docs",
        "version": "1.0.0"
    }



@app.get("/health")
def health_check():
    return {"status": "healthy"}


