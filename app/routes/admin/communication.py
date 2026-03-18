import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Form
from app.database import *
from app.dependencies import get_current_user, verify_token

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/admin/communication", tags=["Admin", "Stage 1"])

@router.post("/tasks", tags=["Admin", "Stage 1"])
async def create_communication_task(
    task_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Admin: Create a new communication task"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Validate required fields
        required_fields = ["skill", "title", "content"]
        for field in required_fields:
            if field not in task_data or not task_data[field]:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Create task document with safe None handling
        task_doc = {
            "skill": (task_data.get("skill") or "").strip(),
            "title": (task_data.get("title") or "").strip(),
            "description": (task_data.get("description") or "").strip() or None,
            "content": (task_data.get("content") or "").strip(),
            "difficulty": task_data.get("difficulty", "intermediate"),
            "duration": int(task_data.get("duration", 5)) if task_data.get("duration") else 5,
            "credits": int(task_data.get("credits", 10)) if task_data.get("credits") else 10,
            "instructions": (task_data.get("instructions") or "").strip() or None,
            "example_answer": (task_data.get("example_answer") or "").strip() or None,
            "is_active": task_data.get("is_active", True),
            "created_by": str(current_user.get("_id")),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        logger.info(f"Creating communication task: {task_doc}")
        
        # Insert into database
        result = await communication_tasks_collection.insert_one(task_doc)
        
        task_doc["_id"] = str(result.inserted_id)
        
        logger.info(f"Communication task created with ID: {task_doc['_id']}")
        
        return {
            "success": True,
            "message": "Communication task created successfully",
            "task": task_doc
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating communication task: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", tags=["Admin", "Stage 1"])
async def fetch_communication_tasks(
    skill: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Admin: Fetch communication tasks by skill"""
    if current_user.get("user_type") not in ["admin", "hod"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        # Filter to only get communication tasks (not quiz questions)
        q = {"skill": {"$exists": True}, "quiz_type": {"$exists": False}}
        if skill:
            q["skill"] = {"$in": [skill]}
        tasks = []
        async for t in communication_tasks_collection.find(q).sort("created_at", -1):
            t["_id"] = str(t["_id"])
            tasks.append(t)
        return {"success": True, "tasks": tasks}
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/tasks/{task_id}", tags=["Admin", "Stage 1"])
async def update_communication_task(
    task_id: str,
    task_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Admin: Update communication task"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        from bson import ObjectId
        
        # Update fields
        update_doc = {
            "skill": task_data.get("skill"),
            "title": task_data.get("title"),
            "description": task_data.get("description"),
            "content": task_data.get("content"),
            "difficulty": task_data.get("difficulty"),
            "duration": task_data.get("duration"),
            "credits": task_data.get("credits"),
            "instructions": task_data.get("instructions"),
            "example_answer": task_data.get("example_answer"),
            "is_active": task_data.get("is_active", True),
            "updated_at": datetime.now(timezone.utc)
        }
        
        try:
            result = await communication_tasks_collection.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_doc}
            )
        except:
            result = await communication_tasks_collection.update_one(
                {"_id": task_id},
                {"$set": update_doc}
            )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {"success": True, "message": "Task updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating communication task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{task_id}", tags=["Admin", "Stage 1"])
async def delete_communication_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Admin: Delete communication task"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        from bson import ObjectId
        
        try:
            result = await communication_tasks_collection.delete_one({"_id": ObjectId(task_id)})
        except:
            result = await communication_tasks_collection.delete_one({"_id": task_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {"success": True, "message": "Task deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting communication task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
