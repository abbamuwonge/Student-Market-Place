"""Settings. Every value can be overridden with an environment variable."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-before-deploying")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'campusmart.db'}")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB per photo

PAGE_SIZE = 20

# The first admin account is created automatically on startup (see seed.py).
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@campusmart.ug")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin12345")
