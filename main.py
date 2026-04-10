from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, canteen_admin, cashier, client, notification, owner, websocket, admin, ai
from app.service.order_automation import OrderAutomationService
import logging
import asyncio
from alembic.config import Config
from alembic import command
from config import settings
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis on startup
    try:
        redis = aioredis.from_url("redis://localhost:6379", encoding="utf8", decode_responses=True)
        FastAPICache.init(RedisBackend(redis), prefix="foodlapp-cache")
        logger.info("✅ Redis Caching initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Redis init error (Is redis-server running?): {e}")

    # Start Background Automation Tasks
    asyncio.create_task(OrderAutomationService.auto_complete_stale_orders())
    logger.info("🚀 Order Automation background task started")
    
    yield
    # Cleanup on shutdown

app = FastAPI(lifespan=lifespan)

# Rate limiting configuration
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger = logging.getLogger(__name__)

# CORS configuration
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
app.include_router(ai.router, prefix="/api/ai", tags=["AI Ration"])
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


