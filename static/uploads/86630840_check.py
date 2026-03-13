# main.py - EDU SYNC 4.0 - COMPLETE WORKING BACKEND WITH ALL FEATURES
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Query, Body, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Dict, Any, AsyncGenerator, Union
from datetime import datetime, timedelta, timezone
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import jwt
import bcrypt
import os
import uuid
import json
import asyncio
from enum import Enum
import base64
from bson import ObjectId
import secrets
import httpx
import aiofiles
import re
import subprocess
import tempfile
from pathlib import Path
import google.generativeai as genai
import speech_recognition as sr
from gtts import gTTS
import io
import shutil
from collections import defaultdict
import mimetypes
import logging
import qrcode
from io import BytesIO
import cv2
import numpy as np
from PIL import Image
import pdfkit
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import aiohttp
import websockets
import redis.asyncio as redis
from contextlib import asynccontextmanager
import hashlib
import zipfile
import csv
import git
import markdown
from datetime import date
import random
import psutil
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============== CONFIGURATION ===============
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
REFRESH_TOKEN_EXPIRE_DAYS = 30

# AI Configuration - GEMINI FIXED
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyA5Mac7EAFlIx3EMCe1xAQj2Co5ZOwGWw8")
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    logger.info("✅ Gemini AI configured successfully")
except Exception as e:
    logger.warning(f"⚠️ Gemini AI configuration failed: {e}")
    gemini_model = None

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# File Upload Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.mp3', '.mp4', '.txt', '.py', '.java', '.cpp', '.c', '.js', '.html', '.css', '.md', '.json', '.csv', '.xlsx', '.docx'}

# Docker Compiler Configuration - FIXED VERSION
# Docker Compiler Configuration - FIXED VERSION
LANG_CONFIG = {
    "python": {
        "image": "python:3.11-slim",
        "run_cmd": "python {filename}",
        "file_ext": "py",
        "compile_cmd": None
    },
    "javascript": {
        "image": "node:18-slim",
        "run_cmd": "node {filename}",
        "file_ext": "js",
        "compile_cmd": None
    },
    "java": {
        "image": "openjdk:17-slim",
        "compile_cmd": "javac {filename}",
        "run_cmd": "java Main",
        "file_ext": "java",
        "main_class": "Main"
    },
    "c": {
        "image": "gcc:12",
        "compile_cmd": "gcc {filename} -o main",
        "run_cmd": "./main",
        "file_ext": "c"
    },
    "cpp": {
        "image": "gcc:12",
        "compile_cmd": "g++ {filename} -o main",
        "run_cmd": "./main",
        "file_ext": "cpp"
    },
    "go": {
        "image": "golang:1.21",
        "run_cmd": "go run {filename}",
        "file_ext": "go",
        "compile_cmd": None
    },
    "rust": {
        "image": "rust:1.70",
        "compile_cmd": "rustc {filename} -o main",
        "run_cmd": "./main",
        "file_ext": "rs"
    }
}

# Docker resource limits
DOCKER_CPU = "1.0"
DOCKER_MEMORY = "512m"
TIMEOUT_SECONDS = 30

# Global variables
redis_client = None
executor = ThreadPoolExecutor(max_workers=10)

# =============== DATABASE CONNECTION ===============
# =============== DATABASE CONNECTION ===============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global redis_client, executor  # ADDED executor to global
    try:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True, encoding="utf-8")
        await redis_client.ping()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Some features may be limited.")
        redis_client = None
    
    # Initialize executor if needed
    if executor is None:  # ADDED
        executor = ThreadPoolExecutor(max_workers=10)
        logger.info("✅ Thread pool executor initialized")
    
    # Create indexes
    await create_indexes()
    
    # Initialize sample data
    await initialize_sample_data()
    
    # Print startup banner
    print_banner()
    
    yield
    
    # Shutdown
    if redis_client:
        await redis_client.close()
        logger.info("✅ Redis connection closed")
    
    # Shutdown executor
    if executor:  # ADDED
        executor.shutdown(wait=True)
        logger.info("✅ Thread pool executor shutdown")
    
    # MongoDB client is closed automatically
    if client:
        client.close()

# =============== INITIALIZE APP ===============
app = FastAPI(
    title="EduSync Campus Learning Platform 4.0",
    version="4.0.0",
    description="Complete AI-Powered Learning Ecosystem with GitHub-like Collaboration",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Mount static files
os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/qr_codes", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============== DATABASE CONFIGURATION ===============
# MongoDB Connection
try:
    client = AsyncIOMotorClient("mongodb://localhost:27017", maxPoolSize=100, minPoolSize=10)
    db = client.edusync_v4
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise

# Collections
users_collection = db.users
challenges_collection = db.challenges
files_collection = db.files  # இந்த line-ஐ சேர்க்கவும்
submissions_collection = db.submissions
groups_collection = db.groups
messages_collection = db.messages
files_collection = db.files
leaderboard_collection = db.leaderboard
badges_collection = db.badges
projects_collection = db.projects
interviews_collection = db.interviews
jobs_collection = db.jobs
notifications_collection = db.notifications
certificates_collection = db.certificates
crew_battles_collection = db.crew_battles
analytics_collection = db.analytics
online_compiler_collection = db.online_compiler
exams_collection = db.exams
announcements_collection = db.announcements
study_materials_collection = db.study_materials
classrooms_collection = db.classrooms
ai_chats_collection = db.ai_chats
coding_challenges_collection = db.coding_challenges
quiz_collection = db.quizzes
assignment_collection = db.assignments
attendance_collection = db.attendance
events_collection = db.events
courses_collection = db.courses
payments_collection = db.payments
feedback_collection = db.feedback
resume_collection = db.resumes
code_repositories_collection = db.code_repositories
code_commits_collection = db.code_commits
ai_code_assistance_collection = db.ai_code_assistance
code_reviews_collection = db.code_reviews
version_control_collection = db.version_control
pair_programming_collection = db.pair_programming
technical_docs_collection = db.technical_docs
ai_tutor_sessions_collection = db.ai_tutor_sessions
learning_paths_collection = db.learning_paths
forum_posts_collection = db.forum_posts
forum_comments_collection = db.forum_comments

# =============== SECURITY ===============
security = HTTPBearer()

# =============== MODELS ===============
# =============== MODELS ===============
class MongoDBModel(BaseModel):
    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }

class UserType(str, Enum):
    STUDENT = "student"
    STAFF = "staff"
    # ... மற்ற வகுப்புகள் (other classes)
class UserType(str, Enum):
    STUDENT = "student"
    STAFF = "staff"
    HOD = "hod"
    ADMIN = "admin"
    PARENT = "parent"
    ALUMNI = "alumni"
    RECRUITER = "recruiter"
    GUEST = "guest"

class Stage(str, Enum):
    FRESHIE = "freshie"
    SOPHOMORE = "sophomore"
    JUNIOR = "junior"
    FINAL_YEAR = "final_year"
    ALUMNI = "alumni"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    user_type: UserType
    department: Optional[str] = None
    year: Optional[int] = Field(None, ge=1, le=5)
    roll_number: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    parent_email: Optional[EmailStr] = None
    parent_phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    device_info: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    weak_areas: Optional[List[str]] = None
    career_goals: Optional[List[str]] = None

class ChallengeCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    stage: Stage
    challenge_type: str = Field(..., pattern="^(voice|coding|quiz|project|writing|presentation)$")
    difficulty: Difficulty
    credits_reward: int = Field(..., ge=10, le=1000)
    time_limit: Optional[int] = Field(None, ge=1, le=300)
    media_url: Optional[str] = None
    code_template: Optional[str] = None
    correct_text: Optional[str] = None
    language: Optional[str] = "python"
    tags: Optional[List[str]] = []
    requirements: Optional[List[str]] = []
    test_cases: Optional[List[Dict]] = []
    correct_answer: Optional[str] = None

class InterviewRequest(BaseModel):
    company: str
    role: str
    difficulty: Difficulty = Difficulty.MEDIUM
    duration: int = Field(15, ge=5, le=60)
    interview_type: str = Field("technical", pattern="^(technical|hr|mixed)$")

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    department: str
    year: int = Field(..., ge=1, le=5)
    is_educational: bool = True
    max_members: int = Field(100, ge=2, le=500)
    privacy: str = Field("public", pattern="^(public|private|invite_only)$")

class MessageSend(BaseModel):
    group_id: str
    content: str = Field(..., min_length=1, max_length=2000)
    message_type: str = Field("text", pattern="^(text|file|image|audio|video|code)$")
    reply_to: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None

class CodeExecution(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field("python", pattern="^(python|javascript|java|c|cpp|go|rust)$")
    input_data: Optional[str] = ""
    test_cases: Optional[List[Dict[str, Any]]] = None

# In Pydantic models section (around line 340)
class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    project_type: str = Field(..., pattern="^(academic|research|hackathon|startup|personal)$")
    tech_stack: List[str] = []
    github_repo: Optional[str] = None
    website: Optional[str] = None
    tags: List[str] = []
    required_skills: List[str] = []
    timeline_days: int = Field(30, ge=1, le=365)
    # ADD THIS LINE for attachments
    attachments: Optional[List[str]] = []

class ExamCreate(BaseModel):
    title: str
    subject: str
    duration_minutes: int = Field(60, ge=10, le=300)
    questions: List[Dict[str, Any]]
    department: str
    year: int
    passing_score: int = Field(40, ge=0, le=100)
    max_attempts: int = Field(1, ge=1, le=10)
    instructions: Optional[str] = None

class AIChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = None
    chat_history_id: Optional[str] = None

class QuizCreate(BaseModel):
    title: str
    subject: str
    questions: List[Dict[str, Any]]
    time_per_question: int = Field(30, ge=10, le=300)
    difficulty: Difficulty
    tags: List[str] = []

class AssignmentCreate(BaseModel):
    title: str
    description: str
    classroom_id: str
    due_date: str
    max_score: int = Field(100, ge=1, le=1000)
    submission_type: str = Field("file", pattern="^(file|text|code|link)$")
    attachments: Optional[List[str]] = []

class CourseCreate(BaseModel):
    title: str
    description: str
    instructor_id: str
    department: str
    year: int
    credits: int = Field(3, ge=1, le=10)
    duration_weeks: int = Field(12, ge=1, le=52)
    syllabus: List[Dict[str, Any]] = []
    prerequisites: List[str] = []

# New Models for Advanced Features
class CodeRepositoryCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    project_id: Optional[str] = None
    is_public: Optional[bool] = True  # Changed to Optional
    language: str = Field("python", pattern="^(python|javascript|java|c|cpp|go|rust|typescript)$")
    
    # Add validator for language
    @validator('language')
    def validate_language(cls, v):
        v = v.lower()
        valid_languages = ['python', 'javascript', 'java', 'c', 'cpp', 'go', 'rust', 'typescript']
        if v not in valid_languages:
            raise ValueError(f'Language must be one of: {", ".join(valid_languages)}')
        return v

class CommitCreate(BaseModel):
    repository_id: str
    message: str = Field(..., min_length=3, max_length=200)
    files: List[Dict[str, Any]] = []
    branch: str = "main"

class CodeReviewRequest(BaseModel):
    code: str
    language: str
    context: Optional[str] = None
    requirements: Optional[List[str]] = None

class AICodeHelpRequest(BaseModel):
    code: Optional[str] = None
    error: Optional[str] = None
    requirement: Optional[str] = None
    language: str = "python"
    context: Optional[str] = None

class PairProgrammingRequest(BaseModel):
    partner_id: str
    language: str = "python"
    session_duration: int = Field(30, ge=10, le=120)

class LearningPathRequest(BaseModel):
    user_id: str
    focus_areas: List[str]
    duration_days: int = Field(30, ge=7, le=365)
    goals: List[str] = []

class ForumPostCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=10, max_length=5000)
    tags: List[str] = []
    category: str = Field(..., pattern="^(question|discussion|help|announcement|project)$")
    is_anonymous: bool = False

class ForumCommentCreate(BaseModel):
    post_id: str
    content: str = Field(..., min_length=1, max_length=1000)
    parent_comment_id: Optional[str] = None

# =============== HELPER FUNCTIONS ===============
# =============== HELPER FUNCTIONS ===============
def convert_objectid_to_str(document):
    """Convert MongoDB ObjectId to string and handle nested documents"""
    if document is None:
        return None
    
    if isinstance(document, list):
        return [convert_objectid_to_str(item) for item in document]
    
    if isinstance(document, dict):
        result = {}
        for key, value in document.items():
            if key == '_id' and isinstance(value, ObjectId):
                result[key] = str(value)
            elif key == 'id' and isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = convert_objectid_to_str(value)
            elif isinstance(value, list):
                result[key] = convert_objectid_to_str(value)
            else:
                result[key] = value
        return result
    
    return document
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user = await users_collection.find_one({"email": payload.get("email")})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Check if token is blacklisted
        if redis_client and await redis_client.exists(f"blacklist:{token}"):
            raise HTTPException(status_code=401, detail="Token revoked")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user_id(current_user: dict = Depends(verify_token)):
    return str(current_user["_id"])

def hash_password(password: str):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

async def validate_file(file: UploadFile):
    # Check file size
    content = await file.read()
    file_size = len(content)
    await file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    return content, file_size

async def generate_qr_code(data: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return buffer.getvalue()

async def send_email_async(to_email: str, subject: str, body: str):
    # This is a placeholder for actual email sending
    logger.info(f"Email sent to {to_email}: {subject}")
    return True

async def send_sms_async(phone: str, message: str):
    # Placeholder for SMS service
    logger.info(f"SMS sent to {phone}: {message}")
    return True

async def upload_to_cloud_storage(file_content: bytes, filename: str, content_type: str):
    # Save locally (for development)
    file_id = str(uuid.uuid4())
    file_ext = Path(filename).suffix.lower()
    safe_filename = f"{file_id}{file_ext}"
    file_path = f"uploads/{safe_filename}"
    
    os.makedirs(os.path.dirname(f"static/{file_path}"), exist_ok=True)
    with open(f"static/{file_path}", "wb") as f:
        f.write(file_content)
    
    return {
        "url": f"/static/{file_path}",
        "file_id": file_id,
        "filename": safe_filename
    }

# =============== AI SERVICES ===============
class AIService:
    @staticmethod
    async def analyze_english_with_gemini(user_text: str, correct_text: str) -> Dict:
        try:
            if gemini_model is None:
                raise Exception("Gemini not configured")
            
            prompt = f"""
            Analyze English pronunciation and grammar:
            
            Student: "{user_text}"
            Correct: "{correct_text}"
            
            Return JSON with:
            - pronunciation_score (0-100)
            - grammar_score (0-100)
            - fluency_score (0-100)
            - confidence_score (0-100)
            - specific_errors (list)
            - correction_suggestions (list in Tamil)
            - overall_feedback (in Tamil)
            - corrected_sentence
            - tamil_explanation
            - improvement_plan (7-day plan)
            - recommended_exercises (list)
            
            Return only JSON.
            """
            
            response = gemini_model.generate_content(prompt)
            text = response.text.strip()
            
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            return {
                "pronunciation_score": 70,
                "grammar_score": 75,
                "fluency_score": 65,
                "confidence_score": 60,
                "specific_errors": ["Check pronunciation"],
                "correction_suggestions": ["மெதுவாக பேச பயிற்சி செய்யுங்கள்"],
                "overall_feedback": "நல்ல முயற்சி! தொடர்ந்து பயிற்சி செய்யுங்கள்.",
                "corrected_sentence": correct_text,
                "tamil_explanation": "உச்சரிப்பு மேம்படுத்த பயிற்சி தேவை",
                "improvement_plan": ["Day 1: Basic pronunciation", "Day 2: Sentence formation"],
                "recommended_exercises": ["Record and listen", "Practice with AI"]
            }
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return {
                "pronunciation_score": 70,
                "grammar_score": 75,
                "fluency_score": 65,
                "confidence_score": 60,
                "specific_errors": ["Check sentence structure"],
                "correction_suggestions": ["மெதுவாக பேசுங்கள்"],
                "overall_feedback": "நல்ல முயற்சி!",
                "corrected_sentence": correct_text,
                "tamil_explanation": "உச்சரிப்பு பயிற்சி தேவை",
                "improvement_plan": ["Practice daily"],
                "recommended_exercises": ["Basic exercises"]
            }
    
    @staticmethod
    async def code_review(code: str, language: str, requirements: List[str] = None) -> Dict:
        try:
            system_prompt = f"""You are an expert {language} code reviewer. Provide detailed constructive feedback.
            Focus on: correctness, efficiency, security, best practices, and code style."""
            
            req_text = "\n".join(requirements) if requirements else "No specific requirements"
            
            prompt = f"""
            Code Review Request:
            Language: {language}
            Requirements: {req_text}
            
            Code:
            ```{language}
            {code}
            ```
            
            Return JSON with:
            - correctness_score (0-100)
            - efficiency_score (0-100)
            - security_score (0-100)
            - best_practices_score (0-100)
            - readability_score (0-100)
            - bugs_found (list with severity: low/medium/high/critical)
            - security_vulnerabilities (list)
            - performance_issues (list)
            - suggestions (list with priority)
            - corrected_code (if needed)
            - explanation
            - complexity_analysis (time/space)
            """
            
            response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
            return json.loads(response)
        except Exception as e:
            logger.error(f"Code review error: {e}")
            return {
                "correctness_score": 70,
                "efficiency_score": 65,
                "security_score": 60,
                "best_practices_score": 60,
                "readability_score": 70,
                "bugs_found": [{"description": "Check syntax", "severity": "low"}],
                "security_vulnerabilities": [],
                "performance_issues": [],
                "suggestions": ["Test your code thoroughly"],
                "corrected_code": code,
                "explanation": "Review code for syntax errors",
                "complexity_analysis": {"time": "O(n)", "space": "O(1)"}
            }
    
    @staticmethod
    async def generate_interview_questions(role: str, difficulty: str, count: int = 5) -> List[Dict]:
        system_prompt = "You are an experienced HR and Technical Interviewer."
        
        prompt = f"""
        Generate {count} interview questions for {role} position.
        Difficulty: {difficulty}
        
        Return JSON with array of questions, each with:
        - id
        - question
        - type (technical/behavioral/situational)
        - difficulty
        - expected_answer_points (list)
        - category
        - time_to_answer (seconds)
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            data = json.loads(response)
            return data.get("questions", [])
        except:
            return [
                {
                    "id": "1",
                    "question": f"Tell me about yourself and why you want to be a {role}",
                    "type": "behavioral",
                    "difficulty": "easy",
                    "expected_answer_points": ["Introduction", "Experience", "Motivation"],
                    "category": "General",
                    "time_to_answer": 120
                }
            ]
    
    @staticmethod
    async def evaluate_interview_answer(question: str, answer: str, role: str) -> Dict:
        system_prompt = "You are an expert interviewer evaluating candidate responses."
        
        prompt = f"""
        Question: "{question}"
        Candidate Answer: "{answer}"
        Role: {role}
        
        Evaluate and return JSON with:
        - content_score (0-100)
        - clarity_score (0-100)
        - confidence_score (0-100)
        - relevance_score (0-100)
        - depth_score (0-100)
        - filler_words_count
        - improvement_tips (list)
        - suggested_better_answer
        - keywords_missing (list)
        - keywords_present (list)
        - overall_feedback
        - recommended_resources (list)
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {
                "content_score": 70,
                "clarity_score": 65,
                "confidence_score": 60,
                "relevance_score": 75,
                "depth_score": 60,
                "filler_words_count": 0,
                "improvement_tips": ["Structure your answer better"],
                "suggested_better_answer": "A better answer would focus on specific examples...",
                "keywords_missing": [],
                "keywords_present": [],
                "overall_feedback": "Good attempt, needs more depth",
                "recommended_resources": ["Interview preparation guides"]
            }
    
    @staticmethod
    async def generate_learning_path(user_data: Dict) -> Dict:
        system_prompt = "You are an expert educational psychologist and career counselor."
        
        prompt = f"""
        Generate personalized learning path for student:
        
        Student Info:
        - Stage: {user_data.get('stage', 'freshie')}
        - Department: {user_data.get('department', 'General')}
        - Current Skills: {user_data.get('skills', [])}
        - Weak Areas: {user_data.get('weak_areas', [])}
        - Interests: {user_data.get('interests', [])}
        - Career Goals: {user_data.get('career_goals', [])}
        
        Create a 30-day comprehensive learning path in JSON with:
        - overview
        - daily_plans (array for 30 days, each with: day_number, focus_areas, tasks, resources, estimated_hours)
        - weekly_milestones (array for 4 weeks)
        - recommended_courses (array)
        - project_ideas (array)
        - skill_development_timeline
        - assessment_schedule
        - motivational_quotes (array)
        - success_metrics
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {
                "overview": "Basic learning path",
                "daily_plans": [{"day": 1, "focus": "Foundations", "tasks": ["Learn basics"]}],
                "weekly_milestones": ["Week 1: Foundation"],
                "recommended_courses": ["Introduction to Programming"],
                "project_ideas": ["Build a simple website"],
                "skill_development_timeline": "4 weeks",
                "assessment_schedule": ["Weekly quiz"],
                "motivational_quotes": ["Keep learning!"],
                "success_metrics": ["Complete all daily tasks"]
            }
    
    @staticmethod
    async def chat_assistant(message: str, context: Dict) -> str:
        system_prompt = f"""You are EduSync AI Assistant, a friendly and knowledgeable tutor.
        User Context: {json.dumps(context, default=str)}
        
        Guidelines:
        1. Be supportive, encouraging, and patient
        2. Provide accurate, practical information
        3. When unsure, admit it and suggest resources
        4. Keep responses concise but helpful
        5. Adapt to user's learning level
        6. Suggest next steps for learning
        7. Use examples when helpful
        8. Maintain professional but friendly tone
        """
        
        prompt = f"User: {message}\n\nAssistant:"
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=False)
        return response
    
    @staticmethod
    async def code_help(code: str, error: str, requirement: str, language: str, context: str) -> Dict:
        system_prompt = f"""You are an expert {language} programming tutor. Help students fix code errors and improve their solutions.
        Provide clear explanations and examples."""
        
        prompt = f"""
        Programming Help Request:
        Language: {language}
        
        {f"Code Provided:\n```{language}\n{code}\n```" if code else ""}
        {f"Error Message:\n{error}" if error else ""}
        {f"Requirement:\n{requirement}" if requirement else ""}
        {f"Context:\n{context}" if context else ""}
        
        Provide comprehensive help including:
        1. Problem analysis
        2. Step-by-step solution
        3. Corrected code with comments
        4. Explanation of key concepts
        5. Common pitfalls to avoid
        6. Alternative approaches
        7. Practice exercises
        
        Return as JSON with:
        - analysis
        - corrected_code
        - explanation
        - key_concepts (list)
        - common_mistakes (list)
        - practice_exercises (list)
        - additional_resources (list)
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {
                "analysis": "Code analysis",
                "corrected_code": code,
                "explanation": "Explanation of the solution",
                "key_concepts": ["Basic concepts"],
                "common_mistakes": ["Common errors"],
                "practice_exercises": ["Practice problems"],
                "additional_resources": ["Documentation links"]
            }
    
    @staticmethod
    async def generate_project_ideas(user_data: Dict) -> List[Dict]:
        system_prompt = "You are a project mentor and software architect."
        
        prompt = f"""
        Generate project ideas for student:
        
        Student Info:
        - Stage: {user_data.get('stage', 'freshie')}
        - Skills: {user_data.get('skills', [])}
        - Interests: {user_data.get('interests', [])}
        - Department: {user_data.get('department', 'Computer Science')}
        
        Generate 5 project ideas with:
        - title
        - description
        - difficulty (beginner/intermediate/advanced)
        - estimated_time (hours)
        - tech_stack
        - learning_outcomes
        - prerequisites
        - resources
        
        Return as JSON array.
        """
        
        response = await AIService.call_ollama(prompt, system_prompt, json_mode=True)
        try:
            data = json.loads(response)
            return data if isinstance(data, list) else []
        except:
            return [
                {
                    "title": "Portfolio Website",
                    "description": "Build a personal portfolio website",
                    "difficulty": "beginner",
                    "estimated_time": 20,
                    "tech_stack": ["HTML", "CSS", "JavaScript"],
                    "learning_outcomes": ["Web development basics", "Responsive design"],
                    "prerequisites": ["Basic HTML/CSS"],
                    "resources": ["MDN Web Docs", "W3Schools"]
                }
            ]
    
    @staticmethod
    async def english_teacher_feedback(user_text: str) -> Dict:
        """Provide English grammar and pronunciation feedback with Tamil explanations"""
        try:
            if gemini_model is None:
                raise Exception("Gemini not configured")
            
            prompt = f"""
            You are an English teacher.
            The user wrote this English sentence:
            
            "{user_text}"
            
            Do these 3 things:
            1. Find mistakes in grammar, tense, spelling, or sentence structure
            2. Explain the mistakes in TAMIL
            3. Give the corrected perfect English sentence
            
            Reply in this format:
            
            Mistakes in Tamil:
            ...
            
            Correct English:
            ...
            
            Additional Tips in Tamil:
            ...
            """
            
            response = gemini_model.generate_content(prompt)
            text = response.text
            
            # Parse response
            mistakes = ""
            correct_english = ""
            tips = ""
            
            if "Mistakes in Tamil:" in text:
                parts = text.split("Mistakes in Tamil:")
                if len(parts) > 1:
                    subparts = parts[1].split("Correct English:")
                    mistakes = subparts[0].strip()
                    if len(subparts) > 1:
                        subsubparts = subparts[1].split("Additional Tips in Tamil:")
                        correct_english = subsubparts[0].strip()
                        if len(subsubparts) > 1:
                            tips = subsubparts[1].strip()
            
            return {
                "user_text": user_text,
                "mistakes_in_tamil": mistakes,
                "correct_english": correct_english,
                "tips_in_tamil": tips,
                "pronunciation_score": 70,
                "grammar_score": 75,
                "feedback": text
            }
        except Exception as e:
            logger.error(f"English teacher feedback error: {e}")
            return {
                "user_text": user_text,
                "mistakes_in_tamil": "தவறுகளை பகுப்பாய்வு செய்ய முடியவில்லை",
                "correct_english": user_text,
                "tips_in_tamil": "மீண்டும் முயற்சிக்கவும்",
                "pronunciation_score": 60,
                "grammar_score": 65,
                "feedback": "Analysis failed. Please try again."
            }
    
    @staticmethod
    async def call_ollama(prompt: str, system_prompt: str = None, json_mode: bool = False):
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            data = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 1000
                }
            }
            
            if json_mode:
                data["format"] = "json"
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=data)
                if response.status_code == 200:
                    result = response.json()
                    return result["message"]["content"]
                else:
                    raise Exception(f"Ollama API error: {response.status_code}")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            if json_mode:
                return '{"error": "AI service unavailable"}'
            return "I apologize, but I'm having trouble connecting to the AI service. Please try again in a moment."

# =============== COMPILER SERVICE ===============
# =============== COMPILER SERVICE ===============
# =============== COMPILER SERVICE ===============
class CompilerService:
    @staticmethod
    def sh_escape(s: str) -> str:
        """Escape string for shell command"""
        if s == "":
            return "''"
        return "'" + s.replace("'", "'\"'\"'") + "'"
    
    @staticmethod
    def run_subprocess(cmd_list, timeout, input_data=None):
        """Run subprocess synchronously"""
        try:
            input_text = input_data.encode() if input_data else None
            proc = subprocess.run(
                cmd_list,
                input=input_text,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                timeout=timeout
            )
            return proc.returncode, proc.stdout.decode('utf-8', errors='replace'), proc.stderr.decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired as e:
            return -1, e.stdout.decode('utf-8', errors='replace') if e.stdout else "", (e.stderr.decode('utf-8', errors='replace') if e.stderr else "") + f"\nTimeout after {timeout}s"
        except Exception as e:
            return -1, "", str(e)
    
    @staticmethod
    async def docker_exec(image: str, workdir: Path, inner_cmd: str, timeout: int, input_data: str = None):
        """Secure docker run with writable /tmp"""
        container_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--cpus", DOCKER_CPU,
            "--memory", DOCKER_MEMORY,
            "--pids-limit", "64",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-v", f"{str(workdir)}:/app:rw",  # CHANGED: /tmp -> /app
            "-w", "/app",  # CHANGED: working directory to /app
            image,
            "sh", "-c", inner_cmd
        ]
        
        try:
            # Check if executor is initialized
            global executor
            if executor is None:
                logger.warning("Executor not initialized, creating new one")
                executor = ThreadPoolExecutor(max_workers=10)
            
            # Run in thread pool asynchronously
            loop = asyncio.get_event_loop()
            
            def run_subprocess_sync():
                try:
                    # Convert input_data to bytes if provided
                    input_bytes = None
                    if input_data is not None:
                        input_bytes = input_data.encode('utf-8')
                    
                    result = subprocess.run(
                        container_cmd,
                        input=input_bytes,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=timeout
                    )
                    return result
                except subprocess.TimeoutExpired as e:
                    # Create a mock result object for timeout
                    class TimeoutResult:
                        def __init__(self):
                            self.returncode = -1
                            self.stdout = b""
                            self.stderr = f"❌ Time limit exceeded ({timeout}s)".encode('utf-8')
                    return TimeoutResult()
                except Exception as e:
                    class ErrorResult:
                        def __init__(self, error_msg):
                            self.returncode = -1
                            self.stdout = b""
                            self.stderr = error_msg.encode('utf-8')
                    return ErrorResult(f"❌ Docker execution error: {str(e)}")
            
            # Run the synchronous subprocess in thread pool
            res = await loop.run_in_executor(executor, run_subprocess_sync)
            
            # Decode the output
            stdout = res.stdout.decode('utf-8', errors='replace') if res.stdout else ""
            stderr = res.stderr.decode('utf-8', errors='replace') if res.stderr else ""
            
            return res.returncode, stdout, stderr
            
        except Exception as e:
            logger.error(f"Docker exec error: {e}")
            return -1, "", f"❌ Docker execution failed: {str(e)}"
            
            # Run the synchronous subprocess in thread pool
            res = await loop.run_in_executor(executor, run_subprocess_sync)
            
            # Decode the output
            stdout = res.stdout.decode('utf-8', errors='replace') if res.stdout else ""
            stderr = res.stderr.decode('utf-8', errors='replace') if res.stderr else ""
            
            return res.returncode, stdout, stderr
            
        except Exception as e:
            logger.error(f"Docker exec error: {e}")
            return -1, "", f"❌ Docker execution failed: {str(e)}"
    
    @staticmethod
    async def execute_code_safely(code: str, language: str, input_data: str = "", test_cases: List = None) -> Dict:
        """Execute code safely in Docker container"""
        # Normalize language input
        language = language.lower().strip()
        
        # Language mapping for common aliases
        language_map = {
            "py": "python",
            "python3": "python",
            "js": "javascript",
            "node": "javascript",
            "nodejs": "javascript",
            "java8": "java",
            "java11": "java",
            "java17": "java",
            "c++": "cpp",
            "cplusplus": "cpp",
            "golang": "go",
            "rs": "rust"
        }
        
        # Map alias to standard language
        if language in language_map:
            language = language_map[language]
        
        # Debug logging
        logger.info(f"Executing code in language: {language}")
        
        # Check if language is supported
        if language not in LANG_CONFIG:
            logger.error(f"Language '{language}' not supported. Available: {list(LANG_CONFIG.keys())}")
            return {
                "success": False,
                "output": "",
                "error": f"❌ Language '{language}' not supported. Available languages: {', '.join(LANG_CONFIG.keys())}",
                "return_code": -1,
                "execution_time": 0,
                "memory_used": 0,
                "test_results": None
            }
        
        cfg = LANG_CONFIG[language]
        
        # Validate configuration
        if cfg is None:
            logger.error(f"Configuration for language '{language}' is None")
            return {
                "success": False,
                "output": "",
                "error": f"❌ Configuration error for language '{language}'",
                "return_code": -1,
                "execution_time": 0,
                "memory_used": 0,
                "test_results": None
            }
        
        # Check required configuration keys
        required_keys = ["image", "run_cmd", "file_ext"]
        missing_keys = [key for key in required_keys if key not in cfg]
        if missing_keys:
            logger.error(f"Missing required config keys for '{language}': {missing_keys}")
            return {
                "success": False,
                "output": "",
                "error": f"❌ Incomplete configuration for language '{language}'. Missing: {', '.join(missing_keys)}",
                "return_code": -1,
                "execution_time": 0,
                "memory_used": 0,
                "test_results": None
            }
        
        # Check if executor is initialized
        global executor
        if executor is None:
            logger.warning("Executor not initialized, creating new one")
            executor = ThreadPoolExecutor(max_workers=10)
        
        ext = cfg["file_ext"]
        tmpdir = Path(tempfile.mkdtemp(prefix=f"compiler-{language}-"))
        
        try:
            start_time = datetime.now()
            
            # Write source file
            if language == "java":
                src_name = f"Main.{ext}"
            elif language == "go":
                src_name = f"main.{ext}"
            else:
                src_name = f"main.{ext}"
            
            src_path = tmpdir / src_name
            src_path.write_text(code, encoding="utf-8")
            
            compile_stderr = None
            compile_time = 0
            
            # Compile if needed
            if cfg.get("compile_cmd"):
                compile_start = datetime.now()
                compile_cmd = cfg["compile_cmd"].format(filename=src_name)
                logger.info(f"Compiling with command: {compile_cmd}")
                
                exit_code, out, err = await CompilerService.docker_exec(
                    cfg["image"], tmpdir, compile_cmd, TIMEOUT_SECONDS
                )
                
                compile_time = (datetime.now() - compile_start).total_seconds()
                compile_stderr = err
                
                if exit_code != 0:
                    logger.error(f"Compilation failed for {language}: {err}")
                    return {
                        "success": False,
                        "output": out,
                        "error": err,
                        "compile_error": compile_stderr,
                        "return_code": exit_code,
                        "execution_time": compile_time,
                        "memory_used": 0,
                        "test_results": None
                    }
                
                logger.info(f"Compilation successful for {language}")
            
            # Run code
            run_cmd = cfg["run_cmd"].format(filename=src_name)
            logger.info(f"Running with command: {run_cmd}")
            
            # Execute the code
            exit_code, stdout, stderr = await CompilerService.docker_exec(
                cfg["image"], tmpdir, run_cmd, TIMEOUT_SECONDS, input_data
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Run test cases if provided
            test_results = []
            if test_cases and isinstance(test_cases, list):
                logger.info(f"Running {len(test_cases)} test cases")
                for i, test_case in enumerate(test_cases):
                    test_input = test_case.get("input", "")
                    expected_output = test_case.get("output", "")
                    
                    test_exit_code, test_stdout, test_stderr = await CompilerService.docker_exec(
                        cfg["image"], tmpdir, run_cmd, TIMEOUT_SECONDS, test_input
                    )
                    
                    actual_output = test_stdout.strip() if test_stdout else ""
                    expected_output_clean = str(expected_output).strip() if expected_output else ""
                    
                    passed = (test_exit_code == 0 and actual_output == expected_output_clean)
                    
                    test_results.append({
                        "test_case": i + 1,
                        "input": test_input,
                        "expected_output": expected_output_clean,
                        "actual_output": actual_output,
                        "passed": passed,
                        "error": test_stderr if test_stderr else "",
                        "exit_code": test_exit_code
                    })
            
            # Format success response
            result = {
                "success": exit_code == 0,
                "output": stdout,
                "error": stderr,
                 "compile_error": compile_stderr if compile_stderr else "",  # FIXED
                "return_code": exit_code,
                "execution_time": round(execution_time, 4),
                "memory_used": 0,
                "test_results": test_results if test_cases else None,
                "compile_time": round(compile_time, 4) if cfg.get("compile_cmd") else 0,
                "language": language,
                "file_name": src_name
            }
            
            logger.info(f"Execution completed for {language}. Success: {exit_code == 0}, Time: {execution_time}s")
            return result
            
        except Exception as e:
            logger.error(f"Compiler error for {language}: {e}", exc_info=True)
            return {
                "success": False,
                "output": "",
                "error": f"❌ Unexpected error during execution: {str(e)}",
                "return_code": -1,
                "execution_time": 0,
                "memory_used": 0,
                "test_results": None
            }
        finally:
            # Cleanup temporary directory
            try:
                if os.path.exists(tmpdir):
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    logger.debug(f"Cleaned up temp directory: {tmpdir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {tmpdir}: {e}")
    
    @staticmethod
    async def execute_simple_code(code: str, language: str = "python", timeout: int = 10) -> Dict:
        """Simplified version for quick code execution"""
        try:
            # Basic code validation
            if not code or len(code.strip()) == 0:
                return {
                    "success": False,
                    "output": "",
                    "error": "❌ Empty code provided",
                    "return_code": -1
                }
            
            # Limit code size
            if len(code) > 10000:
                return {
                    "success": False,
                    "output": "",
                    "error": "❌ Code too large (max 10KB)",
                    "return_code": -1
                }
            
            # Execute code
            result = await CompilerService.execute_code_safely(
                code=code,
                language=language,
                input_data="",
                test_cases=None
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Simple code execution error: {e}")
            return {
                "success": False,
                "output": "",
                "error": f"❌ Execution error: {str(e)}",
                "return_code": -1
            }
    
    @staticmethod
    async def validate_code(code: str, language: str, requirements: List[str] = None) -> Dict:
        """Validate code against requirements"""
        try:
            # Execute the code first
            exec_result = await CompilerService.execute_code_safely(code, language)
            
            # Basic validation
            validation_result = {
                "execution_success": exec_result["success"],
                "execution_output": exec_result["output"],
                "execution_error": exec_result["error"],
                "compile_error": exec_result.get("compile_error"),
                "execution_time": exec_result["execution_time"],
                "requirements_met": [],
                "requirements_failed": [],
                "suggestions": []
            }
            
            # Check requirements if provided
            if requirements and isinstance(requirements, list):
                for req in requirements:
                    if "import" in req.lower() and "import" in code:
                        validation_result["requirements_met"].append(req)
                    elif "function" in req.lower():
                        # Simple function check
                        if "def " in code:
                            validation_result["requirements_met"].append(req)
                        else:
                            validation_result["requirements_failed"].append(req)
                    else:
                        # Generic check - if requirement text appears in code
                        if req.lower() in code.lower():
                            validation_result["requirements_met"].append(req)
                        else:
                            validation_result["requirements_failed"].append(req)
            
            # Add suggestions based on errors
            if exec_result["error"]:
                if "syntax" in exec_result["error"].lower():
                    validation_result["suggestions"].append("Check for syntax errors")
                if "import" in exec_result["error"].lower():
                    validation_result["suggestions"].append("Check module imports")
                if "undefined" in exec_result["error"].lower():
                    validation_result["suggestions"].append("Check variable/function names")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Code validation error: {e}")
            return {
                "execution_success": False,
                "execution_error": f"Validation error: {str(e)}",
                "requirements_met": [],
                "requirements_failed": requirements or [],
                "suggestions": ["Try testing your code with simple inputs first"]
            }
    
    @staticmethod
    async def benchmark_code(code: str, language: str, iterations: int = 5) -> Dict:
        """Benchmark code execution time"""
        try:
            if iterations < 1 or iterations > 20:
                iterations = 5
            
            execution_times = []
            outputs = []
            
            for i in range(iterations):
                start_time = datetime.now()
                result = await CompilerService.execute_code_safely(code, language)
                end_time = datetime.now()
                
                execution_time = (end_time - start_time).total_seconds()
                execution_times.append(execution_time)
                
                if i == 0:  # Only store output from first run
                    outputs.append(result["output"][:500])  # Limit output size
            
            # Calculate statistics
            avg_time = sum(execution_times) / len(execution_times)
            min_time = min(execution_times)
            max_time = max(execution_times)
            
            return {
                "iterations": iterations,
                "average_time": round(avg_time, 4),
                "min_time": round(min_time, 4),
                "max_time": round(max_time, 4),
                "execution_times": [round(t, 4) for t in execution_times],
                "sample_output": outputs[0] if outputs else "",
                "performance_rating": "fast" if avg_time < 1 else "moderate" if avg_time < 5 else "slow"
            }
            
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            return {
                "error": f"Benchmark failed: {str(e)}",
                "iterations": 0,
                "average_time": 0
            }
            
# =============== SPEECH SERVICES ===============
class SpeechService:
    @staticmethod
    async def text_to_speech(text: str, language: str = 'ta', speed: float = 1.0) -> bytes:
        try:
            if language == 'ta':
                tts = gTTS(text=text, lang='ta', slow=False)
            elif language == 'hi':
                tts = gTTS(text=text, lang='hi', slow=False)
            else:
                tts = gTTS(text=text, lang='en', slow=False)
            
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            return audio_bytes.read()
        except Exception as e:
            logger.error(f"TTS error: {e}")
            # Fallback to English
            tts = gTTS(text=text, lang='en', slow=False)
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            return audio_bytes.read()
    
    @staticmethod
    async def speech_to_text(audio_bytes: bytes, language: str = 'en-US') -> str:
        try:
            recognizer = sr.Recognizer()
            
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            
            try:
                with sr.AudioFile(tmp_path) as source:
                    audio = recognizer.record(source)
                    text = recognizer.recognize_google(audio, language=language)
                os.unlink(tmp_path)
                return text
            except:
                os.unlink(tmp_path)
                return "Could not understand audio"
                
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError as e:
            logger.error(f"STT request error: {e}")
            return "Speech recognition service error"
        except Exception as e:
            logger.error(f"STT error: {e}")
            return "Audio processing failed"
    
    @staticmethod
    async def analyze_pronunciation(audio_bytes: bytes, reference_text: str) -> Dict:
        try:
            # Convert audio to text
            spoken_text = await SpeechService.speech_to_text(audio_bytes)
            
            # Get AI analysis
            analysis = await AIService.analyze_english_with_gemini(spoken_text, reference_text)
            
            # Add audio metrics
            analysis["spoken_text"] = spoken_text
            analysis["word_count"] = len(spoken_text.split())
            
            return analysis
        except Exception as e:
            logger.error(f"Pronunciation analysis error: {e}")
            return {
                "pronunciation_score": 50,
                "grammar_score": 50,
                "fluency_score": 50,
                "spoken_text": "Analysis failed",
                "error": str(e)
            }

# =============== GITHUB-LIKE VERSION CONTROL ===============
class VersionControlService:
    @staticmethod
    async def create_repository(user_id: str, name: str, description: str, is_public: bool = True):
        """Create a new code repository"""
        try:
            repo_id = str(uuid.uuid4())
            
            repository = {
                "id": repo_id,
                "name": name,
                "description": description,
                "owner_id": user_id,
                "is_public": is_public,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "collaborators": [user_id],
                "branches": ["main"],
                "default_branch": "main",
                "star_count": 0,
                "fork_count": 0,
                "last_commit": None,
                "language_stats": {},
                "settings": {
                    "allow_pull_requests": True,
                    "allow_issues": True,
                    "require_code_review": False
                }
            }
            
            await code_repositories_collection.insert_one(repository)
            return repository
            
        except Exception as e:
            logger.error(f"Create repository error: {e}")
            raise HTTPException(status_code=500, detail="Failed to create repository")
    
    @staticmethod
    async def create_commit(repository_id: str, user_id: str, message: str, files: List[Dict], branch: str = "main"):
        """Create a new commit in repository"""
        try:
            # Get repository
            repo = await code_repositories_collection.find_one({"id": repository_id})
            if not repo:
                raise HTTPException(status_code=404, detail="Repository not found")
            
            # Check if user has access
            if user_id not in repo.get("collaborators", []):
                raise HTTPException(status_code=403, detail="Access denied")
            
            commit_id = str(uuid.uuid4())
            
            commit = {
                "id": commit_id,
                "repository_id": repository_id,
                "author_id": user_id,
                "message": message,
                "files": files,
                "branch": branch,
                "timestamp": datetime.now(timezone.utc),
                "hash": hashlib.sha256(f"{repository_id}{user_id}{message}{datetime.now()}".encode()).hexdigest()[:12],
                "parent_commit": repo.get("last_commit"),
                "stats": {
                    "files_changed": len(files),
                    "additions": sum(f.get("additions", 0) for f in files),
                    "deletions": sum(f.get("deletions", 0) for f in files)
                }
            }
            
            await code_commits_collection.insert_one(commit)
            
            # Update repository
            await code_repositories_collection.update_one(
                {"id": repository_id},
                {
                    "$set": {
                        "last_commit": commit_id,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "recent_commits": {
                            "$each": [commit_id],
                            "$slice": -50  # Keep only last 50 commits
                        }
                    }
                }
            )
            
            # Update language statistics
            await VersionControlService.update_language_stats(repository_id)
            
            # Send notifications to collaborators
            for collaborator_id in repo.get("collaborators", []):
                if collaborator_id != user_id:
                    await NotificationService.create_notification(
                        user_id=collaborator_id,
                        title="New Commit",
                        message=f"New commit in {repo['name']}: {message}",
                        notification_type="repository",
                        action_url=f"/repos/{repository_id}/commit/{commit_id}"
                    )
            
            return commit
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Create commit error: {e}")
            raise HTTPException(status_code=500, detail="Failed to create commit")
    
    @staticmethod
    async def get_repository_files(repository_id: str, branch: str = "main"):
        """Get all files in repository at specific branch"""
        try:
            # Get all commits for the branch
            commits = await code_commits_collection.find({
                "repository_id": repository_id,
                "branch": branch
            }).sort("timestamp", 1).to_list(1000)  # Limit to 1000 commits
            
            # Build file tree from commits
            files = {}
            for commit in commits:
                for file in commit.get("files", []):
                    file_path = file.get("path")
                    if file_path:
                        files[file_path] = file.get("content", "")
            
            return files
            
        except Exception as e:
            logger.error(f"Get repository files error: {e}")
            return {}
    
    @staticmethod
    async def update_language_stats(repository_id: str):
        """Update language statistics for repository"""
        try:
            files = await VersionControlService.get_repository_files(repository_id)
            
            # Count files by extension
            extensions = {}
            for file_path, content in files.items():
                ext = Path(file_path).suffix.lower()
                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1
            
            # Map extensions to languages
            lang_map = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.java': 'Java',
                '.cpp': 'C++',
                '.c': 'C',
                '.go': 'Go',
                '.rs': 'Rust',
                '.html': 'HTML',
                '.css': 'CSS',
                '.md': 'Markdown',
                '.json': 'JSON'
            }
            
            language_stats = {}
            for ext, count in extensions.items():
                lang = lang_map.get(ext, ext.upper()[1:])
                language_stats[lang] = count
            
            await code_repositories_collection.update_one(
                {"id": repository_id},
                {"$set": {"language_stats": language_stats}}
            )
            
        except Exception as e:
            logger.error(f"Update language stats error: {e}")
    
    @staticmethod
    async def create_pull_request(repository_id: str, user_id: str, title: str, description: str, source_branch: str, target_branch: str = "main"):
        """Create a pull request"""
        try:
            pr_id = str(uuid.uuid4())
            
            pr = {
                "id": pr_id,
                "repository_id": repository_id,
                "title": title,
                "description": description,
                "author_id": user_id,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "status": "open",  # open, closed, merged
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "comments": [],
                "reviewers": [],
                "assignees": [],
                "labels": ["feature"],
                "mergeable": True,
                "conflicts": []
            }
            
            # Save to version_control collection
            await version_control_collection.insert_one(pr)
            
            # Notify repository owner
            repo = await code_repositories_collection.find_one({"id": repository_id})
            if repo:
                await NotificationService.create_notification(
                    user_id=repo["owner_id"],
                    title="New Pull Request",
                    message=f"New PR for {repo['name']}: {title}",
                    notification_type="pull_request",
                    action_url=f"/repos/{repository_id}/pull/{pr_id}"
                )
            
            return pr
            
        except Exception as e:
            logger.error(f"Create pull request error: {e}")
            raise HTTPException(status_code=500, detail="Failed to create pull request")

# =============== NOTIFICATION SERVICE ===============
class NotificationService:
    @staticmethod
    async def create_notification(user_id: str, title: str, message: str, 
                                 notification_type: str = "info", priority: str = "normal",
                                 action_url: str = None, data: Dict = None):
        try:
            notification = {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": notification_type,
                "priority": priority,
                "action_url": action_url,
                "data": data or {},
                "read": False,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=30)
            }
            
            await notifications_collection.insert_one(notification)
            
            # Send real-time notification via WebSocket if user is connected
            await WebSocketManager.send_to_user(user_id, {
                "type": "notification",
                "notification": notification
            })
            
            # Send email for high priority notifications
            if priority == "high":
                user = await users_collection.find_one({"_id": ObjectId(user_id)})
                if user and user.get("email"):
                    await send_email_async(
                        user["email"],
                        f"Urgent: {title}",
                        f"{message}\n\nAction URL: {action_url or 'No action required'}"
                    )
            
            return notification
        except Exception as e:
            logger.error(f"Create notification error: {e}")
    
    @staticmethod
    async def create_broadcast(title: str, message: str, target_users: List[str] = None,
                              filters: Dict = None, notification_type: str = "announcement"):
        try:
            notification = {
                "broadcast": True,
                "title": title,
                "message": message,
                "type": notification_type,
                "target_users": target_users,
                "filters": filters,
                "created_at": datetime.now(timezone.utc)
            }
            
            await notifications_collection.insert_one(notification)
            
            # Send to all connected users
            await WebSocketManager.broadcast({
                "type": "broadcast",
                "notification": notification
            })
            
            return notification
        except Exception as e:
            logger.error(f"Create broadcast error: {e}")

# =============== WEB SOCKET MANAGER ===============
class WebSocketManager:
    _connections: Dict[str, WebSocket] = {}
    _user_connections: Dict[str, List[str]] = defaultdict(list)
    
    @classmethod
    async def connect(cls, websocket: WebSocket, connection_id: str, user_id: str):
        await websocket.accept()
        cls._connections[connection_id] = websocket
        cls._user_connections[user_id].append(connection_id)
        
        # Send connection established message
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    @classmethod
    def disconnect(cls, connection_id: str, user_id: str):
        if connection_id in cls._connections:
            del cls._connections[connection_id]
        
        if user_id in cls._user_connections and connection_id in cls._user_connections[user_id]:
            cls._user_connections[user_id].remove(connection_id)
            if not cls._user_connections[user_id]:
                del cls._user_connections[user_id]
    
    @classmethod
    async def send_to_user(cls, user_id: str, message: Dict):
        if user_id in cls._user_connections:
            for connection_id in cls._user_connections[user_id]:
                if connection_id in cls._connections:
                    try:
                        await cls._connections[connection_id].send_json(message)
                    except Exception as e:
                        logger.error(f"WebSocket send error: {e}")
                        cls.disconnect(connection_id, user_id)
    
    @classmethod
    async def send_to_connection(cls, connection_id: str, message: Dict):
        if connection_id in cls._connections:
            try:
                await cls._connections[connection_id].send_json(message)
            except Exception as e:
                logger.error(f"WebSocket send error: {e}")
                # Find and remove this connection
                for uid, conns in cls._user_connections.items():
                    if connection_id in conns:
                        cls.disconnect(connection_id, uid)
                        break
    
    @classmethod
    async def broadcast(cls, message: Dict):
        disconnected = []
        for connection_id, websocket in cls._connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected websockets
        for connection_id in disconnected:
            for uid, conns in cls._user_connections.items():
                if connection_id in conns:
                    cls.disconnect(connection_id, uid)
                    break
    
    @classmethod
    async def broadcast_to_group(cls, group_id: str, message: Dict, exclude_user: str = None):
        # Get group members
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if group:
            for member_id in group.get("members", []):
                if member_id != exclude_user:
                    await cls.send_to_user(member_id, message)

# =============== BACKGROUND TASKS ===============
async def update_user_analytics(user_id: str):
    try:
        # Calculate various analytics
        total_submissions = await submissions_collection.count_documents({"user_id": user_id})
        completed_challenges = await submissions_collection.count_documents({
            "user_id": user_id,
            "completed": True
        })
        
        # Calculate average score
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$score"},
                "total_credits": {"$sum": "$credits_earned"}
            }}
        ]
        
        result = list(await submissions_collection.aggregate(pipeline).to_list(length=1))
        avg_score = result[0]["avg_score"] if result else 0
        total_credits = result[0]["total_credits"] if result else 0
        
        # Update user analytics
        await analytics_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "total_submissions": total_submissions,
                "completed_challenges": completed_challenges,
                "average_score": avg_score,
                "total_credits": total_credits,
                "last_updated": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Analytics update error: {e}")

async def process_submission_async(submission_id: str):
    try:
        submission = await submissions_collection.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            return
        
        # Update leaderboard
        await update_leaderboard(submission["user_id"], submission.get("score", 0))
        
        # Check for badge eligibility
        await check_badge_eligibility(submission["user_id"])
        
        # Update user analytics in background
        asyncio.create_task(update_user_analytics(submission["user_id"]))
        
    except Exception as e:
        logger.error(f"Submission processing error: {e}")

async def update_leaderboard(user_id: str, score: float):
    try:
        week_start = datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())
        
        await leaderboard_collection.update_one(
            {
                "user_id": user_id,
                "period": "weekly",
                "week_start": week_start
            },
            {"$inc": {
                "total_score": score,
                "challenges_completed": 1
            }},
            upsert=True
        )
        
        # Also update monthly leaderboard
        month_start = datetime.now(timezone.utc).replace(day=1)
        await leaderboard_collection.update_one(
            {
                "user_id": user_id,
                "period": "monthly",
                "month_start": month_start
            },
            {"$inc": {
                "total_score": score,
                "challenges_completed": 1
            }},
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Leaderboard update error: {e}")

async def check_badge_eligibility(user_id: str):
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return
        
        badges_doc = await badges_collection.find_one({"user_id": user_id})
        current_badges = badges_doc.get("badges", []) if badges_doc else []
        earned_badges = []
        
        # Check various badge criteria
        
        # Streak badges
        streak = user.get("daily_login_streak", 0)
        if streak >= 30 and not any(b.get("name") == "30 Day Streak" for b in current_badges):
            earned_badges.append({
                "name": "30 Day Streak",
                "icon": "🔥",
                "earned_date": datetime.now(timezone.utc),
                "description": "Logged in for 30 consecutive days",
                "category": "streak"
            })
        
        # Challenge badges
        completed_challenges = user.get("completed_challenges", 0)
        if completed_challenges >= 50 and not any(b.get("name") == "Challenge Master" for b in current_badges):
            earned_badges.append({
                "name": "Challenge Master",
                "icon": "🏆",
                "earned_date": datetime.now(timezone.utc),
                "description": "Completed 50 challenges",
                "category": "challenges"
            })
        
        # Credit badges
        credits = user.get("credits", 0)
        if credits >= 1000 and not any(b.get("name") == "Credit Millionaire" for b in current_badges):
            earned_badges.append({
                "name": "Credit Millionaire",
                "icon": "💰",
                "earned_date": datetime.now(timezone.utc),
                "description": "Earned 1000 credits",
                "category": "credits"
            })
        
        # Voice challenge badges
        voice_subs = await submissions_collection.count_documents({
            "user_id": user_id,
            "challenge_type": "voice",
            "score": {"$gte": 90}
        })
        if voice_subs >= 10 and not any(b.get("name") == "Voice Virtuoso" for b in current_badges):
            earned_badges.append({
                "name": "Voice Virtuoso",
                "icon": "🎤",
                "earned_date": datetime.now(timezone.utc),
                "description": "10 voice challenges with 90+ score",
                "category": "voice"
            })
        
        # Repository badges
        user_repos = await code_repositories_collection.count_documents({"owner_id": user_id})
        if user_repos >= 5 and not any(b.get("name") == "Code Contributor" for b in current_badges):
            earned_badges.append({
                "name": "Code Contributor",
                "icon": "💾",
                "earned_date": datetime.now(timezone.utc),
                "description": "Created 5 code repositories",
                "category": "coding"
            })
        
        # Add new badges
        if earned_badges:
            if badges_doc:
                await badges_collection.update_one(
                    {"user_id": user_id},
                    {"$push": {"badges": {"$each": earned_badges}}}
                )
            else:
                await badges_collection.insert_one({
                    "user_id": user_id,
                    "badges": earned_badges,
                    "created_at": datetime.now(timezone.utc)
                })
            
            # Send notification for each badge
            for badge in earned_badges:
                await NotificationService.create_notification(
                    user_id=user_id,
                    title="🏆 New Badge Earned!",
                    message=f"Congratulations! You earned the '{badge['name']}' badge: {badge['description']}",
                    notification_type="achievement",
                    priority="high",
                    data={"badge": badge}
                )
        
    except Exception as e:
        logger.error(f"Badge check error: {e}")


        
        

# =============== API ROUTES ===============

# Health Check
@app.get("/api/health", tags=["System"])
async def health_check():
    """Comprehensive health check for all services"""
    try:
        # Check MongoDB
        db_status = "connected"
        try:
            await db.command("ping")
        except:
            db_status = "disconnected"
        
        # Check Redis
        redis_status = "connected"
        try:
            if redis_client:
                await redis_client.ping()
            else:
                redis_status = "not_configured"
        except:
            redis_status = "disconnected"
        
        # Check Ollama
        ollama_status = "disconnected"
        ollama_models = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    ollama_status = "connected"
                    data = response.json()
                    ollama_models = [model["name"] for model in data.get("models", [])]
        except:
            pass
        
        # Check Docker
        docker_status = "unknown"
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            docker_status = "installed" if result.returncode == 0 else "not_installed"
        except:
            docker_status = "not_installed"
        
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "mongodb": db_status,
                "redis": redis_status,
                "ollama": {
                    "status": ollama_status,
                    "models": ollama_models,
                    "default_model": OLLAMA_MODEL
                },
                "docker": docker_status,
                "gemini": "configured" if gemini_model else "not_configured"
            },
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "uptime": psutil.boot_time()
            },
            "version": "4.0.0",
            "environment": os.getenv("ENVIRONMENT", "development")
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Authentication Routes
@app.post("/api/auth/register", tags=["Authentication"])
async def register(user: UserRegister, background_tasks: BackgroundTasks):
    """Register a new user"""
    try:
        # Check if email exists
        existing = await users_collection.find_one({"email": user.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Check if roll number exists (for students)
        if user.user_type == UserType.STUDENT and user.roll_number:
            existing_roll = await users_collection.find_one({"roll_number": user.roll_number})
            if existing_roll:
                raise HTTPException(status_code=400, detail="Roll number already registered")
        
        # Hash password
        hashed_pw = hash_password(user.password)
        
        # Create user document
        user_dict = user.model_dump(exclude={"password"})
        user_dict["password"] = hashed_pw
        user_dict["created_at"] = datetime.now(timezone.utc)
        user_dict["updated_at"] = datetime.now(timezone.utc)
        user_dict["is_active"] = True
        user_dict["is_verified"] = False
        user_dict["verification_code"] = secrets.token_hex(16)
        
        # Add student-specific fields
        if user.user_type == UserType.STUDENT:
            user_dict["stage"] = Stage.FRESHIE.value
            user_dict["credits"] = 0
            user_dict["xp"] = 0
            user_dict["level"] = 1
            user_dict["daily_login_streak"] = 0
            user_dict["weekly_login_streak"] = 0
            user_dict["current_stage_progress"] = 0
            user_dict["last_login"] = None
            user_dict["last_active"] = None
            user_dict["weak_areas"] = []
            user_dict["strengths"] = []
            user_dict["skills"] = []
            user_dict["interests"] = []
            user_dict["career_goals"] = []
            user_dict["completed_challenges"] = 0
            user_dict["projects_completed"] = 0
            user_dict["courses_enrolled"] = []
            user_dict["badges"] = []
            user_dict["achievements"] = []
            user_dict["mood_history"] = []
            user_dict["learning_style"] = None
            user_dict["preferred_language"] = "en"
            user_dict["timezone"] = "UTC"
            user_dict["notification_preferences"] = {
                "email": True,
                "push": True,
                "sms": False,
                "challenge_reminders": True,
                "deadline_alerts": True,
                "achievement_alerts": True
            }
        
        # Insert user
        result = await users_collection.insert_one(user_dict)
        user_id = str(result.inserted_id)
        
        # Create initial badges
        await badges_collection.insert_one({
            "user_id": user_id,
            "badges": [{
                "name": "Welcome Aboard!",
                "icon": "🎉",
                "earned_date": datetime.now(timezone.utc),
                "description": "Welcome to EduSync 4.0",
                "category": "welcome"
            }],
            "created_at": datetime.now(timezone.utc)
        })
        
        # Create analytics entry
        await analytics_collection.insert_one({
            "user_id": user_id,
            "user_type": user.user_type,
            "joined_at": datetime.now(timezone.utc),
            "total_sessions": 0,
            "total_time_spent": 0,
            "last_active": None,
            "created_at": datetime.now(timezone.utc)
        })
        
        # Send welcome email
        background_tasks.add_task(
            send_email_async,
            user.email,
            "Welcome to EduSync 4.0!",
            f"Hello {user.full_name},\n\nWelcome to EduSync 4.0! We're excited to have you on board.\n\n"
            f"Your account has been created successfully.\n\n"
            f"Please verify your email by clicking this link: "
            f"http://localhost:3000/verify/{user_dict['verification_code']}\n\n"
            f"Best regards,\nThe EduSync Team"
        )
        
        # Send welcome notification
        await NotificationService.create_notification(
            user_id=user_id,
            title="Welcome to EduSync 4.0! 🎉",
            message=f"Hello {user.full_name}, welcome to our learning community!",
            notification_type="welcome",
            priority="high",
            action_url="/getting-started"
        )
        
        return {
            "message": "Registration successful",
            "user_id": user_id,
            "user_type": user.user_type,
            "verification_required": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/api/auth/login", tags=["Authentication"])
async def login(login_data: UserLogin, background_tasks: BackgroundTasks):
    """User login with device tracking"""
    try:
        user = await users_collection.find_one({"email": login_data.email})
        if not user or not verify_password(login_data.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is deactivated")
        
        # Update login stats
        now = datetime.now(timezone.utc)
        last_login = user.get("last_login")
        
        # Calculate streaks
        daily_streak = user.get("daily_login_streak", 0)
        weekly_streak = user.get("weekly_login_streak", 0)
        
        if last_login:
            last_login_date = last_login.date()
            today = now.date()
            
            # Daily streak
            if (today - last_login_date).days == 1:
                daily_streak += 1
            elif (today - last_login_date).days > 1:
                daily_streak = 1
            
            # Weekly streak (login at least once per week)
            if (today - last_login_date).days <= 7:
                weekly_streak += 1
            else:
                weekly_streak = 1
        else:
            daily_streak = 1
            weekly_streak = 1
        
        # Award credits for login streak
        login_credits = 10 + (daily_streak * 2)  # Base 10 + 2 per streak day
        
        # Update user
        update_data = {
            "last_login": now,
            "last_active": now,
            "daily_login_streak": daily_streak,
            "weekly_login_streak": weekly_streak,
            "credits": user.get("credits", 0) + login_credits,
            "login_count": user.get("login_count", 0) + 1,
            "updated_at": now
        }
        
        # Add device info if provided
        if login_data.device_info:
            device_history = user.get("device_history", [])
            device_history.append({
                "device_info": login_data.device_info,
                "login_time": now,
                "ip_address": None  # Would get from request in production
            })
            update_data["device_history"] = device_history[-10:]  # Keep last 10
        
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": update_data}
        )
        
        # Update analytics
        await analytics_collection.update_one(
            {"user_id": str(user["_id"])},
            {"$inc": {"total_sessions": 1}}
        )
        
        # Create tokens
        access_token = create_access_token({
            "email": user["email"],
            "user_type": user["user_type"],
            "user_id": str(user["_id"]),
            "full_name": user["full_name"]
        })
        
        refresh_token = create_refresh_token({
            "user_id": str(user["_id"]),
            "email": user["email"]
        })
        
        # Store refresh token in Redis
        if redis_client:
            await redis_client.setex(
                f"refresh_token:{refresh_token}",
                REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
                str(user["_id"])
            )
        
        # Send login notification
        background_tasks.add_task(
            NotificationService.create_notification,
            user_id=str(user["_id"]),
            title="Login Successful",
            message=f"Welcome back! Daily streak: {daily_streak} days. Earned {login_credits} credits.",
            notification_type="login",
            priority="low"
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "user_id": str(user["_id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "user_type": user["user_type"],
                "stage": user.get("stage"),
                "department": user.get("department"),
                "year": user.get("year"),
                "credits": user.get("credits", 0) + login_credits,
                "xp": user.get("xp", 0),
                "level": user.get("level", 1),
                "daily_streak": daily_streak,
                "weekly_streak": weekly_streak,
                "profile_picture": user.get("profile_picture"),
                "is_verified": user.get("is_verified", False)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/api/auth/refresh", tags=["Authentication"])
async def refresh_token(refresh_token: str = Body(..., embed=True)):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Check if refresh token is valid in Redis
        if redis_client:
            stored_user_id = await redis_client.get(f"refresh_token:{refresh_token}")
            if not stored_user_id or stored_user_id != payload.get("user_id"):
                raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Get user
        user = await users_collection.find_one({"_id": ObjectId(payload["user_id"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Create new access token
        new_access_token = create_access_token({
            "email": user["email"],
            "user_type": user["user_type"],
            "user_id": str(user["_id"]),
            "full_name": user["full_name"]
        })
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        logger.error(f"Refresh token error: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")

@app.post("/api/auth/logout", tags=["Authentication"])
async def logout(
    refresh_token: str = Body(None, embed=True),
    current_user: dict = Depends(verify_token)
):
    """Logout user and invalidate tokens"""
    try:
        user_id = str(current_user["_id"])
        
        # Invalidate refresh token if provided
        if refresh_token and redis_client:
            await redis_client.delete(f"refresh_token:{refresh_token}")
        
        return {"message": "Logout successful"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")

# User Profile Routes
@app.get("/api/users/profile", tags=["Users"])
async def get_profile(current_user: dict = Depends(verify_token)):
    """Get current user profile"""
    try:
        user_id = str(current_user["_id"])
        
        # Get user with extended data
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get badges
        badges_doc = await badges_collection.find_one({"user_id": user_id})
        badges = badges_doc.get("badges", []) if badges_doc else []
        
        # Get stats
        total_submissions = await submissions_collection.count_documents({"user_id": user_id})
        completed_challenges = await submissions_collection.count_documents({
            "user_id": user_id,
            "completed": True
        })
        
        # Get repository stats
        repo_count = await code_repositories_collection.count_documents({"owner_id": user_id})
        
        # Remove sensitive data
        user.pop("password", None)
        user.pop("verification_code", None)
        user.pop("reset_token", None)
        
        # Convert ObjectId to string
        user["_id"] = str(user["_id"])
        
        # Add computed fields
        user["badges"] = badges
        user["stats"] = {
            "total_submissions": total_submissions,
            "completed_challenges": completed_challenges,
            "projects_completed": user.get("projects_completed", 0),
            "courses_enrolled": len(user.get("courses_enrolled", [])),
            "repositories": repo_count,
            "completion_rate": (completed_challenges / total_submissions * 100) if total_submissions > 0 else 0
        }
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")

@app.put("/api/users/profile", tags=["Users"])
async def update_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(verify_token)
):
    """Update user profile"""
    try:
        user_id = str(current_user["_id"])
        
        # Prepare update
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        # Update user
        result = await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes made")
        
        # Get updated user
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        user.pop("password", None)
        user["_id"] = str(user["_id"])
        
        return {
            "message": "Profile updated successfully",
            "user": user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(status_code=500, detail="Profile update failed")

@app.post("/api/users/profile/picture", tags=["Users"])
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: dict = Depends(verify_token)
):
    """Upload profile picture"""
    try:
        user_id = str(current_user["_id"])
        
        # Validate file
        content, file_size = await validate_file(file)
        
        # Upload to cloud storage
        upload_result = await upload_to_cloud_storage(
            content,
            f"profile_{user_id}_{datetime.now().timestamp()}.jpg",
            "image/jpeg"
        )
        
        # Update user profile
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "profile_picture": upload_result["url"],
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "message": "Profile picture uploaded successfully",
            "url": upload_result["url"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload profile picture error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")

# Challenge Routes
@app.get("/api/challenges", tags=["Challenges"])
async def get_challenges(
    stage: Optional[Stage] = None,
    challenge_type: Optional[str] = None,
    difficulty: Optional[Difficulty] = None,
    language: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get challenges with filters"""
    try:
        query = {}
        
        # For students, default to their stage
        if current_user["user_type"] == UserType.STUDENT:
            query["stage"] = current_user.get("stage", Stage.FRESHIE.value)
        elif stage:
            query["stage"] = stage.value
        
        if challenge_type:
            query["challenge_type"] = challenge_type
        if difficulty:
            query["difficulty"] = difficulty.value
        if language:
            query["language"] = language
        if tags:
            query["tags"] = {"$in": tags.split(",")}
        
        # Get total count
        total = await challenges_collection.count_documents(query)
        
        # Get challenges
        challenges = await challenges_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Get user's submissions for these challenges
        user_id = str(current_user["_id"])
        challenge_ids = [str(ch["_id"]) for ch in challenges]
        
        submissions = await submissions_collection.find({
            "user_id": user_id,
            "challenge_id": {"$in": challenge_ids}
        }).to_list(len(challenge_ids))
        
        submission_map = {sub["challenge_id"]: sub for sub in submissions}
        
        # Format response
        formatted_challenges = []
        for ch in challenges:
            submission = submission_map.get(str(ch["_id"]))
            
            challenge_data = {
                "id": str(ch["_id"]),
                "title": ch["title"],
                "description": ch["description"],
                "stage": ch["stage"],
                "challenge_type": ch["challenge_type"],
                "difficulty": ch["difficulty"],
                "credits_reward": ch["credits_reward"],
                "time_limit": ch.get("time_limit"),
                "media_url": ch.get("media_url"),
                "code_template": ch.get("code_template"),
                "correct_text": ch.get("correct_text"),
                "language": ch.get("language"),
                "tags": ch.get("tags", []),
                "requirements": ch.get("requirements", []),
                "created_at": ch.get("created_at"),
                "created_by": ch.get("created_by_name"),
                "user_status": {
                    "attempted": submission is not None,
                    "completed": submission.get("completed", False) if submission else False,
                    "score": submission.get("score", 0) if submission else 0,
                    "submission_id": str(submission["_id"]) if submission else None,
                } if submission else {
                    "attempted": False,
                    "completed": False,
                    "score": 0,
                    "submission_id": None,
                }
            }
            formatted_challenges.append(challenge_data)
        
        return {
            "challenges": formatted_challenges,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get challenges error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get challenges")

@app.get("/api/challenges/coding", tags=["Challenges"])
async def get_coding_challenges(
    language: Optional[str] = None,
    difficulty: Optional[Difficulty] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get coding challenges specifically"""
    try:
        query = {"challenge_type": "coding"}
        
        if language:
            query["language"] = language
        if difficulty:
            query["difficulty"] = difficulty.value
        
        total = await challenges_collection.count_documents(query)
        
        challenges = await challenges_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        formatted_challenges = []
        for ch in challenges:
            formatted_challenges.append({
                "id": str(ch["_id"]),
                "title": ch["title"],
                "description": ch["description"],
                "difficulty": ch["difficulty"],
                "language": ch.get("language", "python"),
                "credits_reward": ch["credits_reward"],
                "time_limit": ch.get("time_limit"),
                "tags": ch.get("tags", []),
                "test_cases": ch.get("test_cases", []),
                "created_at": ch.get("created_at")
            })
        
        return {
            "challenges": formatted_challenges,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get coding challenges error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get coding challenges")

@app.get("/api/challenges/{challenge_id}", tags=["Challenges"])
async def get_challenge_detail(
    challenge_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get detailed information about a specific challenge"""
    try:
        challenge = await challenges_collection.find_one({"_id": ObjectId(challenge_id)})
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        user_id = str(current_user["_id"])
        
        # Get user's submissions
        submissions = await submissions_collection.find({
            "user_id": user_id,
            "challenge_id": challenge_id
        }).sort("submitted_at", -1).to_list(10)
        
        # Get challenge statistics
        stats = await get_challenge_statistics(challenge_id)
        
        # Get similar challenges
        similar_challenges = await get_similar_challenges(challenge)
        
        challenge_data = {
            "id": str(challenge["_id"]),
            "title": challenge["title"],
            "description": challenge["description"],
            "stage": challenge["stage"],
            "challenge_type": challenge["challenge_type"],
            "difficulty": challenge["difficulty"],
            "credits_reward": challenge["credits_reward"],
            "time_limit": challenge.get("time_limit"),
            "media_url": challenge.get("media_url"),
            "code_template": challenge.get("code_template"),
            "correct_text": challenge.get("correct_text"),
            "language": challenge.get("language"),
            "tags": challenge.get("tags", []),
            "requirements": challenge.get("requirements", []),
            "created_at": challenge.get("created_at"),
            "created_by": challenge.get("created_by_name"),
            "instructions": challenge.get("instructions", ""),
            "hints": challenge.get("hints", []),
            "test_cases": challenge.get("test_cases", []),
            "solution_explanation": challenge.get("solution_explanation"),
            "prerequisites": challenge.get("prerequisites", []),
            "learning_objectives": challenge.get("learning_objectives", []),
            "statistics": stats,
            "user_submissions": [
                {
                    "id": str(sub["_id"]),
                    "score": sub.get("score", 0),
                    "completed": sub.get("completed", False),
                    "submitted_at": sub.get("submitted_at"),
                    "feedback": sub.get("ai_feedback", {})
                }
                for sub in submissions
            ],
            "similar_challenges": similar_challenges,
            "leaderboard": await get_challenge_leaderboard(challenge_id, limit=10)
        }
        
        return challenge_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get challenge detail error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get challenge details")

async def get_challenge_statistics(challenge_id: str):
    """Get statistics for a challenge"""
    try:
        pipeline = [
            {"$match": {"challenge_id": challenge_id}},
            {"$group": {
                "_id": None,
                "total_attempts": {"$sum": 1},
                "average_score": {"$avg": "$score"},
                "completion_count": {"$sum": {"$cond": ["$completed", 1, 0]}},
                "top_score": {"$max": "$score"},
                "unique_users": {"$addToSet": "$user_id"}
            }}
        ]
        
        result = list(await submissions_collection.aggregate(pipeline).to_list(length=1))
        if result:
            stats = result[0]
            return {
                "total_attempts": stats["total_attempts"],
                "average_score": round(stats["average_score"], 2),
                "completion_rate": (stats["completion_count"] / stats["total_attempts"] * 100) if stats["total_attempts"] > 0 else 0,
                "top_score": stats["top_score"],
                "unique_users": len(stats["unique_users"])
            }
        return {
            "total_attempts": 0,
            "average_score": 0,
            "completion_rate": 0,
            "top_score": 0,
            "unique_users": 0
        }
    except:
        return {
            "total_attempts": 0,
            "average_score": 0,
            "completion_rate": 0,
            "top_score": 0,
            "unique_users": 0
        }

async def get_similar_challenges(challenge: Dict):
    """Get similar challenges based on tags and difficulty"""
    try:
        query = {
            "_id": {"$ne": challenge["_id"]},
            "difficulty": challenge["difficulty"],
            "stage": challenge["stage"],
            "tags": {"$in": challenge.get("tags", [])}
        }
        
        similar = await challenges_collection.find(query) \
            .sort("created_at", -1) \
            .limit(5) \
            .to_list(5)
        
        return [
            {
                "id": str(ch["_id"]),
                "title": ch["title"],
                "challenge_type": ch["challenge_type"],
                "difficulty": ch["difficulty"],
                "credits_reward": ch["credits_reward"]
            }
            for ch in similar
        ]
    except:
        return []

async def get_challenge_leaderboard(challenge_id: str, limit: int = 10):
    """Get leaderboard for a specific challenge"""
    try:
        pipeline = [
            {"$match": {"challenge_id": challenge_id, "completed": True}},
            {"$sort": {"score": -1, "submitted_at": 1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user"
            }},
            {"$unwind": "$user"},
            {"$project": {
                "user_id": 1,
                "user_name": "$user.full_name",
                "score": 1,
                "submitted_at": 1,
                "execution_time": "$ai_feedback.execution_time",
                "department": "$user.department"
            }}
        ]
        
        leaderboard = list(await submissions_collection.aggregate(pipeline).to_list(length=limit))
        
        return [
            {
                "rank": idx + 1,
                "user_id": entry["user_id"],
                "user_name": entry["user_name"],
                "score": entry["score"],
                "submitted_at": entry["submitted_at"],
                "department": entry.get("department"),
                "execution_time": entry.get("execution_time")
            }
            for idx, entry in enumerate(leaderboard)
        ]
    except:
        return []

@app.post("/api/challenges/{challenge_id}/submit", tags=["Challenges"])
async def submit_challenge(
    challenge_id: str,
    submission_type: str = Form(...),
    code: Optional[str] = Form(None),
    audio_text: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
    text_answer: Optional[str] = Form(None),
    file_upload: Optional[UploadFile] = File(None),
    current_user: dict = Depends(verify_token),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Submit a challenge solution"""
    try:
        user_id = str(current_user["_id"])
        
        # Get challenge
        challenge = await challenges_collection.find_one({"_id": ObjectId(challenge_id)})
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Check if user can submit (not exceeding max attempts)
        max_attempts = challenge.get("max_attempts", 3)
        user_attempts = await submissions_collection.count_documents({
            "user_id": user_id,
            "challenge_id": challenge_id
        })
        
        if user_attempts >= max_attempts:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum attempts ({max_attempts}) exceeded for this challenge"
            )
        
        submission_data = {
            "user_id": user_id,
            "user_name": current_user["full_name"],
            "challenge_id": challenge_id,
            "challenge_title": challenge["title"],
            "challenge_type": challenge["challenge_type"],
            "submission_type": submission_type,
            "submitted_at": datetime.now(timezone.utc),
            "completed": False,
            "score": 0,
            "credits_earned": 0,
            "time_spent": 0
        }
        
        # Process based on challenge type
        if challenge["challenge_type"] == "voice":
            # Handle voice challenge
            if audio_file:
                audio_bytes = await audio_file.read()
                spoken_text = await SpeechService.speech_to_text(audio_bytes)
                submission_data["audio_file"] = base64.b64encode(audio_bytes).decode()
                submission_data["spoken_text"] = spoken_text
            elif audio_text:
                submission_data["spoken_text"] = audio_text
            else:
                raise HTTPException(status_code=400, detail="No audio input provided")
            
            # Analyze with AI
            analysis = await AIService.analyze_english_with_gemini(
                submission_data["spoken_text"],
                challenge.get("correct_text", "")
            )
            
            submission_data["ai_feedback"] = analysis
            submission_data["score"] = analysis.get("pronunciation_score", 0)
            submission_data["completed"] = submission_data["score"] >= 60
            
        elif challenge["challenge_type"] == "coding":
            # Handle coding challenge
            if not code:
                raise HTTPException(status_code=400, detail="No code provided")
            
            submission_data["code"] = code
            submission_data["language"] = challenge.get("language", "python")
            
            # Execute code with test cases
            test_cases = challenge.get("test_cases", [])
            execution_result = await CompilerService.execute_code_safely(
                code,
                submission_data["language"],
                test_cases=test_cases
            )
            
            # Code review
            review = await AIService.code_review(
                code,
                submission_data["language"],
                challenge.get("requirements", [])
            )
            
            submission_data["execution_result"] = execution_result
            submission_data["ai_feedback"] = review
            
            # Calculate score
            correctness_score = review.get("correctness_score", 0)
            test_pass_rate = 0
            
            if execution_result.get("test_results"):
                passed_tests = sum(1 for t in execution_result["test_results"] if t["passed"])
                total_tests = len(execution_result["test_results"])
                test_pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            submission_data["score"] = (correctness_score * 0.6) + (test_pass_rate * 0.4)
            submission_data["completed"] = submission_data["score"] >= 70
            submission_data["test_results"] = execution_result.get("test_results", [])
            
        elif challenge["challenge_type"] == "quiz":
            # Handle quiz challenge
            if not text_answer:
                raise HTTPException(status_code=400, detail="No answer provided")
            
            submission_data["answer"] = text_answer
            
            # Compare with correct answer
            correct_answer = challenge.get("correct_answer", "")
            is_correct = text_answer.strip().lower() == correct_answer.strip().lower()
            
            submission_data["score"] = 100 if is_correct else 0
            submission_data["completed"] = is_correct
            submission_data["correct"] = is_correct
            
        else:
            # For other challenge types
            submission_data["text_answer"] = text_answer
            submission_data["score"] = 0
            submission_data["needs_grading"] = True
        
        # Calculate credits earned
        if submission_data["completed"]:
            base_credits = challenge["credits_reward"]
            score_multiplier = submission_data["score"] / 100
            streak_bonus = current_user.get("daily_login_streak", 0) * 0.1
            
            credits_earned = base_credits * score_multiplier * (1 + streak_bonus)
            submission_data["credits_earned"] = int(credits_earned)
            
            # Update user credits
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"credits": submission_data["credits_earned"]}}
            )
        
        # Save submission
        result = await submissions_collection.insert_one(submission_data)
        submission_id = str(result.inserted_id)
        
        # Update user stats
        if submission_data["completed"]:
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"completed_challenges": 1}}
            )
            
            # Update stage progress
            progress_increment = 100 / 10
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"current_stage_progress": progress_increment}}
            )
            
            # Check for stage promotion
            user = await users_collection.find_one({"_id": ObjectId(user_id)})
            current_progress = user.get("current_stage_progress", 0)
            current_stage = user.get("stage", Stage.FRESHIE.value)
            
            if current_progress >= 100:
                new_stage = get_next_stage(current_stage)
                if new_stage:
                    await users_collection.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": {
                            "stage": new_stage.value,
                            "current_stage_progress": 0,
                            "stage_promoted_at": datetime.now(timezone.utc)
                        }}
                    )
                    
                    # Send promotion notification
                    await NotificationService.create_notification(
                        user_id=user_id,
                        title="🎉 Stage Promotion!",
                        message=f"Congratulations! You've been promoted to {new_stage.value.replace('_', ' ').title()} stage!",
                        notification_type="achievement",
                        priority="high"
                    )
        
        # Process in background
        background_tasks.add_task(process_submission_async, submission_id)
        
        # Send notification
        await NotificationService.create_notification(
            user_id=user_id,
            title="Challenge Submitted!",
            message=f"Your submission for '{challenge['title']}' has been processed. Score: {submission_data['score']}/100",
            notification_type="submission",
            priority="low",
            data={
                "challenge_id": challenge_id,
                "submission_id": submission_id,
                "score": submission_data["score"],
                "completed": submission_data["completed"]
            }
        )
        
        return {
            "submission_id": submission_id,
            "score": submission_data["score"],
            "completed": submission_data["completed"],
            "credits_earned": submission_data.get("credits_earned", 0),
            "feedback": submission_data.get("ai_feedback", {}),
            "test_results": submission_data.get("test_results", []),
            "needs_grading": submission_data.get("needs_grading", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit challenge error: {e}")
        raise HTTPException(status_code=500, detail="Submission failed")

def get_next_stage(current_stage: str):
    """Get the next stage after current stage"""
    stages = [Stage.FRESHIE, Stage.SOPHOMORE, Stage.JUNIOR, Stage.FINAL_YEAR, Stage.ALUMNI]
    try:
        current_index = stages.index(Stage(current_stage))
        if current_index < len(stages) - 1:
            return stages[current_index + 1]
    except:
        pass
    return None

# Compiler Routes
# Compiler Routes
@app.post("/api/compiler/execute", tags=["Compiler"])
async def execute_code(
    code_data: CodeExecution,
    current_user: dict = Depends(verify_token)
):
    """Execute code in sandbox environment"""
    try:
        # Validate input
        if not code_data.code or len(code_data.code.strip()) == 0:
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        
        if len(code_data.code) > 50000:  # 50KB limit
            raise HTTPException(status_code=400, detail="Code too large (max 50KB)")
        
        # Execute code
        result = await CompilerService.execute_code_safely(
            code=code_data.code,
            language=code_data.language,
            input_data=code_data.input_data,
            test_cases=code_data.test_cases
        )
        
        # Save to history only if successful or has meaningful output
        if result["success"] or result["output"] or result["error"]:
            await online_compiler_collection.insert_one({
                "user_id": str(current_user["_id"]),
                "user_name": current_user["full_name"],
                "code": code_data.code[:5000],  # Limit stored code size
                "language": code_data.language,
                "input": code_data.input_data[:1000] if code_data.input_data else "",
                "output": result.get("output", "")[:5000],
                "error": result.get("error", "")[:2000],
               "compile_error": result.get("compile_error", "")[:2000] if result.get("compile_error") else "",
                "success": result.get("success", False),
                "return_code": result.get("return_code", -1),
                "execution_time": result.get("execution_time", 0),
                "test_results": result.get("test_results", []),
                "executed_at": datetime.now(timezone.utc)
            })
        
        return {
            "success": result["success"],
            "output": result["output"],
            "error": result["error"],
            "compile_error": result.get("compile_error"),
            "return_code": result["return_code"],
            "execution_time": result.get("execution_time", 0),
            "compile_time": result.get("compile_time", 0),
            "test_results": result.get("test_results"),
            "memory_used": result.get("memory_used", 0),
            "language": result.get("language", code_data.language)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Code execution endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Code execution failed: {str(e)}")

@app.get("/api/compiler/history", tags=["Compiler"])
async def get_compiler_history(
    language: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get code execution history"""
    try:
        user_id = str(current_user["_id"])
        
        query = {"user_id": user_id}
        if language:
            query["language"] = language
        
        total = await online_compiler_collection.count_documents(query)
        
        history = await online_compiler_collection.find(query) \
            .sort("executed_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "history": [
                {
                    "id": str(h["_id"]),
                    "language": h["language"],
                    "code_preview": h["code"][:100] + "..." if len(h["code"]) > 100 else h["code"],
                    "success": h["success"],
                    "output": h.get("output", "")[:200],
                    "error": h.get("error", "")[:200],
                    "execution_time": h.get("execution_time", 0),
                    "executed_at": h["executed_at"]
                }
                for h in history
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get compiler history error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get compiler history")

# AI Chat Routes
@app.post("/api/ai/chat", tags=["AI"])
async def ai_chat(
    chat_message: AIChatMessage,
    current_user: dict = Depends(verify_token)
):
    """Chat with AI assistant"""
    try:
        user_id = str(current_user["_id"])
        
        # Get or create chat history
        chat_history_id = chat_message.chat_history_id
        if not chat_history_id:
            # Create new chat session
            chat_session = {
                "user_id": user_id,
                "title": chat_message.message[:50] + ("..." if len(chat_message.message) > 50 else ""),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "messages": []
            }
            result = await ai_chats_collection.insert_one(chat_session)
            chat_history_id = str(result.inserted_id)
        
        # Get user context
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        user_context = {
            "name": user["full_name"],
            "stage": user.get("stage", "freshie"),
            "department": user.get("department", ""),
            "skills": user.get("skills", []),
            "interests": user.get("interests", []),
            "weak_areas": user.get("weak_areas", []),
            "completed_challenges": user.get("completed_challenges", 0)
        }
        
        # Get chat history
        chat_session = await ai_chats_collection.find_one({"_id": ObjectId(chat_history_id)})
        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Get AI response
        context = chat_message.context or json.dumps(user_context, default=str)
        ai_response = await AIService.chat_assistant(chat_message.message, {"context": context})
        
        # Save messages
        user_msg = {
            "role": "user",
            "content": chat_message.message,
            "timestamp": datetime.now(timezone.utc)
        }
        
        ai_msg = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now(timezone.utc)
        }
        
        await ai_chats_collection.update_one(
            {"_id": ObjectId(chat_history_id)},
            {
                "$push": {"messages": {"$each": [user_msg, ai_msg]}},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        return {
            "chat_history_id": chat_history_id,
            "response": ai_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        raise HTTPException(status_code=500, detail="AI chat failed")

@app.get("/api/ai/chats", tags=["AI"])
async def get_ai_chats(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get AI chat history"""
    try:
        user_id = str(current_user["_id"])
        
        total = await ai_chats_collection.count_documents({"user_id": user_id})
        
        chats = await ai_chats_collection.find({"user_id": user_id}) \
            .sort("updated_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "chats": [
                {
                    "id": str(chat["_id"]),
                    "title": chat["title"],
                    "message_count": len(chat.get("messages", [])),
                    "created_at": chat["created_at"],
                    "updated_at": chat["updated_at"],
                    "last_message": chat.get("messages", [])[-1]["content"][:100] + "..." 
                        if chat.get("messages") and len(chat["messages"]) > 0 else "No messages"
                }
                for chat in chats
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get AI chats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat history")

# English Teacher AI Routes
@app.post("/api/ai/english-teacher", tags=["AI"])
async def english_teacher(
    text: str = Form(..., min_length=1, max_length=1000),
    current_user: dict = Depends(verify_token)
):
    """Get English grammar and pronunciation feedback with Tamil explanations"""
    try:
        feedback = await AIService.english_teacher_feedback(text)
        
        return {
            "feedback": feedback,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"English teacher error: {e}")
        raise HTTPException(status_code=500, detail="English teacher analysis failed")

# Speech Routes
@app.post("/api/speech/text-to-speech", tags=["Speech"])
async def text_to_speech_endpoint(
    text: str = Form(..., min_length=1, max_length=1000),
    language: str = Form("ta"),
    speed: float = Form(1.0, ge=0.5, le=2.0),
    current_user: dict = Depends(verify_token)
):
    """Convert text to speech"""
    try:
        audio_bytes = await SpeechService.text_to_speech(text, language, speed)
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3",
                "Content-Length": str(len(audio_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Text to speech error: {e}")
        raise HTTPException(status_code=500, detail="Text to speech conversion failed")

@app.post("/api/speech/speech-to-text", tags=["Speech"])
async def speech_to_text_endpoint(
    audio_file: UploadFile = File(...),
    language: str = Form("en-US"),
    current_user: dict = Depends(verify_token)
):
    """Convert speech to text"""
    try:
        audio_bytes = await audio_file.read()
        text = await SpeechService.speech_to_text(audio_bytes, language)
        
        return {"text": text}
        
    except Exception as e:
        logger.error(f"Speech to text error: {e}")
        raise HTTPException(status_code=500, detail="Speech to text conversion failed")

@app.post("/api/speech/analyze-pronunciation", tags=["Speech"])
async def analyze_pronunciation_endpoint(
    audio_file: UploadFile = File(...),
    reference_text: str = Form(...),
    current_user: dict = Depends(verify_token)
):
    """Analyze pronunciation with AI feedback"""
    try:
        audio_bytes = await audio_file.read()
        analysis = await SpeechService.analyze_pronunciation(audio_bytes, reference_text)
        
        return {
            "analysis": analysis,
            "recommendations": analysis.get("correction_suggestions", []),
            "improvement_plan": analysis.get("improvement_plan", []),
        }
        
    except Exception as e:
        logger.error(f"Pronunciation analysis error: {e}")
        raise HTTPException(status_code=500, detail="Pronunciation analysis failed")

# Project Routes
@app.get("/api/projects", tags=["Projects"])
async def get_projects(
    status: Optional[str] = None,
    project_type: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get projects with filters"""
    try:
        user_id = str(current_user["_id"])
        
        query = {}
        
        # For students, show their projects and public projects
        if current_user["user_type"] == UserType.STUDENT:
            query["$or"] = [
                {"team_members": user_id},
                {"visibility": "public"}
            ]
        
        if status:
            query["status"] = status
        if project_type:
            query["project_type"] = project_type
        if tags:
            query["tags"] = {"$in": tags.split(",")}
        
        total = await projects_collection.count_documents(query)
        
        projects = await projects_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "projects": [
                {
                    "id": str(p["_id"]),
                    "title": p["title"],
                    "description": p["description"],
                    "project_type": p["project_type"],
                    "status": p["status"],
                    "creator_name": p["creator_name"],
                    "team_size": len(p.get("team_members", [])),
                    "tech_stack": p.get("tech_stack", []),
                    "tags": p.get("tags", []),
                    "created_at": p["created_at"],
                    "updated_at": p.get("updated_at"),
                    "github_repo": p.get("github_repo"),
                    "website": p.get("website"),
                    "is_member": user_id in p.get("team_members", []),
                    "is_creator": p["creator_id"] == user_id
                }
                for p in projects
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get projects error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get projects")

# Group Routes - FIXED AND ENHANCED
@app.post("/api/groups", tags=["Groups"])
async def create_group(
    group_data: GroupCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new study group"""
    try:
        user_id = str(current_user["_id"])
        
        # Check if group name exists
        existing = await groups_collection.find_one({
            "name": group_data.name,
            "department": group_data.department,
            "year": group_data.year
        })
        
        if existing:
            raise HTTPException(status_code=400, detail="Group with this name already exists in your department/year")
        
        group = {
            "name": group_data.name,
            "description": group_data.description,
            "department": group_data.department,
            "year": group_data.year,
            "created_by": user_id,
            "created_by_name": current_user["full_name"],
            "members": [user_id],
            "admins": [user_id],
            "is_educational": group_data.is_educational,
            "privacy": group_data.privacy,
            "max_members": group_data.max_members,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "messages": [],
            "files": [],
            "code_repositories": [],
            "ai_assistant_enabled": True,
            "assistant_model": OLLAMA_MODEL
        }
        
        result = await groups_collection.insert_one(group)
        group_id = str(result.inserted_id)
        
        # Create group chat with AI assistant
        ai_message = {
            "sender_id": "ai_assistant",
            "sender_name": "AI Assistant",
            "content": f"Hello everyone! I'm your group's AI assistant. I can help with coding questions, explain concepts, and assist with learning. Type '@assistant' followed by your question to get my help!",
            "message_type": "system",
            "timestamp": datetime.now(timezone.utc)
        }
        
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"messages": ai_message}}
        )
        
        return {
            "message": "Group created successfully",
            "group_id": group_id,
            "group": {
                "id": group_id,
                "name": group["name"],
                "description": group["description"],
                "department": group["department"],
                "year": group["year"],
                "member_count": 1,
                "is_admin": True,
                "ai_assistant_enabled": True
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create group error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create group")

@app.get("/api/groups", tags=["Groups"])
async def get_groups(
    department: Optional[str] = None,
    year: Optional[int] = None,
    is_educational: Optional[bool] = None,
    privacy: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get study groups with filters"""
    try:
        user_id = str(current_user["_id"])
        
        query = {}
        
        # Build query based on user type and preferences
        if current_user["user_type"] == UserType.STUDENT:
            user_dept = current_user.get("department")
            user_year = current_user.get("year")
            
            query["$or"] = [
                {"members": user_id},
                {"privacy": "public"},
                {"privacy": "invite_only", "department": user_dept, "year": user_year}
            ]
            
            if is_educational:
                query["is_educational"] = is_educational
        
        if department:
            query["department"] = department
        if year:
            query["year"] = year
        if privacy:
            query["privacy"] = privacy
        if is_educational is not None:
            query["is_educational"] = is_educational
        
        total = await groups_collection.count_documents(query)
        
        groups = await groups_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "groups": [
                {
                    "id": str(g["_id"]),
                    "name": g["name"],
                    "description": g["description"],
                    "department": g.get("department"),
                    "year": g.get("year"),
                    "created_by": g["created_by_name"],
                    "member_count": len(g.get("members", [])),
                    "max_members": g.get("max_members", 100),
                    "is_member": user_id in g.get("members", []),
                    "is_admin": user_id in g.get("admins", []),
                    "created_at": g["created_at"],
                    "is_educational": g.get("is_educational", True),
                    "privacy": g.get("privacy", "public"),
                    "ai_assistant_enabled": g.get("ai_assistant_enabled", False),
                    "last_message": g.get("messages", [])[-1]["content"][:100] + "..." if g.get("messages") else "No messages yet"
                }
                for g in groups
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get groups error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get groups")

@app.post("/api/groups/{group_id}/join", tags=["Groups"])
async def join_group(
    group_id: str,
    current_user: dict = Depends(verify_token)
):
    """Join a study group"""
    try:
        user_id = str(current_user["_id"])
        
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Check if user is already a member
        if user_id in group.get("members", []):
            raise HTTPException(status_code=400, detail="Already a member of this group")
        
        # Check if group is full
        if len(group.get("members", [])) >= group.get("max_members", 100):
            raise HTTPException(status_code=400, detail="Group is full")
        
        # Check privacy settings
        if group.get("privacy") == "private":
            raise HTTPException(status_code=403, detail="This is a private group")
        
        # Add user to group
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"members": user_id}}
        )
        
        # Send welcome message
        welcome_message = {
            "sender_id": "system",
            "sender_name": "System",
            "content": f"{current_user['full_name']} has joined the group!",
            "message_type": "system",
            "timestamp": datetime.now(timezone.utc)
        }
        
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"messages": welcome_message}}
        )
        
        # Send notification to group admins
        for admin_id in group.get("admins", []):
            await NotificationService.create_notification(
                user_id=admin_id,
                title="New Group Member",
                message=f"{current_user['full_name']} has joined your group '{group['name']}'",
                notification_type="group",
                priority="low",
                action_url=f"/groups/{group_id}"
            )
        
        return {"message": "Successfully joined the group"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Join group error: {e}")
        raise HTTPException(status_code=500, detail="Failed to join group")

@app.get("/api/groups/{group_id}/messages", tags=["Groups"])
async def get_group_messages(
    group_id: str,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get group messages"""
    try:
        user_id = str(current_user["_id"])
        
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Check if user is a member
        if user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="Not a member of this group")
        
        messages = group.get("messages", [])
        
        # Apply pagination
        total_messages = len(messages)
        start_idx = max(0, total_messages - skip - limit)
        end_idx = total_messages - skip
        paginated_messages = messages[max(0, start_idx):end_idx]
        
        return {
            "messages": paginated_messages,
            "pagination": {
                "total": total_messages,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total_messages
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get group messages error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get group messages")

@app.post("/api/groups/{group_id}/messages", tags=["Groups"])
async def send_group_message(
    group_id: str,
    message_data: MessageSend,
    current_user: dict = Depends(verify_token)
):
    """Send message to group"""
    try:
        user_id = str(current_user["_id"])
        
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Check if user is a member
        if user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="Not a member of this group")
        
        message = {
            "sender_id": user_id,
            "sender_name": current_user["full_name"],
            "content": message_data.content,
            "message_type": message_data.message_type,
            "reply_to": message_data.reply_to,
            "file_url": message_data.file_url,
            "file_name": message_data.file_name,
            "timestamp": datetime.now(timezone.utc)
        }
        
        # Check if message is for AI assistant
        if message_data.content.startswith("@assistant") and group.get("ai_assistant_enabled", False):
            # Extract question
            question = message_data.content.replace("@assistant", "").strip()
            
            # Get AI response
            context = f"Group: {group['name']}, Department: {group['department']}, Year: {group['year']}, Educational: {group['is_educational']}"
            ai_response = await AIService.chat_assistant(question, {"context": context})
            
            # Add user message
            await groups_collection.update_one(
                {"_id": ObjectId(group_id)},
                {"$push": {"messages": message}}
            )
            
            # Add AI response
            ai_message = {
                "sender_id": "ai_assistant",
                "sender_name": "AI Assistant",
                "content": ai_response,
                "message_type": "ai",
                "timestamp": datetime.now(timezone.utc)
            }
            
            await groups_collection.update_one(
                {"_id": ObjectId(group_id)},
                {"$push": {"messages": ai_message}}
            )
            
            # Broadcast via WebSocket
            await WebSocketManager.broadcast_to_group(group_id, {
                "type": "new_message",
                "group_id": group_id,
                "message": message
            }, user_id)
            
            await WebSocketManager.broadcast_to_group(group_id, {
                "type": "new_message",
                "group_id": group_id,
                "message": ai_message
            })
            
            return {
                "message": "Message and AI response sent successfully",
                "user_message": message,
                "ai_response": ai_message
            }
        
        # Regular message
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"messages": message}}
        )
        
        # Broadcast via WebSocket
        await WebSocketManager.broadcast_to_group(group_id, {
            "type": "new_message",
            "group_id": group_id,
            "message": message
        }, user_id)
        
        return {"message": "Message sent successfully", "data": message}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send group message error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@app.post("/api/groups/{group_id}/files", tags=["Groups"])
async def upload_group_file(
    group_id: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    current_user: dict = Depends(verify_token)
):
    """Upload file to group"""
    try:
        user_id = str(current_user["_id"])
        
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Check if user is a member
        if user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="Not a member of this group")
        
        # Validate and upload file
        content, file_size = await validate_file(file)
        
        upload_result = await upload_to_cloud_storage(
            content,
            f"group_{group_id}_{datetime.now().timestamp()}_{file.filename}",
            file.content_type or "application/octet-stream"
        )
        
        # Add file to group
        file_record = {
            "id": str(uuid.uuid4()),
            "name": file.filename,
            "url": upload_result["url"],
            "uploaded_by": user_id,
            "uploaded_by_name": current_user["full_name"],
            "description": description,
            "size": file_size,
            "type": file.content_type,
            "uploaded_at": datetime.now(timezone.utc)
        }
        
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"files": file_record}}
        )
        
        # Send notification
        message = {
            "sender_id": user_id,
            "sender_name": current_user["full_name"],
            "content": f"Uploaded file: {file.filename}",
            "message_type": "file",
            "file_url": upload_result["url"],
            "file_name": file.filename,
            "timestamp": datetime.now(timezone.utc)
        }
        
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"messages": message}}
        )
        
        # Broadcast via WebSocket
        await WebSocketManager.broadcast_to_group(group_id, {
            "type": "new_file",
            "group_id": group_id,
            "file": file_record
        })
        
        await WebSocketManager.broadcast_to_group(group_id, {
            "type": "new_message",
            "group_id": group_id,
            "message": message
        }, user_id)
        
        return {
            "message": "File uploaded successfully",
            "file": file_record
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload group file error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")

# Job Routes
@app.get("/api/jobs", tags=["Jobs"])
async def get_jobs(
    department: Optional[str] = None,
    role: Optional[str] = None,
    company: Optional[str] = None,
    experience: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get job listings with filters"""
    try:
        query = {"status": "active"}
        
        if department:
            query["preferred_departments"] = department
        if role:
            query["role"] = {"$regex": role, "$options": "i"}
        if company:
            query["company"] = {"$regex": company, "$options": "i"}
        if experience:
            query["experience_required"] = experience
        if location:
            query["location"] = {"$regex": location, "$options": "i"}
        
        total = await jobs_collection.count_documents(query)
        
        jobs = await jobs_collection.find(query) \
            .sort("posted_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        user_id = str(current_user["_id"])
        
        return {
            "jobs": [
                {
                    "id": str(j["_id"]),
                    "company": j["company"],
                    "role": j["role"],
                    "description": j["description"],
                    "requirements": j.get("requirements", []),
                    "salary_range": j.get("salary_range"),
                    "location": j.get("location"),
                    "posted_at": j["posted_at"],
                    "apply_by": j.get("apply_by"),
                    "preferred_departments": j.get("preferred_departments", []),
                    "experience_required": j.get("experience_required", "Fresher"),
                    "job_type": j.get("job_type", "Full-time"),
                    "application_count": len(j.get("applications", [])),
                    "has_applied": user_id in j.get("applications", [])
                }
                for j in jobs
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get jobs error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get jobs")

# Notification Routes
@app.get("/api/notifications", tags=["Notifications"])
async def get_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get user notifications"""
    try:
        user_id = str(current_user["_id"])
        
        query = {
            "$or": [
                {"user_id": user_id},
                {"broadcast": True}
            ]
        }
        
        if unread_only:
            query["read"] = False
        
        total = await notifications_collection.count_documents(query)
        
        notifications = await notifications_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "notifications": [
                {
                    "id": str(n["_id"]),
                    "title": n["title"],
                    "message": n["message"],
                    "type": n["type"],
                    "priority": n.get("priority", "normal"),
                    "created_at": n["created_at"],
                    "read": n.get("read", False),
                    "action_url": n.get("action_url"),
                    "data": n.get("data", {})
                }
                for n in notifications
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            },
            "unread_count": await notifications_collection.count_documents({
                "$or": [
                    {"user_id": user_id},
                    {"broadcast": True}
                ],
                "read": False
            })
        }
        
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get notifications")

@app.post("/api/notifications/{notification_id}/read", tags=["Notifications"])
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(verify_token)
):
    """Mark notification as read"""
    try:
        user_id = str(current_user["_id"])
        
        result = await notifications_collection.update_one(
            {
                "_id": ObjectId(notification_id),
                "$or": [
                    {"user_id": user_id},
                    {"broadcast": True}
                ]
            },
            {"$set": {"read": True}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {"message": "Notification marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark notification read error: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")

@app.post("/api/notifications/read-all", tags=["Notifications"])
async def mark_all_notifications_read(current_user: dict = Depends(verify_token)):
    """Mark all notifications as read"""
    try:
        user_id = str(current_user["_id"])
        
        await notifications_collection.update_many(
            {
                "$or": [
                    {"user_id": user_id},
                    {"broadcast": True}
                ],
                "read": False
            },
            {"$set": {"read": True}}
        )
        
        return {"message": "All notifications marked as read"}
        
    except Exception as e:
        logger.error(f"Mark all notifications read error: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark all notifications as read")

# Submission Routes
@app.get("/api/submissions", tags=["Submissions"])
async def get_submissions(
    challenge_id: Optional[str] = None,
    completed: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get user submissions"""
    try:
        user_id = str(current_user["_id"])
        
        query = {"user_id": user_id}
        
        if challenge_id:
            query["challenge_id"] = challenge_id
        if completed is not None:
            query["completed"] = completed
        
        total = await submissions_collection.count_documents(query)
        
        submissions = await submissions_collection.find(query) \
            .sort("submitted_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "submissions": [
                {
                    "id": str(sub["_id"]),
                    "challenge_id": sub["challenge_id"],
                    "challenge_title": sub["challenge_title"],
                    "challenge_type": sub["challenge_type"],
                    "score": sub.get("score", 0),
                    "completed": sub.get("completed", False),
                    "submitted_at": sub.get("submitted_at"),
                    "credits_earned": sub.get("credits_earned", 0),
                    "language": sub.get("language"),
                    "has_feedback": "ai_feedback" in sub
                }
                for sub in submissions
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get submissions error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get submissions")

# Badges Routes
@app.get("/api/badges", tags=["Badges"])
async def get_badges(current_user: dict = Depends(verify_token)):
    """Get user badges"""
    try:
        user_id = str(current_user["_id"])
        
        badges_doc = await badges_collection.find_one({"user_id": user_id})
        
        if not badges_doc:
            return {
                "badges": [],
                "total_badges": 0,
                "categories": {}
            }
        
        badges = badges_doc.get("badges", [])
        
        # Group by category
        categories = {}
        for badge in badges:
            category = badge.get("category", "uncategorized")
            if category not in categories:
                categories[category] = []
            categories[category].append(badge)
        
        return {
            "badges": badges,
            "total_badges": len(badges),
            "categories": categories
        }
        
    except Exception as e:
        logger.error(f"Get badges error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get badges")

# Leaderboard Routes
@app.get("/api/leaderboard", tags=["Leaderboard"])
async def get_leaderboard(
    period: str = Query("weekly", pattern="^(weekly|monthly|all_time)$"),
    department: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(verify_token)
):
    """Get leaderboard with filters"""
    try:
        user_id = str(current_user["_id"])
        
        # For weekly leaderboard
        if period == "weekly":
            # Get submissions from last 7 days
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            pipeline = [
                {"$match": {
                    "submitted_at": {"$gte": week_ago},
                    "completed": True
                }},
                {"$group": {
                    "_id": "$user_id",
                    "total_score": {"$sum": "$score"},
                    "challenges_completed": {"$sum": 1},
                    "average_score": {"$avg": "$score"}
                }},
                {"$sort": {"total_score": -1}},
                {"$limit": limit},
                {"$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user"
                }},
                {"$unwind": "$user"},
                {"$match": {
                    "user.user_type": UserType.STUDENT.value,
                    **({"user.department": department} if department else {}),
                    **({"user.year": year} if year else {})
                }},
                {"$project": {
                    "user_id": "$_id",
                    "user_name": "$user.full_name",
                    "department": "$user.department",
                    "year": "$user.year",
                    "stage": "$user.stage",
                    "profile_picture": "$user.profile_picture",
                    "total_score": 1,
                    "challenges_completed": 1,
                    "average_score": 1
                }}
            ]
            
            leaderboard = list(await submissions_collection.aggregate(pipeline).to_list(length=limit))
            
        else:
            # For monthly/all_time, get from leaderboard collection
            query = {"period": period}
            if period == "monthly":
                month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                query["month_start"] = month_start
            
            leaderboard_entries = await leaderboard_collection.find(query) \
                .sort("total_score", -1) \
                .limit(limit) \
                .to_list(limit)
            
            # Get user details
            leaderboard = []
            for entry in leaderboard_entries:
                user = await users_collection.find_one({"_id": ObjectId(entry["user_id"])})
                if user and user["user_type"] == UserType.STUDENT.value:
                    if (department and user.get("department") != department) or \
                       (year and user.get("year") != year):
                        continue
                    
                    leaderboard.append({
                        "user_id": entry["user_id"],
                        "user_name": user["full_name"],
                        "department": user.get("department"),
                        "year": user.get("year"),
                        "stage": user.get("stage"),
                        "profile_picture": user.get("profile_picture"),
                        "total_score": entry["total_score"],
                        "challenges_completed": entry["challenges_completed"],
                        "average_score": entry.get("average_score", 0)
                    })
        
        # Get user's rank and score
        user_rank = 0
        user_score = 0
        
        for idx, entry in enumerate(leaderboard):
            if entry["user_id"] == user_id:
                user_rank = idx + 1
                user_score = entry["total_score"]
                break
        
        return {
            "period": period,
            "leaderboard": [
                {
                    "rank": idx + 1,
                    **entry
                }
                for idx, entry in enumerate(leaderboard)
            ],
            "user_stats": {
                "rank": user_rank,
                "score": user_score,
                "in_top": user_rank > 0 and user_rank <= limit
            }
        }
        
    except Exception as e:
        logger.error(f"Get leaderboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get leaderboard")

# Learning Path Routes
@app.post("/api/learning-paths/generate", tags=["Learning Path"])
async def generate_learning_path(
    request: LearningPathRequest,
    current_user: dict = Depends(verify_token)
):
    """Generate personalized learning path"""
    try:
        user_id = str(current_user["_id"])
        
        # Get user data
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate learning path with AI
        learning_path = await AIService.generate_learning_path({
            "stage": user.get("stage", "freshie"),
            "department": user.get("department", "Computer Science"),
            "skills": user.get("skills", []),
            "weak_areas": request.focus_areas,
            "interests": user.get("interests", []),
            "career_goals": request.goals
        })
        
        # Save learning path
        path_id = str(uuid.uuid4())
        path_doc = {
            "id": path_id,
            "user_id": user_id,
            "focus_areas": request.focus_areas,
            "goals": request.goals,
            "duration_days": request.duration_days,
            "learning_path": learning_path,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "current_day": 1,
            "completed_days": [],
            "progress": 0
        }
        
        await learning_paths_collection.insert_one(path_doc)
        
        return {
            "message": "Learning path generated successfully",
            "path_id": path_id,
            "learning_path": learning_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate learning path error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate learning path")

@app.get("/api/learning-paths", tags=["Learning Path"])
async def get_learning_paths(
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get user's learning paths"""
    try:
        user_id = str(current_user["_id"])
        
        total = await learning_paths_collection.count_documents({"user_id": user_id})
        
        paths = await learning_paths_collection.find({"user_id": user_id}) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "learning_paths": [
                {
                    "id": p["id"],
                    "focus_areas": p["focus_areas"],
                    "goals": p["goals"],
                    "duration_days": p["duration_days"],
                    "current_day": p["current_day"],
                    "progress": p["progress"],
                    "created_at": p["created_at"],
                    "overview": p["learning_path"].get("overview", "")[:200] + "..."
                }
                for p in paths
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get learning paths error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get learning paths")

# Forum Routes
@app.post("/api/forum/posts", tags=["Forum"])
async def create_forum_post(
    post_data: ForumPostCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a forum post"""
    try:
        user_id = str(current_user["_id"])
        
        post = {
            "id": str(uuid.uuid4()),
            "title": post_data.title,
            "content": post_data.content,
            "author_id": user_id,
            "author_name": current_user["full_name"],
            "tags": post_data.tags,
            "category": post_data.category,
            "is_anonymous": post_data.is_anonymous,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "views": 0,
            "upvotes": 0,
            "downvotes": 0,
            "comments": 0,
            "is_resolved": False,
            "is_pinned": False
        }
        
        if post_data.is_anonymous:
            post["author_name"] = "Anonymous"
        
        await forum_posts_collection.insert_one(post)
        
        return {
            "message": "Forum post created successfully",
            "post_id": post["id"],
            "post": post
        }
        
    except Exception as e:
        logger.error(f"Create forum post error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create forum post")

@app.get("/api/forum/posts", tags=["Forum"])
async def get_forum_posts(
    category: Optional[str] = None,
    tags: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get forum posts with filters"""
    try:
        query = {}
        
        if category:
            query["category"] = category
        if tags:
            query["tags"] = {"$in": tags.split(",")}
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}}
            ]
        
        total = await forum_posts_collection.count_documents(query)
        
        posts = await forum_posts_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "posts": [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "content": p["content"][:200] + ("..." if len(p["content"]) > 200 else ""),
                    "author_name": p["author_name"],
                    "tags": p["tags"],
                    "category": p["category"],
                    "created_at": p["created_at"],
                    "views": p["views"],
                    "upvotes": p["upvotes"],
                    "downvotes": p["downvotes"],
                    "comments": p["comments"],
                    "is_resolved": p["is_resolved"],
                    "is_pinned": p["is_pinned"]
                }
                for p in posts
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get forum posts error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get forum posts")

# Additional Routes
@app.get("/api/announcements", tags=["Announcements"])
async def get_announcements(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get announcements"""
    try:
        query = {"active": True}
        
        total = await announcements_collection.count_documents(query)
        
        announcements = await announcements_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "announcements": [
                {
                    "id": str(ann["_id"]),
                    "title": ann["title"],
                    "content": ann["content"],
                    "type": ann.get("type", "general"),
                    "priority": ann.get("priority", "normal"),
                    "created_at": ann["created_at"],
                    "expires_at": ann.get("expires_at"),
                    "author": ann.get("author_name", "Admin")
                }
                for ann in announcements
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get announcements error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get announcements")

@app.get("/api/study-materials", tags=["Study Materials"])
async def get_study_materials(
    department: Optional[str] = None,
    year: Optional[int] = None,
    subject: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get study materials"""
    try:
        query = {}
        
        if department:
            query["department"] = department
        if year:
            query["year"] = year
        if subject:
            query["subject"] = {"$regex": subject, "$options": "i"}
        
        total = await study_materials_collection.count_documents(query)
        
        materials = await study_materials_collection.find(query) \
            .sort("uploaded_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "materials": [
                {
                    "id": str(mat["_id"]),
                    "title": mat["title"],
                    "description": mat.get("description", ""),
                    "subject": mat["subject"],
                    "department": mat.get("department"),
                    "year": mat.get("year"),
                    "file_url": mat["file_url"],
                    "file_type": mat.get("file_type"),
                    "file_size": mat.get("file_size"),
                    "uploaded_by": mat.get("uploaded_by_name"),
                    "uploaded_at": mat["uploaded_at"],
                    "download_count": mat.get("download_count", 0),
                    "tags": mat.get("tags", [])
                }
                for mat in materials
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get study materials error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get study materials")

@app.get("/api/classrooms", tags=["Classrooms"])
async def get_classrooms(
    department: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get classrooms"""
    try:
        user_id = str(current_user["_id"])
        
        query = {}
        
        if current_user["user_type"] == UserType.STUDENT:
            user_dept = current_user.get("department")
            user_year = current_user.get("year")
            
            query["$or"] = [
                {"students": user_id},
                {"department": user_dept, "year": user_year, "is_public": True}
            ]
        
        if department:
            query["department"] = department
        if year:
            query["year"] = year
        
        total = await classrooms_collection.count_documents(query)
        
        classrooms = await classrooms_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "classrooms": [
                {
                    "id": str(cls["_id"]),
                    "name": cls["name"],
                    "description": cls.get("description", ""),
                    "course_code": cls.get("course_code"),
                    "instructor_name": cls.get("instructor_name"),
                    "department": cls.get("department"),
                    "year": cls.get("year"),
                    "student_count": len(cls.get("students", [])),
                    "is_member": user_id in cls.get("students", []),
                    "created_at": cls["created_at"]
                }
                for cls in classrooms
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get classrooms error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get classrooms")

# =============== ADVANCED FEATURES ===============

# GitHub-like Code Repository Routes
@app.post("/api/repositories", tags=["Repositories"])
async def create_repository(
    repo_data: CodeRepositoryCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new code repository"""
    try:
        user_id = str(current_user["_id"])
        
        repository = await VersionControlService.create_repository(
            user_id=user_id,
            name=repo_data.name,
            description=repo_data.description,
            is_public=repo_data.is_public
        )
        
        # Clean the repository document
        cleaned_repository = clean_mongodb_document(repository)
        
        return {
            "message": "Repository created successfully",
            "repository": cleaned_repository
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create repository error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create repository")
# Clean MongoDB document BEFORE the endpoint
def clean_mongodb_document(doc):
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    doc.pop("_cls", None)
    return doc


@app.get("/api/repositories", tags=["Repositories"])
async def get_repositories(
    owner_id: Optional[str] = None,
    is_public: Optional[bool] = None,
    language: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get repositories with filters"""
    try:
        user_id = str(current_user["_id"])
        
        query = {}
        
        # Build query based on access
        if owner_id:
            query["owner_id"] = owner_id
            if owner_id != user_id:
                query["is_public"] = True
        else:
            # Show user's repos and public repos
            query["$or"] = [
                {"owner_id": user_id},
                {"collaborators": user_id},
                {"is_public": True}
            ]
        
        if is_public is not None:
            query["is_public"] = is_public
        
        if language:
            query[f"language_stats.{language}"] = {"$exists": True}
        
        total = await code_repositories_collection.count_documents(query)
        
        repositories = await code_repositories_collection.find(query) \
            .sort("updated_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Clean the documents
        cleaned_repositories = [clean_mongodb_document(repo) for repo in repositories]
        
        return {
            "repositories": cleaned_repositories,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get repositories error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get repositories")


@app.get("/api/repositories/{repository_id}", tags=["Repositories"])
async def get_repository_detail(
    repository_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get repository details"""
    try:
        user_id = str(current_user["_id"])
        
        repository = await code_repositories_collection.find_one({"id": repository_id})
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Check access
        if (not repository["is_public"] and 
            repository["owner_id"] != user_id and 
            user_id not in repository.get("collaborators", [])):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get recent commits
        recent_commits = await code_commits_collection.find({
            "repository_id": repository_id
        }).sort("timestamp", -1).limit(10).to_list(10)
        
        # Clean commits
        cleaned_commits = [clean_mongodb_document(commit) for commit in recent_commits]
        
        # Get contributors
        contributors = await code_commits_collection.aggregate([
            {"$match": {"repository_id": repository_id}},
            {"$group": {
                "_id": "$author_id",
                "commit_count": {"$sum": 1},
                "last_commit": {"$max": "$timestamp"}
            }},
            {"$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user"
            }},
            {"$unwind": "$user"},
            {"$project": {
                "user_id": {"$toString": "$_id"},  # Convert ObjectId to string
                "user_name": "$user.full_name",
                "profile_picture": "$user.profile_picture",
                "commit_count": 1,
                "last_commit": 1
            }}
        ]).to_list(10)
        
        # Get repository files
        files = await VersionControlService.get_repository_files(repository_id)
        
        # Clean the repository document
        cleaned_repository = clean_mongodb_document(repository)
        cleaned_repository["recent_commits"] = cleaned_commits
        cleaned_repository["contributors"] = contributors
        cleaned_repository["files"] = files
        cleaned_repository["can_edit"] = (cleaned_repository["owner_id"] == user_id or 
                                         user_id in cleaned_repository.get("collaborators", []))
        
        return cleaned_repository
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get repository detail error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get repository details")

@app.post("/api/repositories/{repository_id}/commits", tags=["Repositories"])
async def create_commit(
    repository_id: str,
    commit_data: CommitCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new commit"""
    try:
        user_id = str(current_user["_id"])
        
        commit = await VersionControlService.create_commit(
            repository_id=repository_id,
            user_id=user_id,
            message=commit_data.message,
            files=commit_data.files,
            branch=commit_data.branch
        )
        
        return {
            "message": "Commit created successfully",
            "commit": commit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create commit error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create commit")

# AI Code Assistance Routes
@app.post("/api/ai/code-help", tags=["AI"])
async def get_code_help(
    help_request: AICodeHelpRequest,
    current_user: dict = Depends(verify_token)
):
    """Get AI assistance for coding problems"""
    try:
        user_id = str(current_user["_id"])
        
        # Get AI help
        help_response = await AIService.code_help(
            code=help_request.code,
            error=help_request.error,
            requirement=help_request.requirement,
            language=help_request.language,
            context=help_request.context
        )
        
        # Save to database
        await ai_code_assistance_collection.insert_one({
            "user_id": user_id,
            "request": help_request.model_dump(),
            "response": help_response,
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "help": help_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Code help error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get code help")

@app.post("/api/ai/code-review", tags=["AI"])
async def code_review(
    review_request: CodeReviewRequest,
    current_user: dict = Depends(verify_token)
):
    """Get AI code review"""
    try:
        user_id = str(current_user["_id"])
        
        # Get AI review
        review = await AIService.code_review(
            code=review_request.code,
            language=review_request.language,
            requirements=review_request.requirements
        )
        
        # Save to database
        await code_reviews_collection.insert_one({
            "user_id": user_id,
            "code": review_request.code[:5000],
            "language": review_request.language,
            "review": review,
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "review": review,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Code review error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get code review")

@app.get("/api/ai/project-ideas", tags=["AI"])
async def get_project_ideas(current_user: dict = Depends(verify_token)):
    """Get AI-generated project ideas"""
    try:
        user_id = str(current_user["_id"])
        
        # Get user data
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get AI-generated project ideas
        project_ideas = await AIService.generate_project_ideas({
            "stage": user.get("stage", "freshie"),
            "skills": user.get("skills", []),
            "interests": user.get("interests", []),
            "department": user.get("department", "Computer Science")
        })
        
        return {
            "project_ideas": project_ideas,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project ideas error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project ideas")

# Pair Programming Routes
@app.post("/api/pair-programming/sessions", tags=["Pair Programming"])
async def create_pair_programming_session(
    session_data: PairProgrammingRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a pair programming session"""
    try:
        user_id = str(current_user["_id"])
        partner_id = session_data.partner_id
        
        # Check if partner exists
        partner = await users_collection.find_one({"_id": ObjectId(partner_id)})
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")
        
        # Check if partner is available (simplified check)
        # In production, you'd check for active sessions
        
        session_id = str(uuid.uuid4())
        
        session = {
            "session_id": session_id,
            "user1_id": user_id,
            "user2_id": partner_id,
            "language": session_data.language,
            "duration": session_data.session_duration,
            "status": "pending",  # pending, active, completed, cancelled
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "ended_at": None,
            "code": "",
            "cursor_positions": {},
            "chat_messages": []
        }
        
        await pair_programming_collection.insert_one(session)
        
        # Send invitation to partner
        await NotificationService.create_notification(
            user_id=partner_id,
            title="Pair Programming Invitation",
            message=f"{current_user['full_name']} has invited you to a pair programming session in {session_data.language}",
            notification_type="pair_programming",
            priority="high",
            action_url=f"/pair-programming/{session_id}",
            data={
                "session_id": session_id,
                "inviter_id": user_id,
                "inviter_name": current_user["full_name"],
                "language": session_data.language,
                "duration": session_data.session_duration
            }
        )
        
        return {
            "message": "Pair programming session created",
            "session_id": session_id,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create pair programming session error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")

# Technical Documentation Routes
@app.post("/api/docs/generate", tags=["Documentation"])
async def generate_documentation(
    code: str = Form(...),
    language: str = Form("python"),
    current_user: dict = Depends(verify_token)
):
    """Generate documentation for code"""
    try:
        user_id = str(current_user["_id"])
        
        # Simple documentation generation
        # In production, use AI or documentation generators
        
        documentation = {
            "functions": [],
            "classes": [],
            "variables": [],
            "imports": [],
            "summary": "Code documentation",
            "complexity": "O(n)",
            "suggestions": ["Add comments", "Improve variable names"]
        }
        
        # Extract functions from code (simple regex for Python)
        if language == "python":
            import re
            function_pattern = r'def\s+(\w+)\s*\((.*?)\):'
            functions = re.findall(function_pattern, code, re.DOTALL)
            for func_name, params in functions:
                documentation["functions"].append({
                    "name": func_name,
                    "parameters": params.split(',') if params else [],
                    "description": f"Function {func_name}"
                })
        
        # Save to database
        await technical_docs_collection.insert_one({
            "user_id": user_id,
            "code": code[:2000],
            "language": language,
            "documentation": documentation,
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "documentation": documentation,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Generate documentation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate documentation")
    
@app.post("/api/projects", tags=["Projects"])
async def create_project(
    title: str = Form(...),
    description: str = Form(...),
    project_type: str = Form(...),
    tech_stack: str = Form(""),
    tags: str = Form(""),
    timeline_days: int = Form(30),
    files: List[UploadFile] = File(None),
    current_user: dict = Depends(verify_token)
):
    """Create a new project with file attachments"""
    try:
        user_id = str(current_user["_id"])
        
        # Parse tech stack and tags
        tech_stack_list = [t.strip() for t in tech_stack.split(",") if t.strip()]
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        # Handle file uploads
        attachments = []
        if files:
            for file in files:
                content, file_size = await validate_file(file)
                upload_result = await upload_to_cloud_storage(
                    content,
                    f"project_{user_id}_{datetime.now().timestamp()}_{file.filename}",
                    file.content_type or "application/octet-stream"
                )
                attachments.append(upload_result["url"])
        
        project = {
            "title": title,
            "description": description,
            "project_type": project_type,
            "creator_id": user_id,
            "creator_name": current_user["full_name"],
            "tech_stack": tech_stack_list,
            "tags": tags_list,
            "timeline_days": timeline_days,
            "attachments": attachments,
            "status": "active",
            "team_members": [user_id],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "milestones": [],
            "tasks": [],
            "visibility": "public"
        }
        
        result = await projects_collection.insert_one(project)
        project_id = str(result.inserted_id)
        
        return {
            "message": "Project created successfully",
            "project_id": project_id,
            "project": {
                **project,
                "id": project_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")    

@app.get("/api/projects/{project_id}", tags=["Projects"])
async def get_project_detail(
    project_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get project details"""
    try:
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Convert ObjectId to string
        project["_id"] = str(project["_id"])
        
        return project
    except Exception as e:
        logger.error(f"Get project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project")
    
    
# WebSocket Route
@app.websocket("/api/ws/{connection_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_id: str,
    token: str = Query(...)
):
    """WebSocket endpoint for real-time communication"""
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        if not user_id:
            await websocket.close(code=1008)
            return
        
        # Connect
        await WebSocketManager.connect(websocket, connection_id, user_id)
        
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                message_type = message_data.get("type")
                
                if message_type == "ping":
                    # Respond to ping
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                elif message_type == "group_message":
                    # Handle group message
                    group_id = message_data["group_id"]
                    content = message_data["content"]
                    message_type = message_data.get("message_type", "text")
                    
                    # Save message to database
                    message = {
                        "sender_id": user_id,
                        "sender_name": payload.get("full_name", "User"),
                        "content": content,
                        "message_type": message_type,
                        "timestamp": datetime.now(timezone.utc),
                        "read_by": [user_id]
                    }
                    
                    # Check for AI assistant
                    group = await groups_collection.find_one({"_id": ObjectId(group_id)})
                    if group and content.startswith("@assistant") and group.get("ai_assistant_enabled", False):
                        question = content.replace("@assistant", "").strip()
                        context = f"Group: {group['name']}, User: {payload.get('full_name')}"
                        ai_response = await AIService.chat_assistant(question, {"context": context})
                        
                        # Send AI response
                        ai_message = {
                            "sender_id": "ai_assistant",
                            "sender_name": "AI Assistant",
                            "content": ai_response,
                            "message_type": "ai",
                            "timestamp": datetime.now(timezone.utc)
                        }
                        
                        await groups_collection.update_one(
                            {"_id": ObjectId(group_id)},
                            {"$push": {"messages": {"$each": [message, ai_message]}}}
                        )
                        
                        # Broadcast both messages
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "new_message",
                                "message_id": str(uuid.uuid4()),
                                "group_id": group_id,
                                "sender_id": user_id,
                                "sender_name": payload.get("full_name", "User"),
                                "content": content,
                                "message_type": message_type,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            user_id
                        )
                        
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "new_message",
                                "message_id": str(uuid.uuid4()),
                                "group_id": group_id,
                                "sender_id": "ai_assistant",
                                "sender_name": "AI Assistant",
                                "content": ai_response,
                                "message_type": "ai",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        )
                    else:
                        result = await messages_collection.insert_one(message)
                        message_id = str(result.inserted_id)
                        
                        # Broadcast to group
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "new_message",
                                "message_id": message_id,
                                "group_id": group_id,
                                "sender_id": user_id,
                                "sender_name": payload.get("full_name", "User"),
                                "content": content,
                                "message_type": message_type,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            user_id
                        )
                    
                elif message_type == "typing":
                    # Handle typing indicator
                    group_id = message_data.get("group_id")
                    if group_id:
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "user_typing",
                                "user_id": user_id,
                                "user_name": payload.get("full_name", "User"),
                                "group_id": group_id
                            },
                            user_id
                        )
                
                elif message_type == "pair_programming":
                    # Handle pair programming updates
                    session_id = message_data.get("session_id")
                    code = message_data.get("code")
                    cursor_position = message_data.get("cursor_position")
                    
                    if session_id and code is not None:
                        # Update session code
                        await pair_programming_collection.update_one(
                            {"session_id": session_id},
                            {"$set": {
                                "code": code,
                                f"cursor_positions.{user_id}": cursor_position,
                                "updated_at": datetime.now(timezone.utc)
                            }}
                        )
                        
                        # Broadcast to other participant
                        session = await pair_programming_collection.find_one({"session_id": session_id})
                        if session:
                            other_user = session["user2_id"] if session["user1_id"] == user_id else session["user1_id"]
                            await WebSocketManager.send_to_user(other_user, {
                                "type": "pair_programming_update",
                                "session_id": session_id,
                                "code": code,
                                "cursor_position": cursor_position,
                                "user_id": user_id,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                        
        except WebSocketDisconnect:
            WebSocketManager.disconnect(connection_id, user_id)
            
    except jwt.PyJWTError:
        await websocket.close(code=1008)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass

# Admin Routes
@app.get("/api/admin/stats", tags=["Admin"])
async def get_admin_stats(current_user: dict = Depends(verify_token)):
    """Get admin statistics"""
    try:
        # Check if user is admin
        if current_user["user_type"] not in [UserType.ADMIN, UserType.HOD]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get total counts
        total_users = await users_collection.count_documents({})
        total_students = await users_collection.count_documents({"user_type": UserType.STUDENT.value})
        total_challenges = await challenges_collection.count_documents({})
        total_submissions = await submissions_collection.count_documents({})
        total_groups = await groups_collection.count_documents({})
        total_projects = await projects_collection.count_documents({})
        total_repositories = await code_repositories_collection.count_documents({})
        
        # Get daily active users (last 24 hours)
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        daily_active_users = await users_collection.count_documents({
            "last_active": {"$gte": day_ago}
        })
        
        # Get completion rates
        completed_submissions = await submissions_collection.count_documents({"completed": True})
        completion_rate = (completed_submissions / total_submissions * 100) if total_submissions > 0 else 0
        
        # Get user growth (last 30 days)
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        new_users = await users_collection.count_documents({
            "created_at": {"$gte": month_ago}
        })
        
        # Get challenge completion by stage
        pipeline = [
            {"$match": {"completed": True}},
            {"$lookup": {
                "from": "challenges",
                "localField": "challenge_id",
                "foreignField": "_id",
                "as": "challenge"
            }},
            {"$unwind": "$challenge"},
            {"$group": {
                "_id": "$challenge.stage",
                "count": {"$sum": 1}
            }}
        ]
        
        stage_completion = list(await submissions_collection.aggregate(pipeline).to_list(length=None))
        
        # Get system health
        system_health = await health_check()
        
        return {
            "summary": {
                "total_users": total_users,
                "total_students": total_students,
                "total_challenges": total_challenges,
                "total_submissions": total_submissions,
                "total_groups": total_groups,
                "total_projects": total_projects,
                "total_repositories": total_repositories,
                "daily_active_users": daily_active_users,
                "completion_rate": round(completion_rate, 2),
                "new_users_last_30_days": new_users
            },
            "stage_completion": {
                stage["_id"]: stage["count"] for stage in stage_completion
            },
            "system_health": system_health,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get admin stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin statistics")

# Initialize Data
async def initialize_sample_data():
    """Initialize sample data for development"""
    try:
        # Check if data already exists
        if await challenges_collection.count_documents({}) > 0:
            logger.info("Sample data already exists, skipping initialization")
            return
        
        logger.info("Initializing sample data...")
        
        # Sample challenges
        sample_challenges = [
            {
                "title": "Introduce Yourself in English",
                "description": "Record a 30-second self-introduction in clear English. Focus on pronunciation and fluency.",
                "stage": Stage.FRESHIE.value,
                "challenge_type": "voice",
                "difficulty": Difficulty.EASY.value,
                "credits_reward": 50,
                "time_limit": 180,
                "correct_text": "Hello, my name is [Your Name]. I am a first year student at EduSync University. I am studying Computer Science and Engineering. I enjoy programming, reading books, and playing sports. My goal is to become a software engineer and contribute to innovative projects.",
                "tags": ["english", "pronunciation", "introduction", "communication"],
                "requirements": [
                    "Speak clearly and confidently",
                    "Use proper sentence structure",
                    "Maintain good pacing",
                    "Include personal details"
                ],
                "instructions": "1. Click the record button\n2. Speak clearly into your microphone\n3. Listen to your recording before submitting\n4. Submit when satisfied",
                "hints": [
                    "Practice a few times before recording",
                    "Speak at a moderate pace",
                    "Smile while speaking for better tone",
                    "Use simple, clear sentences"
                ],
                "learning_objectives": [
                    "Improve English pronunciation",
                    "Build confidence in speaking",
                    "Learn self-introduction structure"
                ],
                "created_by": "system",
                "created_by_name": "System Admin",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "title": "Python FizzBuzz Challenge",
                "description": "Write a Python program that prints numbers from 1 to 100. For multiples of 3, print 'Fizz' instead of the number. For multiples of 5, print 'Buzz'. For numbers which are multiples of both 3 and 5, print 'FizzBuzz'.",
                "stage": Stage.SOPHOMORE.value,
                "challenge_type": "coding",
                "difficulty": Difficulty.EASY.value,
                "credits_reward": 100,
                "time_limit": 300,
                "language": "python",
                "code_template": "def fizzbuzz(n):\n    # Your code here\n    pass\n\n# Test the function\nfor i in range(1, 101):\n    print(fizzbuzz(i))",
                "test_cases": [
                    {"input": "", "output": "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz\n..."},
                    {"input": "15", "output": "FizzBuzz"}
                ],
                "tags": ["python", "algorithms", "loops", "conditionals"],
                "requirements": [
                    "Use proper Python syntax",
                    "Handle edge cases",
                    "Write clean, readable code",
                    "Add comments where necessary"
                ],
                "instructions": "1. Write your solution in the code editor\n2. Test with the provided test cases\n3. Ensure all requirements are met\n4. Submit when ready",
                "hints": [
                    "Use modulo operator %",
                    "Consider using range() function",
                    "Think about the order of conditions",
                    "Test with small numbers first"
                ],
                "solution_explanation": "The FizzBuzz problem tests basic programming skills. The solution involves iterating through numbers 1 to 100 and using conditional statements to check divisibility by 3 and 5.",
                "learning_objectives": [
                    "Understand loops and conditionals",
                    "Practice problem-solving",
                    "Learn about modulo operator",
                    "Improve code readability"
                ],
                "created_by": "system",
                "created_by_name": "System Admin",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]
        
        await challenges_collection.insert_many(sample_challenges)
        logger.info(f"✅ Created {len(sample_challenges)} sample challenges")
        
        # Sample jobs
        sample_jobs = [
            {
                "company": "Tech Solutions Inc.",
                "role": "Junior Python Developer",
                "description": "We're looking for a passionate Python developer to join our team. You'll work on backend APIs, data processing pipelines, and contribute to open-source projects.",
                "requirements": [
                    "Strong Python programming skills",
                    "Understanding of REST APIs",
                    "Basic knowledge of databases",
                    "Problem-solving mindset",
                    "Good communication skills"
                ],
                "salary_range": "₹4-6 LPA",
                "location": "Bangalore, Karnataka",
                "job_type": "Full-time",
                "experience_required": "0-2 years",
                "posted_at": datetime.now(timezone.utc),
                "apply_by": datetime.now(timezone.utc) + timedelta(days=30),
                "preferred_departments": ["CSE", "IT", "ECE"],
                "status": "active",
                "applications": [],
                "contact_email": "careers@techsolutions.com",
                "website": "https://techsolutions.com/careers"
            }
        ]
        
        await jobs_collection.insert_many(sample_jobs)
        logger.info(f"✅ Created {len(sample_jobs)} sample jobs")
        
        # Sample groups
        sample_groups = [
            {
                "name": "CSE Freshies 2024",
                "description": "Welcome all Computer Science freshmen! Let's learn, grow, and succeed together.",
                "department": "CSE",
                "year": 1,
                "created_by": "system",
                "created_by_name": "System Admin",
                "members": [],
                "admins": ["system"],
                "is_educational": True,
                "privacy": "public",
                "max_members": 200,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "ai_assistant_enabled": True,
                "assistant_model": OLLAMA_MODEL
            }
        ]
        
        await groups_collection.insert_many(sample_groups)
        logger.info(f"✅ Created {len(sample_groups)} sample groups")
        
        # Admin user
        admin_email = "admin@edusync.com"
        admin_exists = await users_collection.find_one({"email": admin_email})
        if not admin_exists:
            admin_user = {
                "email": admin_email,
                "password": hash_password("Admin@123"),
                "full_name": "System Administrator",
                "user_type": UserType.ADMIN.value,
                "department": "Administration",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "is_active": True,
                "is_verified": True,
                "profile_picture": "https://api.dicebear.com/7.x/avataaars/svg?seed=admin",
                "bio": "System administrator for EduSync platform",
                "skills": ["System Administration", "Database Management", "Python", "FastAPI"],
                "interests": ["Education Technology", "AI", "System Design"],
                "notification_preferences": {
                    "email": True,
                    "push": True,
                    "sms": False,
                    "challenge_reminders": True,
                    "deadline_alerts": True,
                    "achievement_alerts": True
                }
            }
            
            await users_collection.insert_one(admin_user)
            logger.info("✅ Created admin user (admin@edusync.com / Admin@123)")
        
        # Demo student
        demo_email = "student@edusync.com"
        demo_exists = await users_collection.find_one({"email": demo_email})
        if not demo_exists:
            demo_user = {
                "email": demo_email,
                "password": hash_password("Student@123"),
                "full_name": "Demo Student",
                "user_type": UserType.STUDENT.value,
                "department": "CSE",
                "year": 2,
                "roll_number": "CS2024001",
                "stage": Stage.SOPHOMORE.value,
                "credits": 500,
                "xp": 1500,
                "level": 3,
                "daily_login_streak": 7,
                "weekly_login_streak": 3,
                "current_stage_progress": 45,
                "last_login": datetime.now(timezone.utc),
                "last_active": datetime.now(timezone.utc),
                "weak_areas": ["Data Structures", "Algorithms"],
                "strengths": ["Web Development", "Python"],
                "skills": ["Python", "JavaScript", "HTML/CSS", "React"],
                "interests": ["Web Development", "AI/ML", "Open Source"],
                "career_goals": ["Software Engineer", "Full Stack Developer"],
                "completed_challenges": 15,
                "projects_completed": 3,
                "courses_enrolled": ["CS101", "CS201"],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "is_active": True,
                "is_verified": True,
                "profile_picture": "https://api.dicebear.com/7.x/avataaars/svg?seed=student",
                "bio": "Passionate computer science student interested in web development and AI.",
                "learning_style": "visual",
                "preferred_language": "en",
                "timezone": "Asia/Kolkata",
                "notification_preferences": {
                    "email": True,
                    "push": True,
                    "sms": False,
                    "challenge_reminders": True,
                    "deadline_alerts": True,
                    "achievement_alerts": True
                }
            }
            
            await users_collection.insert_one(demo_user)
            demo_user_id = str(demo_user["_id"])
            logger.info("✅ Created demo student (student@edusync.com / Student@123)")
            
            # Create badges for demo student
            await badges_collection.insert_one({
                "user_id": demo_user_id,
                "badges": [
                    {
                        "name": "Welcome Aboard!",
                        "icon": "🎉",
                        "earned_date": datetime.now(timezone.utc),
                        "description": "Welcome to EduSync 4.0",
                        "category": "welcome"
                    },
                    {
                        "name": "7-Day Streak",
                        "icon": "🔥",
                        "earned_date": datetime.now(timezone.utc) - timedelta(days=1),
                        "description": "Logged in for 7 consecutive days",
                        "category": "streak"
                    },
                    {
                        "name": "Challenge Enthusiast",
                        "icon": "⚡",
                        "earned_date": datetime.now(timezone.utc) - timedelta(days=3),
                        "description": "Completed 10 challenges",
                        "category": "challenges"
                    }
                ],
                "created_at": datetime.now(timezone.utc)
            })
            
            # Create sample repository for demo student
            await VersionControlService.create_repository(
                user_id=demo_user_id,
                name="Sample Python Projects",
                description="A collection of beginner Python projects for learning",
                is_public=True
            )
        
        # Sample announcements
        sample_announcements = [
            {
                "title": "Welcome to EduSync 4.0!",
                "content": "We're excited to launch EduSync 4.0 with new features including AI-powered learning, voice challenges, and real-time collaboration.",
                "type": "announcement",
                "priority": "high",
                "active": True,
                "author_name": "Admin",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=30)
            }
        ]
        
        await announcements_collection.insert_many(sample_announcements)
        logger.info("✅ Created sample announcements")
        
        # Sample study materials
        sample_materials = [
            {
                "title": "Python Programming Basics",
                "description": "Introduction to Python programming language",
                "subject": "Programming",
                "department": "CSE",
                "year": 1,
                "file_url": "/static/sample/python_basics.pdf",
                "file_type": "pdf",
                "file_size": 1024 * 1024,  # 1MB
                "uploaded_by": "system",
                "uploaded_by_name": "System Admin",
                "uploaded_at": datetime.now(timezone.utc),
                "download_count": 0,
                "tags": ["python", "programming", "basics"]
            }
        ]
        
        await study_materials_collection.insert_many(sample_materials)
        logger.info("✅ Created sample study materials")
        
        logger.info("🎉 Sample data initialization complete!")
        
    except Exception as e:
        logger.error(f"Sample data initialization error: {e}")

async def create_indexes():
    """Create database indexes for better performance"""
    try:
        # Users collection indexes
        await users_collection.create_index([("email", 1)], unique=True)
        await users_collection.create_index([("roll_number", 1)], sparse=True)
        await users_collection.create_index([("user_type", 1)])
        await users_collection.create_index([("department", 1), ("year", 1)])
        await users_collection.create_index([("stage", 1)])
        await users_collection.create_index([("credits", -1)])
        await users_collection.create_index([("last_active", -1)])
        
        # Challenges collection indexes
        await challenges_collection.create_index([("stage", 1)])
        await challenges_collection.create_index([("challenge_type", 1)])
        await challenges_collection.create_index([("difficulty", 1)])
        await challenges_collection.create_index([("tags", 1)])
        await challenges_collection.create_index([("created_at", -1)])
        
        # Submissions collection indexes
        await submissions_collection.create_index([("user_id", 1)])
        await submissions_collection.create_index([("challenge_id", 1)])
        await submissions_collection.create_index([("user_id", 1), ("challenge_id", 1)])
        await submissions_collection.create_index([("submitted_at", -1)])
        await submissions_collection.create_index([("score", -1)])
        await submissions_collection.create_index([("completed", 1)])
        
        # Groups collection indexes
        await groups_collection.create_index([("department", 1), ("year", 1)])
        await groups_collection.create_index([("members", 1)])
        await groups_collection.create_index([("created_at", -1)])
        
        # Repositories collection indexes
        await code_repositories_collection.create_index([("owner_id", 1)])
        await code_repositories_collection.create_index([("is_public", 1)])
        await code_repositories_collection.create_index([("created_at", -1)])
        
        # Commits collection indexes
        await code_commits_collection.create_index([("repository_id", 1)])
        await code_commits_collection.create_index([("author_id", 1)])
        await code_commits_collection.create_index([("timestamp", -1)])
        
        logger.info("✅ Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Index creation error: {e}")

def print_banner():
    """Print startup banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║         ███████╗██████╗ ██╗   ██╗███████╗██╗   ██╗███╗   ██╗ ║
    ║         ██╔════╝██╔══██╗██║   ██║██╔════╝╚██╗ ██╔╝████╗  ██║ ║
    ║         █████╗  ██║  ██║██║   ██║███████╗ ╚████╔╝ ██╔██╗ ██║ ║
    ║         ██╔══╝  ██║  ██║██║   ██║╚════██║  ╚██╔╝  ██║╚██╗██║ ║
    ║         ███████╗██████╔╝╚██████╔╝███████║   ██║   ██║ ╚████║ ║
    ║         ╚══════╝╚═════╝  ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ║
    ║                                                              ║
    ║                Campus Learning Platform 4.0                  ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    
    🚀 Version: 4.0.0
    📅 Started: {datetime}
    🌐 API: http://localhost:8000
    📚 Docs: http://localhost:8000/api/docs
    🩺 Health: http://localhost:8000/api/health
    
    🔧 Features:
      ✅ AI-Powered Learning Path
      ✅ Voice Recognition & Tamil Support
      ✅ Real-time Code Compiler (FIXED)
      ✅ GitHub-like Code Repositories
      ✅ Pair Programming Sessions
      ✅ AI Code Assistance & Reviews
      ✅ Study Groups with AI Assistant
      ✅ Mock Interview System
      ✅ Job Board & Career Services
      ✅ Badges & Achievement System
      ✅ Real-time Chat (WebSocket)
      ✅ Forum for Discussions
      ✅ Admin Dashboard & Analytics
      ✅ English Teacher with Tamil Feedback
    
    👤 Demo Accounts:
      • Admin: admin@edusync.com / Admin@123
      • Student: student@edusync.com / Student@123
    
    📊 Ready to transform education with AI!
    """
    
    print(banner.format(datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    
# =============== FILE CONTENT API ROUTES ===============
@app.get("/api/files/{file_id}/content", tags=["Files"])
async def get_file_content(
    file_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get file content from storage"""
    try:
        user_id = str(current_user["_id"])
        
        # --- FIX: Handle both ObjectId (24-char) and UUID (like 8b74d210...) ---
        file_record = None
        
        # 1. Try finding by MongoDB ObjectId (_id)
        if len(file_id) == 24:
            try:
                # Tries to convert the string to MongoDB ObjectId
                file_record = await files_collection.find_one({"_id": ObjectId(file_id)})
            except Exception:
                # Ignore if conversion fails, move to UUID check
                pass 
        
        # 2. If not found, try finding by the UUID string (stored in the 'file_id' field)
        if not file_record:
            file_record = await files_collection.find_one({"file_id": file_id})

        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        # --- FIX END ---
        
        # Check access permissions
        if file_record.get("owner_id") != user_id and not file_record.get("is_public", False):
            # Check if user is in the same project/group
            if file_record.get("project_id"):
                # Project ID is expected to be an ObjectId
                project = await projects_collection.find_one({"_id": ObjectId(file_record["project_id"])})
                if not project or user_id not in project.get("team_members", []):
                    raise HTTPException(status_code=403, detail="Access denied")
        
        # Get file path from URL
        file_url = file_record.get("url", "")
        if not file_url.startswith("/static/"):
            raise HTTPException(status_code=404, detail="File path not found")
        
        # Construct the local file path
        file_path = "static" + file_url.replace("/static/", "/")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on server")
        
        # Read file content based on file type
        file_ext = Path(file_path).suffix.lower()

        # Text-based files
        text_files = ['.txt', '.py', '.java', '.cpp', '.c', '.js', '.html', '.css', '.md', '.json', '.csv', '.xml', '.yaml', '.yml']
        
        if file_ext in text_files:
            # Using aiofiles for ASYNCHRONOUS reading
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = await f.read()
            
            return {
                "content": content,
                "type": "text",
                "encoding": "utf-8",
                "file_name": file_record.get("name", ""),
                "file_type": file_record.get("type", ""),
                "size": os.path.getsize(file_path)
            }
        
        # For binary files (images, PDF, etc.), return base64
        elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            # Using aiofiles for ASYNCHRONOUS reading
            async with aiofiles.open(file_path, 'rb') as f:
                content_bytes = await f.read()
            
            content = base64.b64encode(content_bytes).decode('utf-8')
            
            return {
                "content": content,
                "type": "image",
                "encoding": "base64",
                "file_name": file_record.get("name", ""),
                "file_type": file_record.get("type", ""),
                "size": os.path.getsize(file_path)
            }
        
        elif file_ext in ['.pdf']:
            # Using aiofiles for ASYNCHRONOUS reading
            async with aiofiles.open(file_path, 'rb') as f:
                content_bytes = await f.read()
            
            content = base64.b64encode(content_bytes).decode('utf-8')
            
            return {
                "content": content,
                "type": "pdf",
                "encoding": "base64",
                "file_name": file_record.get("name", ""),
                "file_type": file_record.get("type", ""),
                "size": os.path.getsize(file_path)
            }
        
        else:
            # For other file types, return download URL
            return {
                "url": file_record.get("url"),
                "type": "binary",
                "file_name": file_record.get("name", ""),
                "file_type": file_record.get("type", ""),
                "size": os.path.getsize(file_path),
                "download_only": True
            }
        
    except HTTPException:
        # Re-raise HTTPException directly (404, 403)
        raise
    except Exception as e:
        logger.error(f"Get file content error: {e}")
        # Return the specific error message for debugging purposes
        raise HTTPException(status_code=500, detail=f"Failed to get file content: {str(e)}")

@app.get("/api/projects/{project_id}/files", tags=["Projects"])
async def get_project_files(
    project_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get all files for a project"""
    try:
        user_id = str(current_user["_id"])
        
        # Get project
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check if user has access
        if user_id not in project.get("team_members", []):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get files from files collection
        files = await files_collection.find({
            "project_id": project_id
        }).sort("uploaded_at", -1).to_list(100)
        
        # Format response
        formatted_files = []
        for file in files:
            formatted_files.append({
                "id": str(file["_id"]),
                "name": file.get("name", ""),
                "type": file.get("type", ""),
                "url": file.get("url", ""),
                "size": file.get("size", 0),
                "uploaded_by": file.get("uploaded_by_name", ""),
                "uploaded_at": file.get("uploaded_at"),
                "description": file.get("description", "")
            })
        
        return {"files": formatted_files}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get project files error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get project files")    
    

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "path": request.url.path,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "path": request.url.path,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information"""
    return {
        "message": "🎯 EduSync Campus Learning Platform 4.0",
        "version": "4.0.0",
        "status": "operational",
        "documentation": "/api/docs",
        "health_check": "/api/health",
        "features": [
            "AI-Powered Personalized Learning",
            "Multi-language Support (English/Tamil)",
            "Real-time Code Execution (FIXED)",
            "GitHub-like Code Repositories",
            "Pair Programming Sessions",
            "AI Code Assistance & Reviews",
            "Voice-based Challenges",
            "Study Groups with AI Assistant",
            "Career Development Services",
            "Forum for Discussions",
            "Gamified Learning Experience"
        ],
        "quick_links": {
            "register": "/api/auth/register",
            "login": "/api/auth/login",
            "challenges": "/api/challenges",
            "compiler": "/api/compiler/execute",
            "repositories": "/api/repositories",
            "ai_chat": "/api/ai/chat",
            "english_teacher": "/api/ai/english-teacher",
            "groups": "/api/groups",
            "leaderboard": "/api/leaderboard",
            "profile": "/api/users/profile"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Static files
@app.get("/static/{file_path:path}")
async def serve_static_file(file_path: str):
    """Serve static files"""
    file_location = f"static/{file_path}"
    if os.path.exists(file_location):
        return FileResponse(file_location)
    raise HTTPException(status_code=404, detail="File not found")

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
    app,
    host="0.0.0.0",
    port=8000,
    log_level="info"
)
