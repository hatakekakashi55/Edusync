"""
EduSync Backend - Configuration Module
All environment variables, constants, and configuration settings.
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

# =============== MULTIPLE GEMINI API KEYS ===============
GEMINI_API_KEYS = {
    "default": os.getenv("GEMINI_API_KEY_1", "AIzaSyAZRz0s9XdvB_evcGS8IjHNArtb9URGd4g"),
    "grammar": os.getenv("GEMINI_API_KEY_2", "AIzaSyCCC5GlBp2u7JxIgu1ht-qLmVECilztR_M"),
    "pronunciation": os.getenv("GEMINI_API_KEY_3", "AIzaSyAkRwPV5WrCUOJqBXxkOnhBCNLvpbvgLHM"),
    "sentence": os.getenv("GEMINI_API_KEY_4", "AIzaSyCjXuE6BXyToPFsNyBxd-eMqlBUtaDoVm0"),
}

# =============== GEMINI MODELS CONFIGURATION ===============
GEMINI_MODELS_LIST = {
    'gemini-1.5-flash-latest': 'Fast & Stable (Recommended)',
    'gemini-2.0-flash-thinking-exp-01-21': 'Next-Gen Flash with Thinking (Experimental)',
    'gemini-1.5-pro-latest': 'Pro (High Capability)',
}

AVAILABLE_MODELS = [
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-2.0-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-pro'
]

# =============== HOD AI ASSISTANT API KEYS ===============
HOD_API_KEYS = {
    "gemini": os.getenv("HOD_GEMINI_API_KEY", "AIzaSyD_EAZ5s93OLQJuw4_JjAcZb9Ur2xR-NXs"),
    "openai": os.getenv("HOD_OPENAI_API_KEY", ""),
    "speech": os.getenv("HOD_SPEECH_API_KEY", ""),
    "custom": os.getenv("HOD_CUSTOM_API_KEY", ""),
}

# =============== FACULTY AI ASSISTANT API KEYS ===============
FACULTY_AI_API_KEYS = {
    "default": os.getenv("FACULTY_GEMINI_API_KEY_1", os.getenv("GEMINI_API_KEY_1", "AIzaSyAPaE17mWxwDUUlGLc1rD6IdrpEIZv-7Vc")),
    "voice": os.getenv("FACULTY_GEMINI_API_KEY_2", os.getenv("GEMINI_API_KEY_2", "AIzaSyBJv9pO_GYfts3bLJ5KWKeDAKx3lDukORU")),
    "analysis": os.getenv("FACULTY_GEMINI_API_KEY_3", os.getenv("GEMINI_API_KEY_3", "AIzaSyAkRwPV5WrCUOJqBXxkOnhBCNLvpbvgLHM")),
    "content": os.getenv("FACULTY_GEMINI_API_KEY_4", os.getenv("GEMINI_API_KEY_4", "AIzaSyCjXuE6BXyToPFsNyBxd-eMqlBUtaDoVm0")),
}

# =============== RAPIDAPI CONFIGURATION ===============
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "linkedin-jobs-search.p.rapidapi.com")

# =============== AI CONFIGURATION ===============
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")

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

# Initialize model objects for each key
gemini_models = {}
for key_name, api_key in GEMINI_API_KEYS.items():
    gemini_models[key_name] = {"api_key": api_key, "models": AVAILABLE_MODELS}


def get_gemini_config(feature_type="default"):
    """Returns (api_key, model_names) for the requested feature"""
    config = gemini_models.get(feature_type)
    if not config:
        config = gemini_models.get("default")
    return config
