"""
Vercel Serverless Function entrypoint for the FastAPI backend.
Exposes `app` so Vercel routes `/api/*` and `/health*` requests directly to FastAPI.
"""
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parent.parent / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402, F401
