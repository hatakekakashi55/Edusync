"""
EduSync Backend - Compiler Routes
Modularized and deduplicated.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import traceback
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, Query
from starlette.requests import Request

from app.dependencies import verify_token, convert_objectid_to_str
from app.database import *
from app.models.compiler import CodeExecution
from app.services.compiler_service import CompilerService

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/compiler", tags=["Compiler"])

@router.post("/execute", tags=["Compiler"])
async def execute_code(
    request: Request,
    current_user: dict = Depends(verify_token)
):
    """Execute code in a safe sandbox environment"""
    try:
        # Parse the raw JSON body
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        
        code = body.get("code", "")
        lang = body.get("language", body.get("lang", "python"))
        input_data = body.get("input_data", "")
        test_cases = body.get("test_cases", None)

        logger.info(f"Compiler execute request: language={lang}, code_length={len(code)}")
            
        if not code or not code.strip():
            raise HTTPException(status_code=400, detail="Code is required")
            
        result = await CompilerService.execute_code_safely(
            code=code,
            language=lang,
            input_data=input_data,
            test_cases=test_cases
        )
        
        # Save to history safely
        try:
            history_doc = {
                "user_id": str(current_user["_id"]) if current_user else "unknown",
                "code": code,
                "language": lang,
                "success": result.get("success", False),
                "output": result.get("output", ""),
                "executed_at": datetime.now(timezone.utc)
            }
            if online_compiler_collection is not None:
                await online_compiler_collection.insert_one(history_doc)
        except Exception as db_e:
            logger.warning(f"Failed to save compiler history: {db_e}")
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Compiler execution error: {str(e)}"
        trace = traceback.format_exc()
        logger.error(f"{error_msg}\n{trace}")
        raise HTTPException(
            status_code=500, 
            detail=error_msg
        )

@router.get("/history", tags=["Compiler"])
async def get_compiler_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(verify_token)
):
    """Get user's code execution history"""
    try:
        user_id = str(current_user["_id"])
        history = await online_compiler_collection.find({"user_id": user_id}) \
            .sort("executed_at", -1) \
            .limit(limit) \
            .to_list(limit)
            
        return {
            "success": True,
            "history": convert_objectid_to_str(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
