import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base Directory of the application
BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Upload directory
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Database: prefer Neon PostgreSQL, fall back to SQLite for offline dev
DATABASE_URL = os.getenv("NEON_URL") or os.getenv("DATABASE_URL") or f"sqlite:///{DATA_DIR}/sfdr.db"

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Default settings
DEFAULT_MODEL = "llama-3.3-70b-versatile"
SUPPORTED_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it"
]
