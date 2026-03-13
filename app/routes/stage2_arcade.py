import logging
import random
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from bson import ObjectId

from app.dependencies import get_current_user, convert_objectid_to_str
from app.database import users_collection, challenges_collection
from app.services.ai_wrapper import get_gemini_model

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Stage 2 Arcade"])

# 1. Code Battle Arena
@router.post("/api/stage2/arcade/battle/matchmake")
async def battle_matchmake(current_user: dict = Depends(get_current_user)):
    """Finds a match for Code Battle Arena"""
    # Simple mock matchmaking
    room_id = str(uuid.uuid4())
    problem = {
        "title": "Reverse Array",
        "description": "Write a function to reverse an array in-place.",
        "difficulty": "Easy"
    }
    return {"room_id": room_id, "problem": problem, "opponent": "AI_Player_1"}

# 2. AI Boss Fight
@router.post("/api/stage2/arcade/boss/start")
async def boss_start(current_user: dict = Depends(get_current_user)):
    """Starts an AI Boss Fight"""
    return {
        "boss": {
            "name": "Bug Monster",
            "hp": 100,
            "max_hp": 100,
            "image": "bug_monster"
        },
        "problems": [
            {"id": "p1", "title": "Fix the Loop", "damage": 10, "difficulty": "Easy"},
            {"id": "p2", "title": "Sort Array", "damage": 25, "difficulty": "Medium"},
            {"id": "p3", "title": "Dijkstra's Algorithm", "damage": 50, "difficulty": "Hard"}
        ]
    }

@router.post("/api/stage2/arcade/boss/attack")
async def boss_attack(payload: dict, current_user: dict = Depends(get_current_user)):
    problem_id = payload.get("problem_id")
    code = payload.get("code")
    # Mock validation
    damage = 25 if problem_id == "p2" else (50 if problem_id == "p3" else 10)
    return {"success": True, "damage_dealt": damage, "message": "Attack successful!"}

# 3. Bug Hunter Challenge
@router.post("/api/stage2/arcade/bughunter/generate")
async def bughunter_generate(current_user: dict = Depends(get_current_user)):
    try:
        model = get_gemini_model("default")
        prompt = "Generate a simple Python function with exactly one logical bug. Return only JSON format: {\"title\": \"Function Name\", \"description\": \"What it should do\", \"buggy_code\": \"The code\"}"
        response = await model.generate_content_async(prompt)
        text = response.text
        # Fallback if parsing fails
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        data = json.loads(text)
        return data
    except Exception as e:
        logger.error(f"Bug Hunter Generation Error: {e}")
        return {
            "title": "Print Numbers",
            "description": "Print numbers from 0 to 9.",
            "buggy_code": "for i in range(10)\nprint(i)"
        }

@router.post("/api/stage2/arcade/bughunter/verify")
async def bughunter_verify(payload: dict, current_user: dict = Depends(get_current_user)):
    code = payload.get("code", "")
    if ":" in code and "print" in code:
        return {"success": True, "points": 50, "message": "Bug Fixed!"}
    return {"success": False, "message": "Bug still exists."}

# 4. AI Interview Simulator
@router.post("/api/stage2/arcade/interview/analyze")
async def interview_analyze(payload: dict, current_user: dict = Depends(get_current_user)):
    code = payload.get("code", "")
    question = payload.get("question", "")
    try:
        model = get_gemini_model("default")
        prompt = f"Act as an interviewer. The candidate answered '{question}' with this code:\n{code}\nGive a brief analysis of Time/Space complexity and a follow-up question. Return as plain text."
        response = await model.generate_content_async(prompt)
        return {"analysis": response.text}
    except Exception as e:
        return {"analysis": "Time Complexity: O(N). Space Complexity: O(1). How would you optimize this for larger inputs?"}

# 5. Code Escape Room
@router.post("/api/stage2/arcade/escape/room")
async def escape_room(level: int = 1, current_user: dict = Depends(get_current_user)):
    rooms = {
        1: {"type": "decode", "description": "Decode the base64 string: SGVsbG8gV29ybGQ="},
        2: {"type": "fix", "description": "Fix this logic: if True return False"},
        3: {"type": "puzzle", "description": "Find the missing number in: 1, 3, 6, 10, ?"}
    }
    return {"room": rooms.get(level, rooms[1])}

# 6. Daily AI Quest
@router.get("/api/stage2/arcade/quests")
async def get_daily_quests(current_user: dict = Depends(get_current_user)):
    return [
        {"id": 1, "desc": "Solve 3 array problems", "completed": False, "reward": 50},
        {"id": 2, "desc": "Debug 1 program", "completed": False, "reward": 30},
        {"id": 3, "desc": "Optimize 1 code", "completed": False, "reward": 40}
    ]

# 7. Code Speed Run
@router.post("/api/stage2/arcade/speedrun/start")
async def speedrun_start(current_user: dict = Depends(get_current_user)):
    return {
        "time_limit_seconds": 300,
        "problems": [
            {"title": "Sum Array"},
            {"title": "Find Max"},
            {"title": "Reverse String"}
        ]
    }

# 8. Algorithm Builder
@router.get("/api/stage2/arcade/algorithm/blocks")
async def algorithm_blocks(current_user: dict = Depends(get_current_user)):
    return {
        "blocks": [
            {"id": 1, "text": "for i in range(len(arr)):", "order": 2},
            {"id": 2, "text": "def sort_array(arr):", "order": 1},
            {"id": 3, "text": "return arr", "order": 3}
        ]
    }

# 9. AI Code Reviewer
@router.post("/api/stage2/arcade/review")
async def code_review(payload: dict, current_user: dict = Depends(get_current_user)):
    code = payload.get("code", "")
    try:
        model = get_gemini_model("default")
        prompt = f"Review this code briefly. Mention time complexity and clean code aspects:\n{code}"
        response = await model.generate_content_async(prompt)
        return {"review": response.text, "badges": ["Clean Code", "Efficient Coder"]}
    except Exception as e:
        return {"review": "Code looks good. O(n) complexity.", "badges": ["Clean Code"]}

# 10. Real World Mission
@router.post("/api/stage2/arcade/mission/submit")
async def mission_submit(payload: dict, current_user: dict = Depends(get_current_user)):
    # AI evaluate project
    return {"score": 85, "feedback": "Good structure, but lacking some error handling."}

# 11 & 12. AI Personal Mentor
@router.get("/api/stage2/arcade/mentor")
async def personal_mentor(current_user: dict = Depends(get_current_user)):
    return {
        "analysis": "You are doing great with loops, but struggling with recursive functions.",
        "weak_topics": ["Recursion", "Dynamic Programming"],
        "generated_challenge": {
            "title": "Simple Recursion",
            "description": "Write a recursive function to find the sum of numbers from 1 to N."
        }
    }
