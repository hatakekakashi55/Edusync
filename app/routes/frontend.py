"""
EduSync Backend - Frontend Routes
Auto-extracted from main.py via AST parser.
"""
import logging
import os
import re
import json
import uuid
import io
import base64
import random
import asyncio
import hashlib
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from pathlib import Path
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str, create_access_token, create_refresh_token
from app.database import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, get_faculty_gemini_model, hod_gemini_model, faculty_gemini_models, AIModelWrapper
from app.lifespan import get_redis_client, get_executor
from app.config import *

# Import all models
from app.models.auth import *
from app.models.challenge import *
from app.models.classroom import *
from app.models.communication import *
from app.models.career import *
from app.models.group import *
from app.models.ai import *
from app.models.hod import *
from app.models.curriculum import *
from app.models.resource import *
from app.models.report import *
from app.models.credit import *
from app.models.compiler import *
from app.models.speech import *
from app.models.faculty import *

# Import helper functions
from app.utils.helpers import *

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Frontend"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return a simple favicon"""
    # Return a simple SVG favicon as bytes
    favicon_svg = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" fill="#4F46E5"/>
  <text x="50" y="70" font-size="60" font-weight="bold" text-anchor="middle" fill="white">E</text>
</svg>"""
    return Response(content=favicon_svg, media_type="image/svg+xml")


@router.get("/", include_in_schema=False)
async def root():
    """Serve landing page at root"""
    return FileResponse("index.html", media_type="text/html")


@router.get("/login", tags=["Frontend"])
async def login_page():
    """Serve login page"""
    return FileResponse("login.html", media_type="text/html")


@router.get("/dashboard", tags=["Frontend"])
async def dashboard_page():
    """Serve student dashboard"""
    return FileResponse("student_dashboard.html", media_type="text/html")


@router.get("/faculty-dashboard", tags=["Frontend"])
async def faculty_dashboard():
    """Serve faculty dashboard"""
    return FileResponse("faculty_dashboard.html", media_type="text/html")


@router.get("/hod-dashboard", tags=["Frontend"])
async def hod_dashboard_page():
    """Serve HOD dashboard"""
    return FileResponse("hod_dashboard.html", media_type="text/html")


@router.get("/profile", tags=["Frontend"])
async def profile_page():
    """Serve profile page"""
    return FileResponse("profile.html", media_type="text/html")


@router.get("/challenges", tags=["Frontend"])
async def challenges_page():
    """Serve challenges page"""
    return FileResponse("Challenges.html", media_type="text/html")


@router.get("/career-prep", tags=["Frontend"])
async def career_prep_page():
    """Serve career prep page"""
    return FileResponse("career_prep.html", media_type="text/html")


@router.get("/learning-path", tags=["Frontend"])
async def learning_path_page():
    """Serve learning path page"""
    return FileResponse("learning path.html", media_type="text/html")


@router.get("/stage/2", tags=["Frontend"])
async def stage_2_page():
    """Serve stage 2 page"""
    return FileResponse("stage 2.html", media_type="text/html")


@router.get("/stage/3", tags=["Frontend"])
async def stage_3_page():
    """Serve stage 3 page"""
    return FileResponse("stage_3.html", media_type="text/html")


@router.get("/communication", tags=["Frontend"])
async def communication_page():
    """Serve communication stage page"""
    return FileResponse("communication_stage.html", media_type="text/html")


@router.get("/static/{file_path:path}")
async def serve_static_file(file_path: str):
    """Serve static files"""
    file_location = f"static/{file_path}"
    if os.path.exists(file_location):
        return FileResponse(file_location)
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/{path:path}", include_in_schema=False)
async def serve_html(path: str):
    """Serve HTML files - Catch-all route"""
    # Explicitly ignore API and Static paths to be safe, though placement at end handles most
    if path.startswith("api/") or path.startswith("static/") or path.startswith("docs") or path.startswith("openapi"):
        return JSONResponse({"error": "Not found"}, status_code=404)

    try:
        # Check if direct path mapping exists
        if f"/{path}" in HTML_FILES:
            file_path = HTML_FILES[f"/{path}"]
        elif path in HTML_FILES:
            file_path = HTML_FILES[path]
        elif path.endswith(".html"):
            file_path = path
        else:
            # Default to login page for root
            if path == "" or path == "/":
                file_path = "index.html"
            else:
                return JSONResponse({"error": "Not found"}, status_code=404)
        
        full_path = os.path.join(os.getcwd(), file_path)
        
        # Security check
        if not os.path.abspath(full_path).startswith(os.path.abspath(os.getcwd())):
            return JSONResponse({"error": "Forbidden"}, status_code=403)
        
        if os.path.exists(full_path):
            return FileResponse(full_path, media_type="text/html")
        else:
            return JSONResponse({"error": f"File not found: {file_path}"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


