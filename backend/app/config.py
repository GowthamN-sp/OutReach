import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() == "true"


PRODUCTION = os.getenv("APP_ENV", "development").lower() == "production"
SECURE = PRODUCTION or flag("COOKIE_SECURE")
SIGNUP = flag("ALLOW_SIGNUP", not PRODUCTION)
FRONT = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
PUBLIC = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
REDIRECT = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
)
LIMIT = max(1, int(os.getenv("DAILY_SEND_LIMIT", "25")))
DB_PATH = ROOT / os.getenv("V2_DATABASE_PATH", "data/outreachdesk-v2.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE = URL.create("sqlite", database=str(DB_PATH))
