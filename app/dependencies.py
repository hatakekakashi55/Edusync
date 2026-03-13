import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from jose import jwt, JWTError

from app.config import SECRET_KEY, ALGORITHM
from app.database import users_collection
from app.utils.auth import (
    verify_password, 
    hash_password, 
    create_access_token, 
    create_refresh_token
)
from app.utils.common import convert_objectid_to_str

logger = logging.getLogger("edusync")

# Security scheme
security = HTTPBearer()

# Global redis_client reference (set during app startup)
redis_client = None

def set_redis_client(client):
    """Set the redis client reference (called during app startup)"""
    global redis_client
    redis_client = client

# ========== CORE JWT DEPENDENCY ==========

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing credentials")
        
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Token is empty")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("email")
        
        if not email or payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type or missing email")
        
        if redis_client is not None:
            try:
                is_blacklisted = await redis_client.exists(f"blacklist:{token}")
                if is_blacklisted:
                    raise HTTPException(status_code=401, detail="Token revoked")
            except Exception as e:
                logger.error(f"Redis check failed: {e}")

        user = await users_collection.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify Token Error: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# Unified dependency for user authentication (Function instead of alias for better stability)
async def get_current_user(user: dict = Depends(verify_token)):
    return user

async def get_current_user_id(user: dict = Depends(get_current_user)):
    return str(user["_id"])

# ========== ROLE BASED DEPENDENCIES ==========

async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("user_type") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

async def require_faculty(current_user: dict = Depends(get_current_user)):
    if current_user.get("user_type") not in ["faculty", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Faculty access required")
    return current_user

async def require_hod(current_user: dict = Depends(get_current_user)):
    if current_user.get("user_type") not in ["hod", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HOD access required")
    return current_user

async def require_student(current_user: dict = Depends(get_current_user)):
    if current_user.get("user_type") != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")
    return current_user
