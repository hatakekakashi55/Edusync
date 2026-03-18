"""
EduSync Backend - Application Lifespan
Startup and shutdown lifecycle management.
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import redis.asyncio as redis

from app.config import REDIS_URL
from app.services.redis_fallback import FakeRedis
from app.database import create_indexes, initialize_sample_data
from app.services.ai_wrapper import gemini_model

logger = logging.getLogger("edusync")

# Global variables
redis_client = None
executor = ThreadPoolExecutor(max_workers=10)


def create_static_dirs():
    """Ensure necessary directories exist"""
    os.makedirs("static/uploads", exist_ok=True)
    os.makedirs("static/processed", exist_ok=True)
    os.makedirs("static/generated", exist_ok=True)


def print_banner():
    """Print startup banner"""
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        # Ignore reconfigure errors on systems that don't support it
        pass
    
    banner = """
    ==============================================================
                     EDU SYNC 4.0 - BACKEND
                 Complete AI-Powered Learning Platform
    ==============================================================
      API Documentation: /api/docs
      API Redoc: /api/redoc
      Health Check: /api/health
    ==============================================================
    """
    print(banner)
    print(f"[>>] Server starting at: http://localhost:8000")
    print(f"[*] API Docs: http://localhost:8000/api/docs")
    try:
        ai_status = '[OK]' if gemini_model else '[X]'
    except NameError:
        ai_status = '[...]'
        
    print(f"[AI] AI Models: Gemini {ai_status}")
    print(f"[DB] Redis: {'[OK]' if redis_client else '[X]'}")
    print("=" * 60)


@asynccontextmanager
async def lifespan(app):
    """Application startup and shutdown lifecycle"""
    global redis_client, executor
    
    # Import here to avoid circular imports
    from app.dependencies import set_redis_client
    
    # Redis Initialization
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.warning(f"⚠️ Real Redis failed: {e}. Switching to In-Memory Fallback.")
        redis_client = FakeRedis()
        logger.info("✅ Redis Fallback (In-Memory) initialized")
    
    # Set redis client in dependencies module
    set_redis_client(redis_client)
    
    # Initialize executor if needed
    if executor is None:
        executor = ThreadPoolExecutor(max_workers=10)
        logger.info("✅ Thread pool executor initialized")
    
    # Create necessary directories
    create_static_dirs()

    # Create indexes
    await create_indexes()
    
    # Initialize sample data
    await initialize_sample_data()
    
    # Print startup banner
    print_banner()
    
    yield
    
    # Shutdown
    if executor:
        executor.shutdown(wait=True)
        logger.info("✅ Thread pool executor shutdown")
    
    from app.database import client
    if client:
        client.close()
        logger.info("✅ MongoDB connection closed")


def get_redis_client():
    """Get the current redis client instance"""
    return redis_client


def get_executor():
    """Get the thread pool executor"""
    return executor
