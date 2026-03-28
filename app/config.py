"""
EduSync Backend - Configuration Module
All environment variables, constants, and configuration settings.

═══════════════════════════════════════════════════════════════
INIXA OS — AI Engine Configuration
5 FREE AI Engines — NO API Key, NO Auth, UNLIMITED!
Fallback: DuckDuckGo → LLM7 → BlackBox → Pollinations → Pollinations Simple
═══════════════════════════════════════════════════════════════
"""
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edusync")

# =============== JWT CONFIGURATION ===============
SECRET_KEY = os.getenv("SECRET_KEY", "edusync-secret-key-2025-v1-do-not-use-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours for regular users
REFRESH_TOKEN_EXPIRE_DAYS = 30

# =============== RAPIDAPI CONFIGURATION ===============
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "linkedin-jobs-search.p.rapidapi.com")

# ═══════════════════════════════════════════════════════════════
# 5 FREE AI ENGINES — NO API Key, NO Auth, UNLIMITED!
# ═══════════════════════════════════════════════════════════════

# ENGINE 1: POLLINATIONS (OpenAI-compatible)
POLLINATIONS_API_BASE = os.getenv("POLLINATIONS_API_BASE", "https://text.pollinations.ai/openai")
POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "openai")

# ENGINE 2: DUCKDUCKGO (via Cloudflare Worker)
DDG_API_BASE = os.getenv("DDG_API_BASE", "https://bitter-sea-46dc.keerthan4531.workers.dev/chat")
DDG_MODEL = os.getenv("DDG_MODEL", "gpt-4o-mini")

# ENGINE 3: BLACKBOX AI
BLACKBOX_API_BASE = os.getenv("BLACKBOX_API_BASE", "https://api.blackbox.ai/api/chat")

# ENGINE 4: LLM7
LLM7_API_BASE = os.getenv("LLM7_API_BASE", "https://api.llm7.io/v1/chat/completions")
LLM7_MODEL = os.getenv("LLM7_MODEL", "gpt-4o-mini")

# ENGINE 5: POLLINATIONS SIMPLE (Last resort)
POLLINATIONS_SIMPLE_BASE = os.getenv("POLLINATIONS_SIMPLE_BASE", "https://text.pollinations.ai")
POLLINATIONS_SIMPLE_MODEL = os.getenv("POLLINATIONS_SIMPLE_MODEL", "openai")

# POLLINATIONS IMAGE GENERATION
POLLINATIONS_IMAGE_BASE = os.getenv("POLLINATIONS_IMAGE_BASE", "https://image.pollinations.ai/prompt")

# AI Engine Fallback Order (configurable)
AI_ENGINE_ORDER = os.getenv("AI_ENGINE_ORDER", "duckduckgo,llm7,blackbox,pollinations,pollinations-simple").split(",")

# AI Request Timeout (seconds)
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "90"))

# AI Max Retries
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))

# =============== REDIS CONFIGURATION ===============
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")

# =============== FILE UPLOAD CONFIGURATION ===============
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.mp3', '.mp4', '.txt', '.py', '.java', '.cpp', '.c', '.js', '.html', '.css', '.md', '.json', '.csv', '.xlsx', '.docx'}

# =============== DOCKER COMPILER CONFIGURATION ===============
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

DOCKER_CPU = "1.0"
DOCKER_MEMORY = "512m"
TIMEOUT_SECONDS = 30

# =============== HTML FILES MAPPING ===============
HTML_FILES = {
    "/": "login.html",
    "/login": "login.html",
    "/admin": "admin.html",
    "/career-prep": "career_prep.html",
    "/challenges": "Challenges.html",
    "/communication-stage": "communication_stage.html",
    "/faculty-dashboard": "faculty_dashboard.html",
    "/hod-dashboard": "hod_dashboard.html",
    "/learning-path": "learning path.html",
    "/profile": "profile.html",
    "/stage-2": "stage 2.html",
    "/student-dashboard": "student_dashboard.html",
}

# ═══════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY — Old config names still work
# ═══════════════════════════════════════════════════════════════
# These are kept so existing imports don't break
OLLAMA_BASE_URL = "deprecated"
OLLAMA_MODEL = "deprecated"
POLLINATIONS_API_KEY = ""  # Not needed — all engines are FREE
AVAILABLE_MODELS = ["inixa-free-engine"]
GEMINI_API_KEYS = {}
HOD_API_KEYS = {"gemini": ""}
FACULTY_AI_API_KEYS = {"default": "", "voice": "", "analysis": "", "content": ""}
GEMINI_MODELS_LIST = {}

# Old Gemini config functions (kept for backward compat)
gemini_models = {}


def get_gemini_config(feature_type="default"):
    """Legacy — returns None since Gemini is removed"""
    return None
